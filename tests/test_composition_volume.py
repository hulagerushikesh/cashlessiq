"""Real disposable local directories, host UID/GID only; no Docker mount claims."""

import base64
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import composition_volume as target
from scripts.composition_material import ROLES, Material, MaterialDenied, _archive, names


@pytest.fixture
def bundle(tmp_path):
    parent = tmp_path / "staging"
    parent.mkdir(mode=0o700)

    def build(role="broker"):
        contents = {name: ("fictional-private-" + name).encode() for name in names(role)}
        return Material.expected(role, "a" * 64, contents).provision(parent, contents)

    return build


@pytest.fixture
def destination(tmp_path):
    path = tmp_path / "destination"
    path.mkdir(mode=0o700)
    yield path
    # Only this fixture's exact disposable root; no product resources involved.
    path.chmod(0o700)


def installed(bundle, destination):
    staged = bundle()
    spec, archive = target.parse(target.request(staged, install=True), install=True)
    owner = os.getuid(), os.getgid()
    target.install(destination, spec, archive, owner=owner)
    return spec, owner


@pytest.mark.parametrize("role", ROLES)
def test_all_role_archives_install_and_verify_without_overwrite(bundle, destination, role, capsys):
    staged = bundle(role)
    spec, archive = target.parse(target.request(staged, install=True), install=True)
    owner = os.getuid(), os.getgid()  # Not UID-10001 or a Linux/Docker acceptance claim.
    target.install(destination, spec, archive, owner=owner)
    assert target.verify(destination, spec, owner=owner)
    verify_spec, absent = target.parse(target.request(staged, install=False), install=False)
    assert absent is None and verify_spec == spec
    assert target.verify(destination, verify_spec, owner=owner)
    before = {p.name: p.read_bytes() for p in destination.iterdir()}
    with pytest.raises(MaterialDenied):
        target.install(destination, spec, archive, owner=owner)
    assert before == {p.name: p.read_bytes() for p in destination.iterdir()}
    assert capsys.readouterr() == ("", "")


def edited_archive(payload, change):
    output = io.BytesIO()
    with (
        tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as original,
        tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as result,
    ):
        for entry in original.getmembers():
            data = original.extractfile(entry).read() if entry.isfile() else None
            change(entry)
            result.addfile(entry, io.BytesIO(data) if data is not None else None)
    return output.getvalue()


@pytest.mark.parametrize(
    "fault",
    [
        "parent",
        "absolute",
        "symlink",
        "hardlink",
        "fifo",
        "mode",
        "uid",
        "gid",
        "mtime",
        "extra",
        "missing",
        "duplicate",
        "digest",
        "trailing",
        "pax",
        "gzip",
    ],
)
def test_archive_is_fully_validated_before_any_directory_mutation(bundle, destination, fault):
    staged = bundle()
    spec, archive = target.parse(target.request(staged, install=True), install=True)

    def change(entry):
        if entry.name != "identity.key":
            return
        if fault in {"parent", "absolute"}:
            entry.name = "../escape" if fault == "parent" else "/escape"
        elif fault in {"symlink", "hardlink", "fifo"}:
            entry.type = {
                "symlink": tarfile.SYMTYPE,
                "hardlink": tarfile.LNKTYPE,
                "fifo": tarfile.FIFOTYPE,
            }[fault]
            entry.linkname = "config.json"
        elif fault in {"mode", "uid", "gid", "mtime"}:
            setattr(entry, fault, {"mode": 0o444, "uid": 0, "gid": 0, "mtime": 1}[fault])

    if fault in {"extra", "missing", "duplicate", "digest", "pax", "gzip"}:
        snapshot = target.unpack(spec, archive)
        if fault == "extra":
            snapshot["db.json"] = b"foreign-secret"
        elif fault == "missing":
            del snapshot["ca.pem"]
        elif fault == "digest":
            snapshot["identity.key"] = b"bad-key"
        archive = _archive(snapshot)
        if fault == "duplicate":
            # Insert a second directory record ahead of the first file record.
            archive = archive[:512] + archive
        elif fault == "pax":
            output = io.BytesIO()
            with tarfile.open(
                fileobj=output,
                mode="w",
                format=tarfile.PAX_FORMAT,
                pax_headers={"comment": "untrusted"},
            ) as result:
                result.addfile(tarfile.TarInfo("."))
            archive = output.getvalue()
        elif fault == "gzip":
            import gzip

            archive = gzip.compress(archive)
    elif fault == "trailing":
        archive += b"hidden-trailing-archive"
    else:
        archive = edited_archive(archive, change)
    original_mode = destination.stat().st_mode
    with pytest.raises(MaterialDenied):
        target.install(destination, spec, archive, owner=(os.getuid(), os.getgid()))
    assert list(destination.iterdir()) == [] and destination.stat().st_mode == original_mode


@pytest.mark.parametrize(
    "fault",
    [
        "extra",
        "missing",
        "content",
        "file-mode",
        "root-mode",
        "owner",
        "link",
        "fifo",
    ],
)
def test_readback_denies_changed_volume_without_repair(bundle, destination, fault):
    spec, owner = installed(bundle, destination)
    destination.chmod(0o700)
    path = destination / "identity.key"
    if fault == "extra":
        (destination / "unexpected.pem").touch(mode=0o400)
    elif fault == "missing":
        path.unlink()
    elif fault == "content":
        path.chmod(0o600)
        path.write_bytes(b"x" * path.stat().st_size)
        path.chmod(0o400)
    elif fault == "file-mode":
        path.chmod(0o444)
    elif fault == "owner":
        owner = (owner[0] + 1, owner[1])  # No host ownership changes needed.
    elif fault == "link":
        path.unlink()
        path.symlink_to(destination / "identity.pem")
    elif fault == "fifo":
        path.unlink()
        os.mkfifo(path, 0o400)
    destination.chmod(0o700 if fault == "root-mode" else 0o500)
    with pytest.raises(MaterialDenied):
        target.verify(destination, spec, owner=owner)


@pytest.mark.parametrize(
    "fault",
    [
        "extra",
        "duplicate",
        "bool-size",
        "oversize",
        "bad-digest",
        "duplicate-record",
        "foreign-role",
        "bool-version",
        "missing-archive",
        "bad-base64",
        "frame-limit",
    ],
)
def test_private_input_frame_is_closed_and_bounded(bundle, fault):
    staged = bundle()
    frame = target.request(staged, install=True)
    raw = json.loads(frame)
    if fault == "extra":
        raw["root"] = "/caller-selected"
    elif fault == "bool-size":
        raw["records"][0][1] = True
    elif fault == "oversize":
        raw["records"][0][1] = 262145
    elif fault == "bad-digest":
        raw["records"][0][2] = "z" * 64
    elif fault == "duplicate-record":
        raw["records"][1] = raw["records"][0]
    elif fault == "foreign-role":
        raw["role"] = "controller"
    elif fault == "bool-version":
        raw["version"] = True
    elif fault == "missing-archive":
        del raw["archive"]
    elif fault == "bad-base64":
        raw["archive"] = "***"
    frame = json.dumps(raw).encode()
    if fault == "duplicate":
        frame = b'{"version":1,' + frame[1:]
    elif fault == "frame-limit":
        frame = b"x" * (target.MAX_FRAME + 1)
    with pytest.raises(MaterialDenied):
        target.parse(frame, install=True)


def test_partial_write_failure_retains_state_and_never_retries(bundle, destination, monkeypatch):
    staged = bundle()
    spec, archive = target.parse(target.request(staged, install=True), install=True)
    owner = os.getuid(), os.getgid()
    write = Mock(side_effect=OSError("fictional-private-driver-failure"))
    monkeypatch.setattr(os, "write", write)
    with pytest.raises(MaterialDenied):
        target.install(destination, spec, archive, owner=owner)
    assert len(list(destination.iterdir())) == 1
    assert destination.stat().st_mode & 0o777 == 0o700
    with pytest.raises(MaterialDenied):
        target.install(destination, spec, archive, owner=owner)
    assert write.call_count == 1


def test_cli_has_no_default_action_and_redacts_failed_input():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "scripts.composition_volume"],
        cwd=root,
        env={},
        input=b"fictional-private-payload",
        capture_output=True,
        timeout=3,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert result.stderr == b"Disposable material operation denied; outcome unknown\n"


def test_read_only_request_contains_no_archive_or_private_bytes(bundle):
    staged = bundle()
    raw = json.loads(target.request(staged, install=False))
    assert "archive" not in raw
    assert "fictional-private" not in json.dumps(raw)
    spec, archive = target.parse(json.dumps(raw).encode(), install=False)
    assert spec == staged.expected and archive is None
    assert base64.b64encode(b"fictional-private") not in json.dumps(raw).encode()


@pytest.mark.parametrize("action", ["install", "verify"])
def test_cli_fixes_path_identity_and_emits_only_bound_metadata(bundle, monkeypatch, capsys, action):
    from types import SimpleNamespace

    staged = bundle()
    frame = target.request(staged, install=action == "install")
    operation = Mock()
    monkeypatch.setattr(target, action, operation)
    monkeypatch.setattr(sys, "argv", ["helper", action])
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(frame)))
    monkeypatch.setattr(os, "geteuid", lambda: 0 if action == "install" else 10001)
    assert target.main() == 0
    arguments = operation.call_args
    assert arguments.args[0] == Path("/material")
    assert arguments.kwargs == {"owner": (10001, 10001)}
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out) == {
        "state": "INSTALLED" if action == "install" else "VERIFIED",
        "role": "broker",
        "fingerprint": "a" * 64,
    }


@pytest.mark.parametrize("action", ["install", "verify"])
def test_cli_wrong_uid_never_runs_operation(monkeypatch, capsys, action):
    operation = Mock()
    monkeypatch.setattr(target, action, operation)
    monkeypatch.setattr(sys, "argv", ["helper", action])
    monkeypatch.setattr(os, "geteuid", lambda: 10001 if action == "install" else 0)
    assert target.main() == 1
    operation.assert_not_called()
    assert capsys.readouterr().out == ""
