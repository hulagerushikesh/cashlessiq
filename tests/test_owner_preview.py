"""Preview configuration cannot silently open up or replace existing credentials."""

import stat

import pytest

from scripts import owner_preview as preview


@pytest.mark.parametrize(
    "origin",
    [
        "http://owner.example.test",
        "https://owner.example.test/",
        "https://owner.example.test/cases",
        "https://owner.example.test?query=1",
        "https://owner.example.test#fragment",
        "https://owner.example.test:443",
        "https://user@owner.example.test",
        "https://owner..example.test",
        "https://-owner.example.test",
        "https://localhost",
        "https://owner.example.test\nINJECTED=value",
    ],
)
def test_prepare_refuses_invalid_origin_before_any_docker_call(monkeypatch, origin):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid origin must not reach Docker")

    monkeypatch.setattr(preview.subprocess, "run", unexpected)
    with pytest.raises(ValueError):
        preview.prepare(origin)


def test_prepare_does_not_replace_existing_environment(tmp_path, monkeypatch):
    env = tmp_path / "private-env"
    env.write_text("existing authority")
    monkeypatch.setattr(preview, "ENV_FILE", env)
    monkeypatch.setattr(preview, "CREDENTIALS", tmp_path / "credentials")
    with pytest.raises(ValueError, match="already exists"):
        preview.prepare("https://owner.example.test")
    assert env.read_text() == "existing authority"


def test_headroom_denial_precedes_password_hashing_or_writes(tmp_path, monkeypatch):
    env = tmp_path / "private-env"
    credentials = tmp_path / "credentials"
    monkeypatch.setattr(preview, "ENV_FILE", env)
    monkeypatch.setattr(preview, "CREDENTIALS", credentials)

    def defer():
        raise RuntimeError("Insufficient headroom")

    monkeypatch.setattr(preview, "require_local_headroom", defer)
    with pytest.raises(RuntimeError, match="headroom"):
        preview.prepare("https://owner.example.test")
    assert not env.exists() and not credentials.exists()


def test_private_settings_keep_bcrypt_dollars_literal(tmp_path, monkeypatch):
    env = tmp_path / "private-env"
    monkeypatch.setattr(preview, "ENV_FILE", env)
    preview.private_write(env, "CIQ_PREVIEW_PASSWORD_HASH='$2a$14$hash'\n")
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert preview.read_settings()["CIQ_PREVIEW_PASSWORD_HASH"] == "$2a$14$hash"
    env.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        preview.read_settings()


def test_private_settings_refuse_symlink(tmp_path, monkeypatch):
    target = tmp_path / "target"
    preview.private_write(target, "CIQ_WEB_ORIGIN=https://owner.example.test\n")
    link = tmp_path / "link"
    link.symlink_to(target)
    monkeypatch.setattr(preview, "ENV_FILE", link)
    with pytest.raises(ValueError, match="private regular file"):
        preview.read_settings()
