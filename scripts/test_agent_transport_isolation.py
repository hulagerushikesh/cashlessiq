"""Explicit disposable Docker test, CI only. Dummy identities; never a live adapter.

No local service activation, cloud call, real secret or source data. The image
contains just Python and the fake runtime. Only invocation-owned resources are
removed. Parent/child process limits are tested separately without Docker.
"""

import base64
import hashlib
import json
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from ciq_api.agent_contracts import capture_input
from ciq_api.agent_executor import FakeProcessRequest, decode_reply

ROOT = Path(__file__).resolve().parents[1]


def docker(*args, input=None, check=True, timeout=30):
    result = subprocess.run(
        ["docker", *args], cwd=ROOT, input=input, capture_output=True, timeout=timeout,
    )
    if check and result.returncode:
        raise RuntimeError("Disposable fake-transport Docker operation failed")
    return result


def interrupted(_signal, _frame):
    raise SystemExit("Interrupted; cleaning owned fake-transport resources")


def main():
    if (
        sys.platform != "linux"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
        or os.environ.get("CIQ_AGENT_TRANSPORT_TEST") != "1"
    ):
        raise SystemExit("Fake transport isolation requires the explicit disposable CI job")
    signal.signal(signal.SIGTERM, interrupted)
    prefix = "ciq-agent-transport-" + uuid4().hex[:12]
    image = prefix + ":fake"
    containers = []
    policy = json.loads(files("ciq_api").joinpath("fixtures/policy-template.json").read_text())
    snapshot = capture_input(
        tenant_id=uuid4(), request_id="REQ-FAKE-ISOLATION", policy_id=uuid4(),
        input_revision=0, review_version=0, correlation_id=uuid4(),
        facts=policy["examples"][0]["facts"], policy=policy,
    )
    packet = FakeProcessRequest(
        operation_id=uuid4(), attempt_id=uuid4(), submission_id=uuid4(),
        tenant_id=snapshot.binding.tenant_id, config_digest="a" * 64, source_digest="b" * 64,
        deadline=datetime.now(UTC) + timedelta(seconds=120), snapshot=snapshot,
    ).wire()
    try:
        docker("build", "-f", "apps/agent-transport/Dockerfile", "-t", image, ".", timeout=180)
        with TemporaryDirectory(prefix=prefix) as directory:
            root = Path(directory)
            packet = FakeProcessRequest.model_validate_json(packet).model_copy(update={
                "deadline": datetime.now(UTC) + timedelta(seconds=120),
            }).wire()
            fixture = root / "response.json"
            marker = root / "identity"
            marker.write_text("DUMMY-ONLY-no-real-credentials")
            marker.chmod(0o444)
            fixture.write_text(json.dumps({
                "request_sha256": hashlib.sha256(packet).hexdigest(),
                "candidate_base64": base64.b64encode(b'{"synthetic":"private"}').decode(),
            }))
            fixture.chmod(0o444)

            def create(role, *, probe=False):
                uid = "11001:11001" if role == "controller" else "11002:11002"
                own = "controller-db" if role == "controller" else "transport-identity"
                args = [
                    "create", "-i", "--name", f"{prefix}-{role}-{len(containers)}",
                    "--label", f"ciq.agent-transport-test={prefix}",
                    "--network", "none", "--read-only", "--cap-drop", "ALL",
                    "--security-opt", "no-new-privileges", "--user", uid,
                    "--memory", "64m", "--cpus", "0.25", "--pids-limit", "16",
                    "--ulimit", "nofile=64:64",
                    "--mount", f"type=bind,src={marker},dst=/run/ciq/{own},readonly",
                ]
                if role == "transport":
                    args += [
                        "--mount",
                        f"type=bind,src={fixture},dst=/run/ciq-fake/response.json,readonly",
                    ]
                if probe:
                    other = "transport-identity" if role == "controller" else "controller-db"
                    code = f"""
import importlib.util, os, pathlib, socket
assert os.getuid() == {uid.split(':')[0]}
assert pathlib.Path('/run/ciq/{own}').read_text().startswith('DUMMY-ONLY')
assert not pathlib.Path('/run/ciq/{other}').exists()
assert not set(os.environ) & {{'DATABASE_URL','SNOWFLAKE_TOKEN','GOOGLE_APPLICATION_CREDENTIALS'}}
for module in ('ciq_api', 'sqlalchemy', 'psycopg', 'snowflake'):
 assert importlib.util.find_spec(module) is None
for path in ('/var/run/docker.sock','/var/run/postgresql','.snowflake','/root/.config/gcloud'):
 assert not os.access(path, os.F_OK)
try:
 pathlib.Path('/opt/ciq/unauthorized').write_text('denied')
except OSError:
 pass
else:
 raise AssertionError('writable-image')
for address in (('127.0.0.1',5432),('1.1.1.1',443)):
 connection=socket.socket()
 connection.settimeout(0.2)
 assert connection.connect_ex(address) != 0
 connection.close()
print('PASS')
"""
                    args += ["--entrypoint", "python", image, "-I", "-c", code]
                else:
                    args += [image]
                identifier = docker(*args).stdout.decode().strip()
                containers.append(identifier)
                config = json.loads(docker("inspect", identifier).stdout)[0]
                host = config["HostConfig"]
                assert host["NetworkMode"] == "none" and not host["PortBindings"]
                assert not host["Privileged"]
                assert host["PidMode"] != "host" and host["IpcMode"] != "host"
                assert host["ReadonlyRootfs"] and host["CapDrop"] == ["ALL"]
                assert "no-new-privileges" in host["SecurityOpt"]
                assert host["Memory"] == 64 * 1024 * 1024 and host["PidsLimit"] == 16
                assert config["Config"]["User"] == uid
                assert all(not mount["RW"] for mount in config["Mounts"])
                assert {m["Destination"] for m in config["Mounts"]} == (
                    {f"/run/ciq/{own}", "/run/ciq-fake/response.json"}
                    if role == "transport" else {f"/run/ciq/{own}"}
                )
                return identifier

            for role in ("controller", "transport"):
                identifier = create(role, probe=True)
                result = docker("start", "-a", "-i", identifier, input=b"")
                assert result.stdout.strip() == b"PASS" and not result.stderr

            identifier = create("transport")
            result = docker("start", "-a", "-i", identifier, input=packet)
            assert decode_reply(result.stdout, packet) == b'{"synthetic":"private"}'
            assert not result.stderr

            # Fixed manifest/request pins reject payload changes and selectors;
            # the runtime emits one fixed error, never the clinical payload.
            for change in (
                {"tenant_id": str(uuid4())}, {"endpoint": "https://example.com"},
                {"credential": "DUMMY-ONLY"}, {"retry": True},
            ):
                altered = json.loads(packet)
                altered.update(change)
                identifier = create("transport")
                result = docker(
                    "start", "-a", "-i", identifier,
                    input=json.dumps(altered).encode(), check=False,
                )
                state = json.loads(docker("inspect", identifier).stdout)[0]["State"]
                assert state["ExitCode"] == 1 and not state["Running"] and not result.stdout
                assert result.stderr == b"fake_transport_unavailable\n"

            # Missing fixture fields are a closed failure, never a fallback.
            fixture.chmod(0o600)
            fixture.write_text("{}")
            fixture.chmod(0o444)
            identifier = create("transport")
            result = docker("start", "-a", "-i", identifier, input=packet, check=False)
            state = json.loads(docker("inspect", identifier).stdout)[0]["State"]
            assert state["ExitCode"] == 1 and not state["Running"] and not result.stdout
            assert result.stderr == b"fake_transport_unavailable\n"
        print("PASS: fake transport, distinct identities, no network/DB/SDK, fixed IPC denials")
    finally:
        failures = []
        for identifier in reversed(containers):
            if docker("rm", "-f", identifier, check=False).returncode:
                failures.append("container")
        if docker("image", "rm", image, check=False).returncode:
            failures.append("image")
        if failures:
            raise RuntimeError("Owned fake-transport cleanup incomplete")
        print("PASS: all invocation-owned fake-transport containers/image removed")


if __name__ == "__main__":
    main()
