"""Early refusal for the explicit Linux UID acceptance; no local host changes."""

from pathlib import Path

import pytest

from scripts import test_agent_provider_identity as runner


def guarded(monkeypatch):
    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner.os, "geteuid", lambda: 0)
    for key, value in (("GITHUB_ACTIONS", "true"),
                       ("GITHUB_REPOSITORY", "hulagerushikesh/cashlessiq"),
                       ("CIQ_PROVIDER_IDENTITY_TEST", "1")):
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize("fault", ["platform", "uid", "actions", "repository", "optin"])
def test_guard_refuses_before_host_inventory_or_mutation(monkeypatch, fault):
    guarded(monkeypatch)
    if fault == "platform":
        monkeypatch.setattr(runner.sys, "platform", "darwin")
    elif fault == "uid":
        monkeypatch.setattr(runner.os, "geteuid", lambda: 1)
    else:
        key = {"actions": "GITHUB_ACTIONS", "repository": "GITHUB_REPOSITORY",
               "optin": "CIQ_PROVIDER_IDENTITY_TEST"}[fault]
        monkeypatch.setenv(key, "wrong")
    monkeypatch.setattr(Path, "exists", lambda _: pytest.fail("early host access"))
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: pytest.fail("early host mutation"))
    with pytest.raises(SystemExit, match="explicit disposable"):
        runner.main()


@pytest.mark.parametrize("symlink", [False, True])
def test_existing_path_is_preserved(monkeypatch, tmp_path, symlink):
    guarded(monkeypatch)
    existing = tmp_path / "private"
    if symlink:
        existing.symlink_to(tmp_path / "absent")
    else:
        existing.mkdir()
        (existing / "owner").write_text("preserve")
    monkeypatch.setattr(runner, "PRIVATE", existing)
    monkeypatch.setattr(runner, "RUNTIME", tmp_path / "runtime")
    with pytest.raises(RuntimeError, match="existing host object"):
        runner.main()
    assert existing.is_symlink() if symlink else (existing / "owner").read_text() == "preserve"


@pytest.mark.parametrize("lookup", ["user", "group"])
def test_existing_numeric_identity_denied_before_mutation(monkeypatch, tmp_path, lookup):
    guarded(monkeypatch)
    monkeypatch.setattr(runner, "PRIVATE", tmp_path / "private")
    monkeypatch.setattr(runner, "RUNTIME", tmp_path / "runtime")

    def absent(_):
        raise KeyError

    monkeypatch.setattr(runner.pwd, "getpwuid",
                        (lambda _: object()) if lookup == "user" else absent)
    monkeypatch.setattr(runner.grp, "getgrgid",
                        (lambda _: object()) if lookup == "group" else absent)
    with pytest.raises(RuntimeError, match="occupied numeric identity"):
        runner.main()
    assert not runner.PRIVATE.exists() and not runner.RUNTIME.exists()
