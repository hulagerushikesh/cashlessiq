"""Real helper CLIs on fresh CI-only volumes; not the full composition owner.

No caller DSN, local daemon opt-in, existing volume adoption or real credentials.
The dedicated disposable runner owns teardown, including failed test data.
"""

import json
import os
import re
import subprocess
import uuid
from hashlib import sha256
from pathlib import Path

import pytest

if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("CIQ_DATABASE_IMAGE_TEST") != "1":
    pytest.skip("Dedicated disposable CI image job required", allow_module_level=True)

from scripts.composition_database import DatabaseStaging, prepare
from scripts.composition_database_volume import request
from tests.test_composition_database import plan

LABEL = "ciq.disposable-image-test"
MATERIAL = "/database-material"
DATA = "/database-data"


def docker(*args, frame=None, timeout=10):
    # Never put private frames into argv, environment, files or failure messages.
    try:
        return subprocess.run(
            ["docker", *args],
            input=frame,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("CI Docker command timed out; runner teardown required")


def inspect(kind, identity):
    result = docker(kind, "inspect", identity)
    assert result.returncode == 0, "CI resource inspection failed"
    rows = json.loads(result.stdout)
    assert len(rows) == 1
    return rows[0]


class DatabaseImages:
    """Test-only owner on the fresh hosted runner, not a recovery/adoption API."""

    def __init__(self):
        self.token = uuid.uuid4().hex
        self.images = {}
        for role in ("cluster", "bootstrap"):
            image = (Path(os.environ["RUNNER_TEMP"]) / f"{role}-image-id").read_text().strip()
            assert re.fullmatch(r"sha256:[0-9a-f]{64}", image)
            assert inspect("image", image)["Id"] == image
            self.images[role] = image
        self.containers, self.volumes = [], []

    def volume(self, role):
        name = f"ciq-db-image-{self.token}-{role}"
        absent = docker("volume", "inspect", name)
        assert absent.returncode == 1 and b"no such volume" in absent.stderr.lower()
        created = docker("volume", "create", "--label", f"{LABEL}={self.token}", name)
        assert created.returncode == 0 and created.stdout.strip().decode() == name
        assert inspect("volume", name)["Labels"][LABEL] == self.token
        self.volumes.append(name)
        return name

    def run(
        self,
        image,
        module,
        mode,
        frame,
        mounts,
        *,
        root=False,
        expected="VERIFIED",
        code=0,
        program=None,
    ):
        name = f"ciq-db-image-{self.token}-{len(self.containers)}"
        user = "0:0" if root else "10002:10002"
        args = [
            "container",
            "create",
            "--interactive",
            "--name",
            name,
            "--label",
            f"{LABEL}={self.token}",
            "--network",
            "none",
            "--read-only",
            "--user",
            user,
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "128m",
            "--cpus",
            "0.5",
            "--pids-limit",
            "32",
            "--ipc",
            "private",
            "--restart",
            "no",
            "--entrypoint",
            "python",
        ]
        if root:
            args += ["--cap-add", "CHOWN"]
        for volume, destination, writable in mounts:
            mount = f"type=volume,src={volume},dst={destination},volume-nocopy"
            args += ["--mount", mount + ("" if writable else ",readonly")]
        args += [self.images[image]]
        args += ["-c", program] if program else ["-m", f"scripts.{module}", mode]
        created = docker(*args)
        assert created.returncode == 0, "CI helper creation failed; do not retry"
        cid = created.stdout.strip().decode()
        assert re.fullmatch("[0-9a-f]{64}", cid)
        self.containers.append(cid)
        before = inspect("container", cid)
        assert before["Id"] == cid and before["Image"] == self.images[image]
        assert before["Config"]["Labels"][LABEL] == self.token
        assert before["Config"]["User"] == user
        host = before["HostConfig"]
        assert host["ReadonlyRootfs"] and host["NetworkMode"] == "none"
        assert host["CapDrop"] == ["ALL"] and host["CapAdd"] == (["CHOWN"] if root else None)
        assert host["SecurityOpt"] == ["no-new-privileges"]
        assert (host["Memory"], host["NanoCpus"], host["PidsLimit"]) == (
            128 * 1024**2,
            500_000_000,
            32,
        )
        assert host["RestartPolicy"]["Name"] == "no" and host["IpcMode"] == "private"
        assert not host["Privileged"] and not host["PortBindings"]
        assert sorted((m["Name"], m["Destination"], m["RW"]) for m in before["Mounts"]) == (
            sorted(mounts)
        )
        result = docker(
            "container", "start", "--attach", "--interactive", cid, frame=frame, timeout=60
        )
        after = inspect("container", cid)
        assert after["Id"] == cid and after["Image"] == self.images[image]
        state = after["State"]
        assert not state["Running"] and not state["Paused"] and not state["OOMKilled"]
        assert state["Error"] == "" and state["ExitCode"] == result.returncode == code
        if code:
            assert result.stdout == b"" and b"denied" in result.stderr
        else:
            assert result.stderr == b""
            assert json.loads(result.stdout) == {
                "state": expected,
                "role": "database",
                "fingerprint": self.fingerprint,
            }

    def close(self):
        # Exact acknowledged IDs/names only. Never prune or touch other projects.
        for cid in reversed(self.containers):
            assert inspect("container", cid)["Config"]["Labels"][LABEL] == self.token
            assert docker("container", "rm", "--force", cid).returncode == 0
        for name in reversed(self.volumes):
            assert inspect("volume", name)["Labels"][LABEL] == self.token
            assert docker("volume", "rm", name).returncode == 0


@pytest.fixture
def database_images():
    owner = DatabaseImages()
    try:
        yield owner
    finally:
        owner.close()


ATTEMPTED_PROBE = """
import json, sys
from scripts import composition_database_bootstrap as bootstrap
from scripts import composition_database_cluster as cluster
from scripts import composition_volume as volume
from scripts.composition_database_volume import DatabaseVolume
spec, _ = volume.parse(sys.stdin.buffer.read(volume.MAX_FRAME + 1),
                       install=False, material_type=DatabaseVolume)
cluster.verify(cluster.DATA, cluster.MATERIAL, spec)
assert cluster.read_file(cluster.DATA / 'pgdata', bootstrap.MARKER, 4096,
                         (10002, 10002), 0o600) == cluster.record(spec, 'ATTEMPTED')
print(json.dumps(dict(state='ATTEMPTED', role='database', fingerprint=spec.fingerprint)))
"""


@pytest.mark.parametrize("fault", [None, "sql", "catalog"])
def test_real_initdb_bootstrap_probes_and_no_repeat(database_images, tmp_path, fault):
    owner = database_images
    bundle = prepare(plan())
    if fault == "sql":
        bundle.server["bootstrap.sql"] = b"BEGIN; INVALID SYNTAX; COMMIT;\n"
    elif fault == "catalog":
        bundle.server["bootstrap.sql"] += (
            b"GRANT TEMPORARY ON DATABASE synthetic TO membership_test;\n"
        )
    owner.fingerprint = sha256(owner.token.encode()).hexdigest()
    tmp_path.chmod(0o700)
    staged = DatabaseStaging.expected("database", owner.fingerprint, bundle.server).provision(
        tmp_path,
        bundle.server,
    )
    frame = request(staged, install=False)
    data_frame = json.dumps(
        {
            "version": 1,
            "role": "database",
            "fingerprint": owner.fingerprint,
        }
    ).encode()
    material, data = owner.volume("material"), owner.volume("data")
    material_ro, data_ro = (material, MATERIAL, False), (data, DATA, False)
    material_rw, data_rw = (material, MATERIAL, True), (data, DATA, True)
    owner.run(
        "cluster",
        "composition_database_volume",
        "install",
        request(staged, install=True),
        [material_rw],
        root=True,
        expected="INSTALLED",
    )
    owner.run("cluster", "composition_database_volume", "verify", frame, [material_ro])
    owner.run(
        "cluster",
        "composition_database_data",
        "prepare",
        data_frame,
        [data_rw],
        root=True,
        expected="PREPARED",
    )
    owner.run("cluster", "composition_database_data", "verify", data_frame, [data_ro])
    owner.run(
        "cluster",
        "composition_database_cluster",
        "initialize",
        frame,
        [material_ro, data_rw],
        expected="INITIALIZED",
    )
    owner.run("cluster", "composition_database_cluster", "verify", frame, [material_ro, data_ro])
    owner.run(
        "bootstrap",
        "composition_database_bootstrap",
        "bootstrap",
        frame,
        [material_ro, data_rw],
        expected="BOOTSTRAPPED",
        code=1 if fault else 0,
    )
    if fault:
        owner.run(
            "bootstrap",
            None,
            None,
            frame,
            [material_ro, data_ro],
            expected="ATTEMPTED",
            program=ATTEMPTED_PROBE,
        )
    owner.run(
        "bootstrap",
        "composition_database_bootstrap",
        "verify",
        frame,
        [material_ro, data_ro],
        code=1 if fault else 0,
    )
    # Fresh containers cannot initialize or bootstrap the same volumes twice.
    owner.run(
        "cluster",
        "composition_database_cluster",
        "initialize",
        frame,
        [material_ro, data_rw],
        code=1,
    )
    owner.run(
        "bootstrap",
        "composition_database_bootstrap",
        "bootstrap",
        frame,
        [material_ro, data_rw],
        code=1,
    )
    if fault:
        owner.run(
            "bootstrap",
            None,
            None,
            frame,
            [material_ro, data_ro],
            expected="ATTEMPTED",
            program=ATTEMPTED_PROBE,
        )
    else:
        owner.run(
            "bootstrap", "composition_database_bootstrap", "verify", frame, [material_ro, data_ro]
        )
