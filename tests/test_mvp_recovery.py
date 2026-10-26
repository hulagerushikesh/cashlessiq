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


def test_restore_rejects_missing_or_changed_table_rows():
    verified = {"review_audit": {"rows": 4, "sha256": "a" * 64}}
    recovery.verify_manifest(verified, verified)
    with pytest.raises(RuntimeError, match="do not match"):
        recovery.verify_manifest(verified, {})
    with pytest.raises(RuntimeError, match="do not match"):
        recovery.verify_manifest(verified, {"review_audit": {"rows": 3, "sha256": "a" * 64}})
