"""Disposable CI only: irreversible identity loss, descriptor and exec checks."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

if not (
    sys.platform == "linux" and os.getuid() == 0
    and os.environ.get("GITHUB_ACTIONS") == "true"
    and os.environ.get("GITHUB_REPOSITORY") == "hulagerushikesh/cashlessiq"
    and os.environ.get("CIQ_AGENT_RECEIPT_PEER_TEST") == "1"
):
    pytest.skip("Identity transition requires explicit disposable CI", allow_module_level=True)

from ciq_api.agent_single_call_identity import ERROR, PYTHON, TARGETS


@pytest.mark.parametrize("role", ["receipt", "provider", "custody"])
def test_real_transition_clears_groups_descriptors_and_cannot_regain_privilege(role):
    root = Path("/run/ciq-identity-" + uuid4().hex)
    root.mkdir(mode=0o755)
    try:
        for owner in (0, 53002, 53003, 53004):
            path = root / str(owner)
            path.write_bytes(b"DUMMY-PRIVATE-" + str(owner).encode())
            path.chmod(0o600)
            os.chown(path, owner, owner)
        with (root / "0").open("rb") as secret:
            code = f"""
import errno,os,resource,sys
from pathlib import Path
from ciq_api.agent_single_call_identity import prepare_identity
prepare_identity({role!r})
from ciq_api.agent_claim_runner import guard_process
from ciq_api.agent_single_call_peer import _guard
guard_process()
_guard({TARGETS[role][0]})
assert os.getcwd()=='/' and resource.getrlimit(resource.RLIMIT_NOFILE)==(64,64)
try:
    os.fstat({secret.fileno()})
except OSError as error:
    assert error.errno==errno.EBADF
else:
    raise AssertionError('inherited credential descriptor survived')
for action in (lambda:os.setresuid(0,0,0),lambda:os.setresgid(0,0,0),
               lambda:os.setgroups([0])):
    try:
        action()
    except PermissionError:
        pass
    else:
        raise AssertionError('root identity regained')
for owner in (0,53002,53003,53004):
    try:
        data=(Path({str(root)!r})/str(owner)).read_bytes()
    except PermissionError:
        assert owner!={TARGETS[role][0]}
    else:
        assert owner=={TARGETS[role][0]} and data==b'DUMMY-PRIVATE-'+str(owner).encode()
os.write(1,b'PASS')
"""
            result = subprocess.run(
                (sys.executable, "-I", "-B", "-c", code), cwd="/",
                env={"LANG": "C.UTF-8"}, stdin=subprocess.DEVNULL,
                capture_output=True, timeout=5,
                extra_groups=[0, 777], pass_fds=(secret.fileno(),),
            )
        assert result.returncode == 0 and result.stdout == b"PASS" and not result.stderr, (
            "fixed identity transition acceptance failed"
        )
    finally:
        shutil.rmtree(root)


@pytest.mark.parametrize("role", ["receipt", "provider", "custody"])
def test_actual_fixed_exec_enters_selected_runner_and_denies_missing_plan(role):
    # The image has only a public fixed-path interpreter link. No private plans,
    # SQL, journal, provider credential or egress is prepared for this check.
    result = subprocess.run(
        (PYTHON, "-I", "-B", "-m", "ciq_api.agent_single_call_identity", role), cwd="/",
        env={"LANG": "C.UTF-8"}, stdin=subprocess.DEVNULL,
        capture_output=True, timeout=5, extra_groups=[0, 777],
    )
    assert result.returncode == 1 and result.stdout == b""
    assert result.stderr == f"single_call_{role}_unavailable\n".encode(), (
        "fixed runner exec denial failed"
    )


@pytest.mark.parametrize("args,extra_env", [
    ([], {}), (["custody", "--retry"], {}), (["root"], {}),
    (["provider"], {"PGPASSWORD": "DUMMY-MUST-NOT-BE-USED"}),
])
def test_actual_launcher_denies_extra_authority_and_configuration(args, extra_env):
    result = subprocess.run(
        (PYTHON, "-I", "-B", "-m", "ciq_api.agent_single_call_identity", *args), cwd="/",
        env={"LANG": "C.UTF-8"} | extra_env, stdin=subprocess.DEVNULL,
        capture_output=True, timeout=5, extra_groups=[0, 777],
    )
    assert result.returncode == 1 and result.stdout == b"" and result.stderr == ERROR
