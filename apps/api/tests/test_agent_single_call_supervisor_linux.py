"""Disposable CI: actual runner guards, private plans, three UIDs and paired IPC.

The trusted fixture substitutes SQL work and the HTTPS process, not the peers,
private PAT read or runner entries. No network is available. The journal path is
mapped to the invocation-owned /run fixture. This is not installed systemd or
independent recovery acceptance.
"""

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

import pytest

if not (
    sys.platform == "linux" and os.getuid() == 0
    and os.environ.get("GITHUB_ACTIONS") == "true"
    and os.environ.get("GITHUB_REPOSITORY") == "hulagerushikesh/cashlessiq"
    and os.environ.get("CIQ_AGENT_RECEIPT_PEER_TEST") == "1"
):
    pytest.skip("Launch sequence requires the explicit disposable CI job", allow_module_level=True)

from single_call_fixtures import response_bytes
from test_agent_single_call_peer_linux import peers as peers

from ciq_api import agent_single_call_supervisor as supervisor
from ciq_api.agent_provider_identity import IDENTITY, PLAN
from ciq_api.agent_provider_peer import ENDPOINT


@pytest.mark.parametrize("peers", ["assembly"], indirect=True)
@pytest.mark.parametrize("fault", [None, "provider-plan", "custody", "issue-ack"])
def test_original_three_runner_sequence_retains_uncertainty_and_stops_all(peers, fault):
    s = peers
    snapshot, config, pin, body = s.material
    provider_root = ENDPOINT.parents[1]
    custody_root = Path("/run/ciq-agent-custody")
    # Refuse existing paths; register only successful creations for teardown.
    roots, children = [], {}
    pin_digest = hashlib.sha256(pin.canonical().encode()).hexdigest()
    token = "DUMMY-NOT-A-CREDENTIAL-" + uuid4().hex
    reply = response_bytes(snapshot, pin.operation_id)

    def private(path, raw, uid):
        with path.open("xb") as stream:
            stream.write(raw)
        path.chmod(0o600)
        os.chown(path, uid, uid)

    class Host:
        def __init__(self):
            self.ids, self.output, self.started, self.stopped = {}, {}, [], []

        def check(self):
            return True  # Fixture authority only, never actual consent.

        def quiescent(self, role):
            child = children.get(role)
            if child is None:
                return True
            try:
                os.killpg(child.pid, 0)
            except ProcessLookupError:
                return child.poll() is not None
            return False

        def start(self, role):
            self.started.append(role)
            child = subprocess.Popen(
                (sys.executable, "-I", "-B", "-c", codes[role]), cwd="/",
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env={"LANG": "C.UTF-8"}, user={"receipt": 53003, "provider": 53004,
                                              "custody": 53002}[role],
                group={"receipt": 53003, "provider": 53004, "custody": 53002}[role],
                extra_groups=[], start_new_session=True,
            )
            children[role] = child
            self.ids[role] = uuid4().hex
            self.output[role] = [b"", b""]
            for stream in (child.stdout, child.stderr):
                os.set_blocking(stream.fileno(), False)
            return self.ids[role]

        def observe(self, role):
            child = children[role]
            code = child.poll()
            for index, stream in enumerate((child.stdout, child.stderr)):
                try:
                    raw = os.read(stream.fileno(), 129)
                except BlockingIOError:
                    raw = b""
                self.output[role][index] += raw
            return supervisor.Observation(self.ids[role], code is None, code,
                                          *self.output[role])

        def stop(self, role):
            self.stopped.append(role)
            child = children.get(role)
            if child is not None:
                with suppress(ProcessLookupError):
                    os.killpg(child.pid, signal.SIGKILL)
                child.communicate(timeout=3)
            return self.quiescent(role)

    prefix = "import os,sys\nsys.argv=['prepared-fixture-entry']\n"
    custody = prefix + f"""
from ciq_api import agent_single_call_runner as runner
from ciq_api.agent_contracts import AgentInput,AgentContext
from ciq_api.agent_one_shot import CapturedOneShotConfig
from ciq_api.agent_single_call_custody import PreparedSingleCallCustody
from ciq_api.agent_single_call_peer import SingleCallReceiptClient
from ciq_api.agent_provider_peer import ReviewedProviderPeerClient
def original(plan):
    assert {fault != 'custody'!r}, 'DUMMY SQL unavailable'
    snapshot=AgentInput.model_validate_json({snapshot.model_dump_json()!r})
    config=CapturedOneShotConfig.model_validate_json({config.model_dump_json()!r})
    current=AgentContext(binding=snapshot.binding,tenant_active=True,policy_approved=True,
                        clinical_authorized=True,review_open=True)
    attempt=PreparedSingleCallCustody(snapshot,current,config,plan.pin,
        SingleCallReceiptClient(plan.pin),ReviewedProviderPeerClient({pin_digest!r}))
    attempt.dispatch(current)
    assert attempt.take_candidate(current).candidate.run_id==plan.pin.operation_id
runner.run_once=original  # Explicit SQL substitution, no database in this fixture.
sys.exit(runner.main())
"""
    provider = prefix + f"""
import time
from ciq_api import agent_single_call_provider_runner as runner, agent_provider_identity as identity
from ciq_api.agent_https_process import decode_control
identity.PYTHON=sys.executable
def exchange(self, *, timeout):
    transport,body=decode_control(self._control)
    assert body=={body!r} and transport._token=={token!r}
    time.sleep(2.1)  # Longer than a receipt frame budget.
    return {reply!r}
identity.BoundedHTTPSProcess.exchange=exchange  # No HTTPS process/network.
sys.exit(runner.main())
"""
    receipt = prefix + f"""
from pathlib import Path
from ciq_api import agent_single_call_receipt_runner as runner, agent_single_call_peer as peer
runner.JOURNAL=Path({str(s.directory)!r})  # Invocation-owned retained fixture only.
if {fault == 'issue-ack'!r}:
    original=peer._send
    def lost(connection,marker,value,end):
        if marker==peer._RESPONSE:
            raise OSError('DUMMY lost issue ACK')
        return original(connection,marker,value,end)
    peer._send=lost
sys.exit(runner.main())
"""
    codes = {"receipt": receipt, "provider": provider, "custody": custody}
    host = Host()
    try:
        for root in (provider_root, custody_root):
            root.mkdir(mode=0o755)
            roots.append(root)
        ENDPOINT.parent.mkdir(mode=0o755)
        os.chown(ENDPOINT.parent, 53004, 53004)
        private(IDENTITY, token.encode(), 53004)
        private(PLAN, json.dumps({"protocol": "wrong" if fault == "provider-plan"
                                 else "ciq-private-provider-v2",
                                 "pin": json.loads(pin.canonical())}).encode(), 53004)
        private(s.directory.parents[1] / "receipt.json", json.dumps({
            "protocol": "ciq-single-call-receipt-v1", "pin": json.loads(pin.canonical()),
        }).encode(), 53003)
        private(custody_root / "single-call.json", json.dumps({
            "protocol": "ciq-single-call-custody-v1", "database": "dummy", "database_oid": 100,
            "login": "dummy_custody", "login_oid": 101, "password": "DUMMY-ONLY",
            "pin": json.loads(pin.canonical()),
        }).encode(), 53002)
        result = supervisor.SingleCallSupervisor(host).run()
        assert result.cleanup_confirmed, "owned launch cleanup unconfirmed"
        assert result.outcome == ("published" if fault is None else "unavailable"), (
            "fixed launch outcome mismatch: " + str(fault) + ": " + result.outcome
        )
        assert host.started == (["receipt", "provider"] if fault == "provider-plan"
                                else list(supervisor.ROLES))
        assert host.stopped == list(reversed(host.started))
        assert all(host.quiescent(role) for role in supervisor.ROLES)
        phase = "observed" if fault is None else "issued" if fault == "issue-ack" else "ready"
        s.run(f"assert SingleCallJournal(directory,pin).status().phase=={phase!r}\n"
              "os.write(1,b'PASS')", 53003)
    finally:
        for role in reversed(host.started):
            host.stop(role)
        for root in reversed(roots):
            shutil.rmtree(root)
