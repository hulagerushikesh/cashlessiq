"""The remote preview package stays bounded to approved images and files."""

import io
import json
import stat
import tarfile

import pytest

from scripts import gcp_preview_runtime as runtime
from scripts import package_gcp_preview as package


def private_environment(path):
    path.write_text(
        "CIQ_DB_PASSWORD=fictional-password\n"
        "CIQ_LOCAL_AUTH_SECRET=fictional-secret\n"
        "CIQ_WEB_ORIGIN=https://owner.example.test\n"
        f"CIQ_PREVIEW_PASSWORD_HASH='$2a$14${'A' * 53}'\n"
    )
    path.chmod(0o600)


def image(service, character):
    registry = "us-central1-docker.pkg.dev/cashlessiq-dev-rush/ciq-preview"
    return f"{registry}/{service}@sha256:{character * 64}"


@pytest.mark.parametrize(
    "bad_image",
    [
        "us-central1-docker.pkg.dev/cashlessiq-dev-rush/ciq-preview/api:latest",
        "us-central1-docker.pkg.dev/other/ciq-preview/api@sha256:" + "a" * 64,
        "us-central1-docker.pkg.dev/cashlessiq-dev-rush/ciq-preview/api@sha256:" + "A" * 64,
    ],
)
def test_rejects_mutable_or_wrong_project_image(tmp_path, monkeypatch, bad_image):
    env = tmp_path / ".env.owner-preview.local"
    private_environment(env)
    monkeypatch.setattr(runtime, "ENV_FILE", env)
    with pytest.raises(ValueError, match="exact SHA-256"):
        runtime.set_images(bad_image, image("web", "b"))
    assert "CIQ_PREVIEW_API_IMAGE" not in env.read_text()


def test_runtime_resolves_full_mvp_and_refuses_replacing_digest(tmp_path, monkeypatch):
    env = tmp_path / ".env.owner-preview.local"
    private_environment(env)
    monkeypatch.setattr(runtime, "ENV_FILE", env)
    runtime.set_images(image("api", "a"), image("web", "b"))
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    runtime.check()  # Docker Compose config only; no build, start or GCP call.
    with pytest.raises(ValueError, match="Existing image digest differs"):
        runtime.set_images(image("api", "c"), image("web", "b"))
    assert runtime.validate()["CIQ_PREVIEW_API_IMAGE"] == image("api", "a")


def test_runtime_rejects_shell_port_override(tmp_path, monkeypatch):
    env = tmp_path / ".env.owner-preview.local"
    private_environment(env)
    monkeypatch.setattr(runtime, "ENV_FILE", env)
    runtime.set_images(image("api", "a"), image("web", "b"))
    monkeypatch.setenv("CIQ_PREVIEW_PORT", "3082")
    with pytest.raises(ValueError, match="loopback port 3080"):
        runtime.check()


def test_bundle_rejects_extra_entry_and_changed_bytes(tmp_path):
    path = tmp_path / "bad.tar.gz"
    manifest = {
        "revision": "a" * 40,
        "project_id": "cashlessiq-dev-rush",
        "files": {name: "0" * 64 for name in package.FILES},
    }
    with tarfile.open(path, "w:gz") as archive:
        for name in (*package.FILES, "unwanted-secret"):
            data = b"test"
            item = tarfile.TarInfo(name)
            item.size = len(data)
            archive.addfile(item, io.BytesIO(data))
        data = json.dumps(manifest).encode()
        item = tarfile.TarInfo(package.MANIFEST)
        item.size = len(data)
        archive.addfile(item, io.BytesIO(data))
    with pytest.raises(ValueError, match="unexpected"):
        package.verify(path)
