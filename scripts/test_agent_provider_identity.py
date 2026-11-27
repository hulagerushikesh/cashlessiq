"""Disposable Linux CI only: real UID/DAC, dummy PAT, no network or activation."""

import grp
import hashlib
import json
import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path("/run/ciq-agent-provider")
RUNTIME = Path("/opt/ciq-agent-provider-review")
BODY = b'{"synthetic":"private provider identity test"}'
REPLY = b'{"synthetic":"private response"}'


def guard():
    if not (
        sys.platform == "linux" and os.geteuid() == 0
        and os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_REPOSITORY") == "hulagerushikesh/cashlessiq"
        and os.environ.get("CIQ_PROVIDER_IDENTITY_TEST") == "1"
    ):
        raise SystemExit("Provider identity acceptance requires explicit disposable Linux CI")
    for path in (PRIVATE, RUNTIME):
        if path.exists() or path.is_symlink():
            raise RuntimeError("Provider identity acceptance refuses an existing host object")
    for uid in (53002, 53004):
        for lookup in (pwd.getpwuid, grp.getgrgid):
            try:
                lookup(uid)
            except KeyError:
                pass
            else:
                raise RuntimeError("Provider identity acceptance refuses occupied numeric identity")


def main():
    guard()
    owned = []
    try:
        for path in (PRIVATE, RUNTIME):
            path.mkdir(mode=0o755)
            owned.append(path)
            path.chmod(0o755)
        package = RUNTIME / "ciq_api"
        package.mkdir(mode=0o755)
        (package / "__init__.py").touch(mode=0o644)
        for module in ("agent_private_file", "agent_https_transport", "agent_https_process",
                       "agent_https_worker", "agent_provider_identity"):
            destination = package / (module + ".py")
            shutil.copyfile(ROOT / "apps/api/src/ciq_api" / (module + ".py"), destination)
            destination.chmod(0o644)
        token = uuid4().hex.encode()
        digest = hashlib.sha256(token).hexdigest()
        plan = {"protocol": "ciq-private-provider-v1",
                "hostname": "reviewed-account.snowflakecomputing.com",
                "request_sha256": hashlib.sha256(BODY).hexdigest()}
        identity = PRIVATE / "identity.pat"
        plan_path = PRIVATE / "plan.json"
        clinical = PRIVATE / "clinical-password"

        def write(path, raw, *, uid=53004, mode=0o600):
            path.write_bytes(raw)
            os.chown(path, uid, uid)
            path.chmod(mode)

        write(plan_path, json.dumps(plan).encode())
        write(identity, token)
        write(clinical, b"DUMMY-private-clinical-password", uid=53002)
        # No token is present in code, argv, environment or output. This
        # synthetic hash is an in-memory positive-control verifier, not identity
        # authentication or a provider receipt. Never print it to CI logs.
        worker = f"""
import os, sys, hashlib
sys.path.insert(0, {str(RUNTIME)!r})
from ciq_api.agent_https_worker import main
from ciq_api.agent_https_transport import SinglePostHTTPS
def exchange(self, body, *, timeout):
    assert os.getresuid() == (53004,)*3 and os.getgroups() == []
    assert body == {BODY!r} and timeout == 10
    assert hashlib.sha256(self._token.encode()).hexdigest() == {digest!r}
    return {REPLY!r}
SinglePostHTTPS.exchange = exchange
os._exit(main())
"""
        provider = f"""
import os, sys, resource
sys.path.insert(0, {str(RUNTIME)!r})
from pathlib import Path
from ciq_api import agent_provider_identity as identity
from ciq_api import agent_https_process as process
resource.setrlimit(resource.RLIMIT_CORE, (0,0))
try:
    Path({str(clinical)!r}).read_bytes()
except PermissionError:
    pass
else:
    os._exit(1)
real_popen = process.subprocess.Popen
attempts = []
identity.PYTHON = sys.executable
def spawn(argv, **kwargs):
    assert argv == (sys.executable, '-I', '-B', '-m', 'ciq_api.agent_https_worker')
    attempts.append(True)
    return real_popen((sys.executable, '-I', '-B', '-c', {worker!r}), **kwargs)
process.subprocess.Popen = spawn
attempt = identity.PrivateProviderAttempt()
try:
    response = attempt.exchange({BODY!r}, timeout=2)
    valid = response == {REPLY!r} and len(attempts) == 1
except ValueError as error:
    valid = str(error) == identity.ERROR and not attempts
    response = None
try:
    attempt.exchange({BODY!r}, timeout=2)
except ValueError as error:
    valid = valid and str(error) == identity.ERROR
else:
    valid = False
if valid:
    os.write(1, b'OK' if response is not None else b'DENIED')
os._exit(0 if valid else 1)
"""
        custody = f"""
import os, sys, resource
sys.path.insert(0, {str(RUNTIME)!r})
from pathlib import Path
from ciq_api.agent_provider_identity import PrivateProviderAttempt, ERROR
resource.setrlimit(resource.RLIMIT_CORE, (0,0))
assert Path({str(clinical)!r}).read_bytes() == b'DUMMY-private-clinical-password'
for path in ({str(identity)!r}, {str(plan_path)!r}):
    try:
        Path(path).read_bytes()
    except PermissionError:
        pass
    else:
        os._exit(1)
try:
    PrivateProviderAttempt().exchange({BODY!r}, timeout=2)
except ValueError as error:
    if str(error) == ERROR:
        os.write(1, b'DENIED')
        os._exit(0)
os._exit(1)
"""

        def check(code, uid, expected, *, groups=(), extra_env=None):
            result = subprocess.run(
                (sys.executable, "-I", "-B", "-c", code),
                stdin=subprocess.DEVNULL, capture_output=True, cwd="/",
                env={"LANG": "C.UTF-8"} | (extra_env or {}),
                user=uid, group=uid, extra_groups=groups, timeout=6,
            )
            if result.returncode or result.stdout != expected or result.stderr:
                raise RuntimeError("Provider identity acceptance failed; private output suppressed")

        check(provider, 53004, b"OK")
        check(custody, 53002, b"DENIED")
        check(provider, 53004, b"DENIED", groups=(53002,))
        check(provider, 53004, b"DENIED", extra_env={"DATABASE_URL": "DUMMY-PRIVATE"})
        # Wrong ownership and unsafe/special files never become a fallback
        # credential source. No rejection is permission to retry this attempt.
        for mode in (0o644, 0o400, 0o660):
            identity.chmod(mode)
            check(provider, 53004, b"DENIED")
        identity.chmod(0o600)
        os.chown(identity, 53002, 53002)
        check(provider, 53004, b"DENIED")
        identity.unlink()
        check(provider, 53004, b"DENIED")
        identity.symlink_to(clinical)
        check(provider, 53004, b"DENIED")
        identity.unlink()
        write(identity, token)
        link = PRIVATE / "identity-link"
        os.link(identity, link)
        check(provider, 53004, b"DENIED")
        link.unlink()
        identity.unlink()
        os.mkfifo(identity, mode=0o600)
        os.chown(identity, 53004, 53004)
        check(provider, 53004, b"DENIED")
        identity.unlink()
        for invalid in (b"", b"x" * 8193, b"\xff", b"DUMMY\nheader"):
            write(identity, invalid)
            check(provider, 53004, b"DENIED")
        write(identity, token)
        plan_path.chmod(0o644)
        check(provider, 53004, b"DENIED")
        plan_path.chmod(0o600)
        write(plan_path, json.dumps(plan).encode()[:-1] + b',"hostname":"localhost"}')
        check(provider, 53004, b"DENIED")
        write(plan_path, json.dumps(plan | {"request_sha256": "a" * 64}).encode())
        check(provider, 53004, b"DENIED")
        write(plan_path, json.dumps(plan).encode())
        check(provider, 53004, b"OK")
        print("PASS: 20 provider-identity controls; distinct UIDs, private files, no network")
    finally:
        for path in reversed(owned):
            shutil.rmtree(path)
        print("PASS: owned provider-identity fixture paths removed; no accounts/services created")


if __name__ == "__main__":
    main()
