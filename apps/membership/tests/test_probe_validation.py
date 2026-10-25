"""Acceptance probes must distinguish actual denial from their own assertions."""

from unittest.mock import Mock

import psycopg
import pytest
from ciq_api.worker_authority import WorkerDenied
from ciq_membership_runtime import connection as boundary

from apps.membership.tests import composition_db_probe as probe
from apps.membership.tests import db_probe as older
from apps.membership.tests.test_connection import config

PROFILES = [
    ("00000000-0000-4000-8000-000000000101", "00000000-0000-4000-8000-000000000111", "processor")
]


@pytest.fixture
def connected(monkeypatch):
    for name in tuple(boundary.os.environ):
        if name.upper().startswith("PG"):
            monkeypatch.delenv(name)
    engine = Mock()
    engine.connect.return_value = Mock(__enter__=Mock(), __exit__=Mock(return_value=False))
    monkeypatch.setattr(boundary, "create_engine", Mock(return_value=engine))
    return boundary.MembershipConnectionFactory(config())


def test_unexpected_factory_acceptance_cannot_be_redacted_into_pass(connected):
    with pytest.raises(AssertionError, match="Unexpected connection acceptance"):
        probe.denied(connected, PROFILES)


def test_accepted_connection_then_cleanup_failure_is_not_a_negative_pass(connected):
    connected._engine.connect.return_value.__exit__.side_effect = RuntimeError("dummy cleanup")
    with pytest.raises(AssertionError, match="Unexpected connection acceptance"):
        probe.denied(connected, PROFILES)


@pytest.mark.parametrize("action", ["tls-hostname", "factory-ambient"])
@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_older_probe_cannot_redact_its_negative_assertion(
    connected, monkeypatch, action, cleanup_failure
):
    # Simulate a regression that bypasses ambient guards but retains redaction.
    def unguarded_connect(self):
        from contextlib import contextmanager

        @contextmanager
        def redacting():
            try:
                yield Mock()
                if cleanup_failure:
                    raise RuntimeError("dummy cleanup")
            except Exception:
                raise WorkerDenied("Worker access denied") from None

        return redacting()

    monkeypatch.setattr(boundary.MembershipConnectionFactory, "connect", unguarded_connect)
    monkeypatch.setattr(older, "fixed_factory", lambda **kwargs: connected)
    with pytest.raises(AssertionError, match=r"was accepted|configuration connected"):
        older.factory_tls_check(action)


def test_connection_denial_cannot_become_membership_absence(monkeypatch):
    factory = Mock()
    factory.connect.side_effect = WorkerDenied("Worker access denied")
    store = Mock()
    store.lookup.return_value = None
    monkeypatch.setattr(probe, "RestrictedMembershipStore", Mock(return_value=store))
    with pytest.raises(AssertionError, match="became membership absence"):
        probe.denied(factory, PROFILES)


def test_actual_factory_and_store_denials_pass(monkeypatch):
    factory = Mock()
    factory.connect.side_effect = WorkerDenied("Worker access denied")
    probe.denied(factory, PROFILES)
    assert factory.connect.call_count == 2


@pytest.mark.parametrize("outcome", ["accepted", "unrelated-error", "close-error"])
def test_raw_probe_requires_precise_driver_denial(monkeypatch, outcome):
    connect = Mock()
    if outcome in {"accepted", "close-error"}:
        connect.return_value = Mock(__enter__=Mock(), __exit__=Mock(return_value=False))
        if outcome == "close-error":
            connect.return_value.__exit__.side_effect = psycopg.OperationalError(
                "SSL error: certificate verify failed"
            )
    else:
        connect.side_effect = psycopg.OperationalError("connection refused")
    monkeypatch.setattr(probe.psycopg, "connect", connect)
    with pytest.raises(AssertionError):
        probe.raw_denied(config(), "certificate verify failed")
    with pytest.raises(AssertionError):
        probe.raw_denied(config(), probe.CA_ERRORS)


@pytest.mark.parametrize(
    "detail",
    [
        "certificate verify failed",
        "invalid padding",
        "data too large for modulus",
    ],
)
def test_wrong_ca_accepts_recognized_crypto_rejection_only(monkeypatch, detail):
    monkeypatch.setattr(
        probe.psycopg, "connect", Mock(side_effect=psycopg.OperationalError("SSL error: " + detail))
    )
    probe.raw_denied(config(), probe.CA_ERRORS)


@pytest.mark.parametrize(
    "message,expected",
    [
        ("secret password authentication failed private-host", "password"),
        ("secret invalid connection option private-token", "parameter"),
        ("private unclassified details", "check"),
    ],
)
def test_diagnostic_reason_never_returns_error_details(message, expected):
    try:
        raise RuntimeError(message)
    except RuntimeError:
        try:
            raise WorkerDenied("Worker access denied") from None
        except WorkerDenied as error:
            assert probe.reason(error) == expected
