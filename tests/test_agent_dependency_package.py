"""Locked dependency selection, offline integrity and incomplete download behavior."""

import copy
import io
import json
import subprocess
import tomllib
from pathlib import Path

import pytest

from scripts import package_agent_dependencies as package


def wheel(name, data=b"locked wheel", tag="py3-none-any"):
    return {"url": f"https://files.pythonhosted.org/packages/{name}-1.0-{tag}.whl",
            "size": len(data), "hash": "sha256:" + package.review.sha256(data)}


@pytest.fixture
def lock():
    return {"requires-python": "==3.11.*", "package": [
        {"name": "cashlessiq-api", "source": {"editable": "."}, "dependencies": [
            {"name": "cashlessiq-domain"}, {"name": "driver", "extra": ["binary"]}],
         "optional-dependencies": {"snowflake": [{"name": "provider"}]},
         "dev-dependencies": {"dev": [{"name": "pytest"}]}},
        {"name": "cashlessiq-domain", "source": {"directory": "../../packages/domain"}},
        {"name": "driver", "version": "1.0", "source": {"registry": "https://pypi.org/simple"},
         "dependencies": [{"name": "windows", "marker": "sys_platform == 'win32'"}],
         "optional-dependencies": {"binary": [{"name": "native"}]},
         "wheels": [wheel("driver")]},
        {"name": "native", "version": "1.0", "source": {"registry": "https://pypi.org/simple"},
         "dependencies": [{"name": "driver"}],  # A base dependency cycle is finite.
         "wheels": [wheel("native", tag="cp311-cp311-manylinux_2_17_x86_64")]},
    ]}


def test_runtime_closure_selects_requested_extras_not_dev_provider_or_windows(lock):
    selected = package.selected_wheels(lock)
    assert {w["name"] for w in selected.values()} == {"driver", "native"}
    changed = copy.deepcopy(lock)
    changed["package"].reverse()
    assert package.selected_wheels(changed) == selected


@pytest.mark.parametrize("tag,accepted", [
    ("py2.py3-none-any", True), ("cp311-cp311-manylinux_2_36_x86_64", True),
    ("cp39-abi3-manylinux2014_x86_64", True), ("cp312-abi3-manylinux2014_x86_64", False),
    ("cp310-cp310-manylinux2014_x86_64", False), ("cp311-cp311-manylinux_2_37_x86_64", False),
    ("cp311-cp311-manylinux_2_17_aarch64", False), ("cp311-cp311-musllinux_1_2_x86_64", False),
    ("cp311-cp311-linux_x86_64", False), ("cp311-cp311-win_amd64", False),
    ("py3-none-macosx_11_0_arm64", False), ("cp311-cp311-any", False),
])
def test_target_compatibility_is_narrow(tag, accepted):
    assert package.compatible(f"demo-1.0-{tag}.whl") is accepted
    assert not package.compatible("../demo-1.0-py3-none-any.whl")


@pytest.mark.parametrize("fault", [
    "marker", "source", "extra", "hash", "url", "size", "duplicate", "missing", "target",
])
def test_unsupported_lock_changes_refuse_before_download(lock, fault, monkeypatch):
    driver = lock["package"][2]
    if fault == "marker":
        driver["dependencies"][0]["marker"] = "unknown == 'value'"
    elif fault == "source":
        driver["source"] = {"git": "https://example.invalid/code"}
    elif fault == "extra":
        lock["package"][0]["dependencies"][1]["extra"] = ["unknown"]
    elif fault == "hash":
        driver["wheels"][0]["hash"] = "sha256:bad"
    elif fault == "url":
        driver["wheels"][0]["url"] = "https://example.invalid/demo-1.0-py3-none-any.whl"
    elif fault == "size":
        driver["wheels"][0]["size"] = package.MAX_WHEEL + 1
    elif fault == "duplicate":
        lock["package"].append(driver)
    elif fault == "missing":
        driver["wheels"] = []
    else:
        lock["requires-python"] = ">=3.11"
    monkeypatch.setattr(package, "urlopen", lambda *_a, **_k: pytest.fail("Network contacted"))
    with pytest.raises((ValueError, KeyError)):
        package.selected_wheels(lock)


@pytest.fixture
def bundle(tmp_path, monkeypatch, lock):
    wheels = package.selected_wheels(lock)
    metadata = {"agent-dependencies.json": b'{"activation":"disabled"}',
                "requirements.txt": b"independently derived requirements"}
    monkeypatch.setattr(package, "expected", lambda _: (wheels, metadata))

    class Response(io.BytesIO):
        def geturl(self):
            return self.url

    def fetch(url, timeout):
        assert timeout == 20
        response = Response(b"locked wheel")
        response.url = url
        return response

    monkeypatch.setattr(package, "urlopen", fetch)
    directory = tmp_path / "wheels"
    assert package.create(directory, "a" * 40) == 2
    return directory, wheels, metadata


def test_created_bundle_verifies_offline_and_existing_output_is_preserved(bundle, monkeypatch):
    directory, _, _ = bundle
    monkeypatch.setattr(package, "urlopen", lambda *_a, **_k: pytest.fail("Network contacted"))
    assert package.verify(directory, "a" * 40) == 2
    with pytest.raises(FileExistsError):
        package.create(directory, "a" * 40)
    assert package.verify(directory, "a" * 40) == 2


@pytest.mark.parametrize("fault", [
    "changed", "missing", "extra", "manifest", "requirements", "symlink", "hardlink", "fifo",
])
def test_incoming_bundle_faults_are_rejected_without_installation(bundle, fault):
    directory, wheels, _ = bundle
    target = directory / next(iter(wheels))
    if fault == "changed":
        target.write_bytes(b"forged wheel")
    elif fault == "missing":
        target.unlink()
    elif fault == "extra":
        (directory / "provider.whl").write_bytes(b"unrequested")
    elif fault == "manifest":
        (directory / "agent-dependencies.json").write_text("forged self-consistent metadata")
    elif fault == "requirements":
        (directory / "requirements.txt").write_text("provider==1.0")
    else:
        saved = directory.parent / "saved"
        target.rename(saved)
        if fault == "symlink":
            target.symlink_to(saved)
        elif fault == "hardlink":
            target.hardlink_to(saved)
        else:
            package.os.mkfifo(target)
    with pytest.raises((ValueError, OSError)):
        package.verify(directory, "a" * 40)


@pytest.mark.parametrize("fault", ["truncated", "oversize", "changed", "redirect"])
def test_failed_fetch_leaves_no_complete_manifest(tmp_path, monkeypatch, lock, fault):
    monkeypatch.setattr(package, "expected", lambda _: (
        package.selected_wheels(lock), {"agent-dependencies.json": b"complete"}))

    class Response(io.BytesIO):
        def geturl(self):
            return "https://example.invalid/redirect" if fault == "redirect" else self.url

    def fetch(url, timeout):
        response = Response({"truncated": b"short", "oversize": b"locked wheel!",
                             "changed": b"forged wheel", "redirect": b"locked wheel"}[fault])
        response.url = url
        return response

    monkeypatch.setattr(package, "urlopen", fetch)
    directory = tmp_path / "partial"
    with pytest.raises(ValueError, match=package.ERROR):
        package.create(directory, "a" * 40)
    assert not (directory / "agent-dependencies.json").exists()
    with pytest.raises(FileExistsError):
        package.create(directory, "a" * 40)


def test_committed_runtime_graph_matches_uv_frozen_export(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    lock_bytes = (root / "apps/api/uv.lock").read_bytes()
    selected = package.selected_wheels(tomllib.loads(lock_bytes.decode()))
    result = subprocess.run([
        "uv", "export", "--project", str(root / "apps/api"), "--frozen", "--offline",
        "--no-dev", "--no-default-groups", "--no-emit-local", "--no-header", "--no-annotate",
        "--no-hashes"], check=True, capture_output=True, text=True, timeout=15)
    exported = set()
    for line in result.stdout.splitlines():
        pin, _, marker = line.partition(" ; ")
        # This comparison independently checks uv's closure, including combined markers.
        if not marker or "win32" not in marker:
            exported.add(pin)
    assert {f"{w['name']}=={w['version']}" for w in selected.values()} == exported
    assert len(selected) == 32
    assert sum(w["size"] for w in selected.values()) == 20_086_288
    assert not {"pytest", "snowflake-connector-python", "httpx"} & {
        w["name"] for w in selected.values()}
    monkeypatch.setattr(package.review, "committed_files",
                        lambda _: {"apps/api/uv.lock": lock_bytes})
    wheels, metadata = package.expected("a" * 40)
    manifest = json.loads(metadata["agent-dependencies.json"])
    assert manifest["revision"] == "a" * 40 and manifest["activation"] == "disabled"
    assert manifest["lock_sha256"] == package.review.sha256(lock_bytes)
    assert manifest["wheels"] == wheels == selected
    assert metadata["requirements.txt"].decode().splitlines() == [
        f"{w['name']}=={w['version']} --hash={w['hash']}" for w in wheels.values()]


def test_total_size_limit_precedes_any_download(lock, monkeypatch):
    monkeypatch.setattr(package, "MAX_TOTAL", 1)
    with pytest.raises(ValueError, match=package.ERROR):
        package.selected_wheels(lock)
