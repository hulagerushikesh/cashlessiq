"""Disposable CI assembly: real peers, private dummy PAT, isolated dummy worker.

The container has no network. Only the remote HTTPS exchange is substituted;
UID checks, private-file reads, process supervision, IPC, retention and custody
are the actual implementations. No service/installation or owner data is used.
"""

import hashlib
import json
import os
import select
import shutil
import signal
import subprocess
import sys
from uuid import uuid4

import pytest

if not (
    sys.platform == "linux" and os.getuid() == 0
    and os.environ.get("GITHUB_ACTIONS") == "true"
    and os.environ.get("GITHUB_REPOSITORY") == "hulagerushikesh/cashlessiq"
    and os.environ.get("CIQ_AGENT_RECEIPT_PEER_TEST") == "1"
):
    pytest.skip("Single-call assembly requires disposable CI", allow_module_level=True)

from single_call_fixtures import response_bytes
from test_agent_single_call_peer_linux import peers as peers

from ciq_api.agent_provider_identity import IDENTITY, PLAN
from ciq_api.agent_provider_peer import ENDPOINT


@pytest.mark.parametrize("peers", ["assembly"], indirect=True)
@pytest.mark.parametrize("fault", [None, "plan", "issue-ack", "observe-ack", "candidate"])
def test_original_cross_uid_dispatch_observation_and_reconstruction(peers, fault):
    s = peers
    snapshot, config, pin, body = s.material
    root = ENDPOINT.parents[1]
    # Refuse any existing path before registering teardown or changing files.
    root.mkdir(mode=0o755)
    children = []
    token = uuid4().hex.encode()
    pin_digest = hashlib.sha256(pin.canonical().encode()).hexdigest()
    reply = response_bytes(snapshot, pin.operation_id)
    if fault == "candidate":
        value = json.loads(reply)
        value["content"][0]["text"] = "PRIVATE invalid clinical answer"
        reply = json.dumps(value).encode()

    def launch(code, uid):
        child = subprocess.Popen(
            (sys.executable, "-I", "-B", "-c", code), cwd="/",
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={"LANG": "C.UTF-8"}, user=uid, group=uid, extra_groups=[],
            start_new_session=True,
        )
        children.append(child)
        return child

    def ready(child):
        assert select.select([child.stdout], [], [], 5)[0], "assembly readiness timed out"
        assert child.stdout.readline() == b"READY\n", "assembly readiness failed"

    def collect(child):
        out, err = child.communicate(timeout=20)
        assert child.returncode == 0 and out == b"PASS" and not err, "assembly child failed"

    def write_private(path, raw):
        path.write_bytes(raw)
        os.chown(path, 53004, 53004)
        path.chmod(0o600)

    prefix = """
import os, resource, time
from pathlib import Path
resource.setrlimit(resource.RLIMIT_CORE, (0,0))
def wait(path):
    end=time.monotonic()+5
    while not Path(path).is_file():
        assert time.monotonic()<end
        time.sleep(0.01)
"""
    client = prefix + f"""
from ciq_api.agent_contracts import AgentInput, AgentContext, AgentContractError
from ciq_api.agent_one_shot import CapturedOneShotConfig
from ciq_api.agent_single_call_journal import ReviewedCallPin
from ciq_api.agent_single_call_peer import SingleCallReceiptClient
from ciq_api.agent_provider_peer import ReviewedProviderPeerClient
from ciq_api.agent_single_call_custody import PreparedSingleCallCustody, ERROR
snapshot=AgentInput.model_validate_json({snapshot.model_dump_json()!r})
config=CapturedOneShotConfig.model_validate_json({config.model_dump_json()!r})
pin=ReviewedCallPin.model_validate_json({pin.model_dump_json()!r})
current=AgentContext(binding=snapshot.binding,tenant_active=True,policy_approved=True,
                     clinical_authorized=True,review_open=True)
def build():
    return PreparedSingleCallCustody(snapshot,current,config,pin,SingleCallReceiptClient(pin),
                                    ReviewedProviderPeerClient({pin_digest!r}))
"""
    # Only synthetic pins enter fixture argv; never actual credentials.
    worker = prefix + f"""
import sys, hashlib
from ciq_api.agent_https_worker import main
from ciq_api.agent_https_transport import SinglePostHTTPS
def exchange(self, body, *, timeout):
    assert os.getresuid()==(53004,)*3 and os.getresgid()==(53004,)*3 and not os.getgroups()
    assert body=={body!r} and self._host=={pin.hostname!r}
    assert hashlib.sha256(self._token.encode()).hexdigest()=={hashlib.sha256(token).hexdigest()!r}
    wait({str(root / 'response-ready')!r})
    return {reply!r}
SinglePostHTTPS.exchange=exchange
os._exit(main())
"""
    provider = prefix + f"""
import sys
from ciq_api import agent_provider_identity as identity, agent_https_process as process
from ciq_api.agent_provider_peer import ReviewedProviderPeer
identity.PYTHON=sys.executable
reads,spawns=[],[]
original_read=identity.read_private
def read(path,maximum):
    if path==identity.IDENTITY:
        reads.append(True)
    return original_read(path,maximum)
identity.read_private=read
original_popen=process.subprocess.Popen
def spawn(argv, **kwargs):
    assert argv==(sys.executable,'-I','-B','-m','ciq_api.agent_https_worker')
    spawns.append(True)
    return original_popen((sys.executable,'-I','-B','-c',{worker!r}),**kwargs)
process.subprocess.Popen=spawn
server=ReviewedProviderPeer({pin_digest!r})
server.bind()
os.write(1,b'READY\\n')
try:
    server.serve_once(timeout=12)
    assert {fault != 'plan'!r}
except ValueError:
    assert {fault == 'plan'!r}
finally:
    server.close()
assert len(reads)==len(spawns)=={0 if fault == 'plan' else 1}
os.write(1,b'PASS')
"""
    try:
        ENDPOINT.parent.mkdir(mode=0o755)
        os.chown(ENDPOINT.parent, 53004, 53004)
        write_private(IDENTITY, token)
        write_private(PLAN, json.dumps({
            "protocol": "ciq-private-provider-v2", "hostname": pin.hostname,
            "request_sha256": pin.request_sha256,
            "pin_sha256": "0" * 64 if fault == "plan" else (
                hashlib.sha256(pin.canonical().encode()).hexdigest()
            ),
        }).encode())
        # Custody can never read the dummy PAT or private provider plan.
        s.run(f"""
for name in ({str(IDENTITY)!r},{str(PLAN)!r}):
    try:
        Path(name).read_bytes()
    except PermissionError:
        pass
    else:
        raise AssertionError('provider private file exposed')
os.write(1,b'PASS')
""")
        original = client + f"""
attempt=build()
os.write(1,b'READY\\n')
wait({str(root / 'dispatch-ready')!r})
try:
    attempt.dispatch(current)
    assert {fault in (None, 'candidate')!r}
except AgentContractError as error:
    assert str(error)==ERROR and {fault not in (None, 'candidate')!r}
try:
    final=attempt.take_candidate(current)
    assert {fault is None!r} and final.candidate.run_id==pin.operation_id
    assert final.observation.response_sha256=={hashlib.sha256(reply).hexdigest()!r}
except AgentContractError as error:
    assert str(error)==ERROR and {fault is not None!r}
for repeat in (lambda: attempt.dispatch(current), lambda: attempt.take_candidate(current)):
    try:
        repeat()
    except AgentContractError as error:
        assert str(error)==ERROR
    else:
        raise AssertionError('original attempt reused')
os.write(1,b'PASS')
"""
        caller = launch(original, 53002)
        ready(caller)  # Prepare/import before starting either listener's deadline.
        remote = None
        if fault != "issue-ack":
            remote = launch(provider, 53004)
            ready(remote)
        issue = s.start(denied=fault == "issue-ack", lost=fault == "issue-ack")
        (root / "dispatch-ready").touch(mode=0o644)
        s.collect(issue, b"PASS")
        if fault in (None, "candidate", "observe-ack"):
            observed = s.start(denied=fault == "observe-ack", lost=fault == "observe-ack")
            (root / "response-ready").touch(mode=0o644)
            s.collect(observed, b"PASS")
        collect(caller)
        if remote is not None:
            collect(remote)
        phase = "issued" if fault in ("plan", "issue-ack") else "observed"
        s.run(f"status=SingleCallJournal(directory,pin).status()\n"
              f"assert status.phase=={phase!r} and status.uncertain_units==20\n"
              "os.write(1,b'PASS')", 53003)
        # A separately reconstructed custody still has no permission to send.
        reconstructed = client + """
attempt=build()
os.write(1,b'READY\\n')
""" + f"wait({str(root / 'reconstructed-ready')!r})\n" + """
try:
    attempt.dispatch(current)
except AgentContractError as error:
    assert str(error)==ERROR
else:
    raise AssertionError('reconstructed dispatch accepted')
os.write(1,b'PASS')
"""
        replacement = launch(reconstructed, 53002)
        ready(replacement)
        denied = s.start(denied=True)
        (root / "reconstructed-ready").touch(mode=0o644)
        collect(replacement)
        s.collect(denied, b"PASS")
    finally:
        for child in reversed(children):
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
            child.communicate(timeout=3)
        shutil.rmtree(root)
