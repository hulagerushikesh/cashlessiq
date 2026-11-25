"""Host-mutation refusal, artifact integrity and private diagnostic contracts."""

import json
import socket
import stat
import struct
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from scripts import test_agent_service_packages as runner


def absent(_name):
    raise KeyError


def test_runtime_inputs_copy_committed_bytes_and_refuse_existing_directory(tmp_path, monkeypatch):
    metadata = json.dumps({runner.PYTHON_KEY: {"sha256": "reviewed digest"}}).encode()
    pins = {"deploy/agent-controller/python-downloads.json": metadata,
            "deploy/agent-controller/build-requirements.txt": b"reviewed build pins\n"}
    revisions = []

    def committed(revision):
        revisions.append(revision)
        return pins

    monkeypatch.setattr(runner.dependencies.review, "committed_files", committed)
    inputs = runner.runtime_inputs(tmp_path, "a" * 40)
    assert revisions == ["a" * 40]
    assert {p.name: p.read_bytes() for p in inputs.iterdir()} == {
        name.rsplit("/", 1)[1]: data for name, data in pins.items()}
    with pytest.raises(FileExistsError):
        runner.runtime_inputs(tmp_path, "a" * 40)
    assert (inputs / "python-downloads.json").read_bytes() == metadata


@pytest.mark.parametrize("metadata", [
    {}, {"cpython-3.12.0-linux-x86_64-gnu": {}},
    {runner.PYTHON_KEY: {}, "cpython-3.11.15-linux-aarch64-gnu": {}},
])
def test_interpreter_alternatives_refuse_before_staging(tmp_path, monkeypatch, metadata):
    monkeypatch.setattr(runner.dependencies.review, "committed_files", lambda _: {
        "deploy/agent-controller/python-downloads.json": json.dumps(metadata).encode()})
    with pytest.raises(ValueError, match="one pinned private interpreter"):
        runner.runtime_inputs(tmp_path, "a" * 40)
    assert not list(tmp_path.iterdir())


def test_pinned_interpreter_metadata_is_accepted_by_uv_without_installing():
    # Actual uv parsing, no download, extraction, interpreter or host mutation.
    path = Path(__file__).resolve().parents[1] / "deploy/agent-controller/python-downloads.json"
    result = runner.policy.run("uv", "python", "list", runner.PYTHON_KEY,
                               "--all-platforms", "--all-arches", "--only-downloads",
                               "--offline", "--no-config", "--output-format", "json",
                               "--python-downloads-json-url", path.as_uri())
    entries = json.loads(result.stdout)
    assert len(entries) == 1 and entries[0]["key"] == runner.PYTHON_KEY
    assert entries[0]["path"] is None and entries[0]["version"] == "3.11.15"


def test_package_optin_precedes_all_host_access(monkeypatch):
    monkeypatch.delenv("CIQ_AGENT_PACKAGE_TEST", raising=False)
    monkeypatch.setattr(runner.policy, "guard", lambda: pytest.fail("Host accessed"))
    with pytest.raises(SystemExit, match="explicit disposable CI"):
        runner.main()


@pytest.mark.parametrize("fault", ["directory", "symlink", "user", "group"])
def test_existing_install_or_identity_is_preserved_before_mutation(monkeypatch, tmp_path, fault):
    monkeypatch.setenv("CIQ_AGENT_PACKAGE_TEST", "1")
    monkeypatch.setattr(runner.policy, "guard", lambda: None)
    install = tmp_path / "install"
    monkeypatch.setattr(runner, "INSTALL", install)
    if fault == "directory":
        install.mkdir()
        (install / "owner").write_bytes(b"owner")
    elif fault == "symlink":
        install.symlink_to(tmp_path / "missing-owner-path")
    monkeypatch.setattr(runner.pwd, "getpwnam",
                        (lambda _: SimpleNamespace()) if fault == "user" else absent)
    monkeypatch.setattr(runner.policy.grp, "getgrnam",
                        (lambda _: SimpleNamespace()) if fault == "group" else absent)
    monkeypatch.setattr(runner, "install", lambda _: pytest.fail("Installation attempted"))
    with pytest.raises(SystemExit, match="Refusing existing"):
        runner.main()
    if fault == "directory":
        assert (install / "owner").read_bytes() == b"owner"
    elif fault == "symlink":
        assert install.is_symlink()


@pytest.mark.parametrize("fault", [None, "changed", "extra", "missing"])
def test_wheel_bytes_and_complete_package_inventory(tmp_path, fault):
    source = tmp_path / "source"
    source.mkdir()
    (source / "runner.py").write_bytes(b"exact code")
    (source / "fixture.json").write_bytes(b"{}")
    wheel = tmp_path / "dummy.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr("dummy/runner.py", b"rewritten" if fault == "changed" else b"exact code")
        if fault != "missing":
            archive.writestr("dummy/fixture.json", b"{}")
        if fault == "extra":
            archive.writestr("dummy/authority.py", b"extra code")
        archive.writestr("dummy-0.1.dist-info/METADATA", b"metadata")
    if fault:
        with pytest.raises(ValueError, match="package"):
            runner.verify_wheel(wheel, "dummy", source)
    else:
        runner.verify_wheel(wheel, "dummy", source)


@pytest.mark.parametrize("count,payload", [(0, b""), (-1, b""), (8193, b""), (5, b"short"[:2])])
def test_dummy_authentication_frames_are_bounded_and_fail_on_truncation(count, payload):
    reader, writer = socket.socketpair()
    try:
        reader.settimeout(0.5)
        writer.sendall(payload)
        writer.shutdown(socket.SHUT_WR)
        with pytest.raises(ValueError, match="Dummy authentication frame"):
            runner.receive(reader, count)
    finally:
        reader.close()
        writer.close()


@pytest.mark.parametrize("fault", [None, "protocol", "identity", "password", "oversize"])
def test_dummy_sink_accepts_only_expected_startup_and_password_without_retaining_secret(fault):
    # A socketpair exercises the trusted fixture protocol without a local listener.
    reader, writer = socket.socketpair()
    sink = runner.PasswordSink.__new__(runner.PasswordSink)
    sink.password = b"PRIVATE-DUMMY\0"
    sink.results = []
    sink.stopped = runner.threading.Event()

    class Listener:
        def accept(self):
            sink.stopped.set()  # Exactly one controlled socketpair.
            return reader, None

    sink.listener = Listener()
    startup = struct.pack("!I", 123 if fault == "protocol" else 196608)
    startup += (b"user\0other\0" if fault == "identity" else b"user\0ciq_dummy_login\0")
    startup += b"database\0ciq_dummy_database\0\0"
    writer.sendall(struct.pack("!I", 99999 if fault == "oversize" else len(startup) + 4)
                   + startup)
    password = b"WRONG\0" if fault == "password" else sink.password
    writer.sendall(b"p" + struct.pack("!I", len(password) + 4) + password)
    writer.shutdown(socket.SHUT_WR)
    try:
        sink.serve()
        assert sink.results == [fault is None]
        # Only fixed booleans are retained; password/packets/exception text are not.
        if fault is None:
            assert writer.recv(9) == b"R" + struct.pack("!II", 8, 3)
            error = writer.recv(256)
            assert b"PRIVATE" not in error and b"28P01" in error
    finally:
        reader.close()
        writer.close()


def test_unexpected_private_journal_message_never_appears_in_diagnostics(monkeypatch, capsys):
    values = {"ActiveState": "failed", "InvocationID": "a" * 32, "NRestarts": "0",
              "Result": "exit-code", "ExecMainStatus": "1"}
    monkeypatch.setattr(runner.policy, "value", lambda _unit, name: values[name])
    monkeypatch.setattr(runner.policy, "run", lambda *_: None)
    monkeypatch.setattr(runner.policy, "empty", lambda _: True)
    monkeypatch.setattr(runner, "logs", lambda _: ["PRIVATE-DUMMY-PASSWORD"])
    with pytest.raises(RuntimeError, match="fixed private contract") as result:
        runner.execute("owned", "claim")
    assert "PRIVATE" not in str(result.value) and capsys.readouterr() == ("", "")


def test_invocation_logs_are_scoped_and_not_printed(monkeypatch, capsys):
    calls = []

    def run(*args):
        calls.append(args)
        return SimpleNamespace(stdout=json.dumps({"MESSAGE": "PRIVATE"}) + "\n")

    monkeypatch.setattr(runner.policy, "run", run)
    assert runner.logs("a" * 32) == ["PRIVATE"]
    assert calls[1][1:3] == ("_SYSTEMD_INVOCATION_ID=" + "a" * 32, "_TRANSPORT=stdout")
    assert calls[1][-1] == "--lines=8" and capsys.readouterr() == ("", "")
    with pytest.raises(ValueError, match="invocation identity"):
        runner.logs("unscoped")


def test_only_owned_install_files_are_hardened_without_following_external_symlinks(tmp_path):
    root = tmp_path / "install"
    root.mkdir(mode=0o775)
    library = root / "library.py"
    library.write_bytes(b"exact trusted code")
    library.chmod(0o664)
    (root / "alias.py").symlink_to(library)
    runner.harden_installation(root)
    assert stat.S_IMODE(root.stat().st_mode) == 0o755
    assert stat.S_IMODE(library.stat().st_mode) == 0o644
    assert library.read_bytes() == b"exact trusted code"
    outside = tmp_path / "foreign.py"
    outside.write_bytes(b"owner bytes")
    outside.chmod(0o664)
    (root / "escape.py").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink escapes"):
        runner.harden_installation(root)
    assert outside.read_bytes() == b"owner bytes"
    assert stat.S_IMODE(outside.stat().st_mode) == 0o664


def test_installation_hardening_rejects_nonregular_files_without_opening_them(tmp_path):
    root = tmp_path / "install"
    root.mkdir()
    runner.os.mkfifo(root / "fifo")
    with pytest.raises(ValueError, match="file kind"):
        runner.harden_installation(root)
