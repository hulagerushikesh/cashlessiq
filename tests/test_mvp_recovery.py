"""Recovery refuses accidental service restarts and incomplete restores."""

import pytest

from scripts import check_mvp_recovery as recovery


def test_restart_is_disallowed_outside_disposable_preview_ci(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="disposable GitHub CI"):
        recovery.require_restart_permission("preview")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(ValueError, match="disposable GitHub CI"):
        recovery.require_restart_permission("product")
    monkeypatch.delenv("GITHUB_ACTIONS")
    with pytest.raises(ValueError, match="disposable GitHub CI"):
        recovery.fresh_volume_preview(None, {})


def test_fresh_volume_uses_separate_port_and_project():
    assert recovery.fresh_compose_prefix()[2:4] == ["-p", "cashlessiq-recovery-ci"]
    assert recovery.fresh_preview_env()["CIQ_PREVIEW_PORT"] == "3081"
    assert recovery.fresh_preview_env()["CIQ_WEB_ORIGIN"] == "http://127.0.0.1:3081"


def test_restore_rejects_missing_or_changed_table_rows():
    verified = {"review_audit": {"rows": 4, "sha256": "a" * 64}}
    recovery.verify_manifest(verified, verified)
    with pytest.raises(RuntimeError, match="do not match"):
        recovery.verify_manifest(verified, {})
    with pytest.raises(RuntimeError, match="do not match"):
        recovery.verify_manifest(verified, {"review_audit": {"rows": 3, "sha256": "a" * 64}})
