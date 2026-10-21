"""Offline factory tests: dummy secrets, no PostgreSQL or network required."""

from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock

import pytest
from ciq_api.worker_authority import WorkerDenied
from ciq_membership_runtime import connection as boundary
from sqlalchemy.pool import NullPool


def config(**changes):
    values = dict(
        host="ciq-membership-db.test",
        hostaddr="172.20.0.2",
        port=5432,
        database="membership",
        username="membership_reader",
        password="dummy-only:'/@? secret",
        ca_file="/run/ciq/db-ca.pem",
    )
    values.update(changes)
    return boundary.MembershipDatabaseConfig(**values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("host", "https://db"),
        ("host", "db,evil"),
        ("host", "db:5432"),
        ("host", "db evil"),
        ("host", "déb"),
        ("host", "127.0.0.1"),
        ("host", "DB.test"),
        ("host", "db."),
        ("host", "-db"),
        ("hostaddr", "127.0.0.1"),
        ("hostaddr", "8.8.8.8"),
        ("hostaddr", "100.64.0.1"),
        ("hostaddr", "172.32.0.1"),
        ("hostaddr", "10.00.0.1"),
        ("hostaddr", "::1"),
        ("hostaddr", 123),
        ("port", True),
        ("port", "5432"),
        ("port", 0),
        ("port", 65536),
        ("database", "dbname=x"),
        ("username", "user name"),
        ("username", ""),
        ("password", ""),
        ("password", "bad\x00value"),
        ("password", 123),
        ("ca_file", "relative.pem"),
        ("ca_file", "/a/../ca.pem"),
        ("ca_file", "/a//ca.pem"),
        ("ca_file", "//ca.pem"),
        ("ca_file", "/"),
        ("ca_file", "/a\nca.pem"),
    ],
)
def test_strict_configuration(field, value):
    with pytest.raises(ValueError, match=r"^Invalid membership database configuration$"):
        config(**{field: value})


def test_immutable_redacted_no_unknown_options():
    value = config()
    assert repr(value) == "MembershipDatabaseConfig(<redacted>)"
    assert repr(replace(value, password="different")) == repr(value)
    with pytest.raises(FrozenInstanceError):
        value.password = "changed"
    with pytest.raises(TypeError):
        config(sslmode="disable")


def test_no_io_construction_and_exact_options(monkeypatch):
    create = Mock()
    monkeypatch.setattr(boundary, "create_engine", create)
    value = config()
    factory = boundary.MembershipConnectionFactory(value)
    create.return_value.connect.assert_not_called()
    url = create.call_args.args[0]
    assert url.password == value.password  # URL object, never interpolated SQL/DSN.
    assert url.host == value.host and url.database == value.database
    assert not url.query
    assert value.password not in str(url)
    assert repr(factory) == "MembershipConnectionFactory(<redacted>)"
    assert create.call_args.kwargs == dict(
        connect_args=dict(
            hostaddr=value.hostaddr,
            sslmode="verify-full",
            sslrootcert=value.ca_file,
            ssl_min_protocol_version="TLSv1.3",
            gssencmode="disable",
            connect_timeout=2,
            options="-csearch_path=",
            passfile="/dev/null",
            sslcertmode="disable",
            application_name="ciq-membership",
        ),
        poolclass=NullPool,
        echo=False,
        hide_parameters=True,
    )


@pytest.fixture
def factory(monkeypatch):
    for name in tuple(boundary.os.environ):
        if name.upper().startswith("PG"):
            monkeypatch.delenv(name)
    engine = Mock()
    engine.connect.return_value = Mock(__enter__=Mock(), __exit__=Mock(return_value=False))
    monkeypatch.setattr(boundary, "create_engine", Mock(return_value=engine))
    return boundary.MembershipConnectionFactory(config()), engine


@pytest.mark.parametrize(
    "name",
    [
        "PGHOST",
        "PGHOSTADDR",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
        "PGPASSFILE",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGSSLMODE",
        "PGSSLROOTCERT",
        "PGSSLMINPROTOCOLVERSION",
        "PGOPTIONS",
        "PGGSSENCMODE",
        "PGCONNECT_TIMEOUT",
    ],
)
def test_ambient_libpq_denied_without_connection_or_env_mutation(factory, monkeypatch, name):
    candidate, engine = factory
    monkeypatch.setenv(name, "hostile-setting")
    with pytest.raises(WorkerDenied, match=r"^Worker access denied$"), candidate.connect():
        pytest.fail("Must not yield")
    engine.connect.assert_not_called()
    assert boundary.os.environ[name] == "hostile-setting"


def test_new_connection_each_time_and_close(factory):
    candidate, engine = factory
    for _ in range(2):
        with candidate.connect():
            pass
    assert engine.connect.call_count == 2
    assert engine.connect.return_value.__exit__.call_count == 2
    candidate.close()
    engine.dispose.assert_called_once_with()


@pytest.mark.parametrize("stage", ["connect", "body", "close"])
def test_errors_suppressed_without_retry(factory, stage):
    candidate, engine = factory
    private = "dummy-password private-host private-sql"
    if stage == "connect":
        engine.connect.side_effect = RuntimeError(private)
    if stage == "close":
        engine.dispose.side_effect = RuntimeError(private)
    with pytest.raises(WorkerDenied) as caught:
        if stage == "close":
            candidate.close()
        else:
            with candidate.connect():
                raise RuntimeError(private)
    assert str(caught.value) == "Worker access denied"
    assert caught.value.__suppress_context__
    assert caught.value.__cause__ is None
    assert engine.connect.call_count <= 1


def test_constructor_failure_is_sanitized(monkeypatch):
    monkeypatch.setattr(boundary, "create_engine", Mock(side_effect=RuntimeError("secret")))
    with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
        boundary.MembershipConnectionFactory(config())
    with pytest.raises(ValueError):
        boundary.MembershipConnectionFactory({"password": "not typed"})


def test_real_dialect_preserves_fixed_parameters_without_network(monkeypatch):
    import psycopg

    for name in tuple(boundary.os.environ):
        if name.upper().startswith("PG"):
            monkeypatch.delenv(name)
    # Exercise SQLAlchemy's actual psycopg argument assembly, but stop BEFORE
    # libpq can open a socket or read a file. Never include kwargs in failures.
    captured = []

    def stop_before_libpq(*args, **kwargs):
        captured.append((args, kwargs))
        raise RuntimeError("dummy connection failure")

    monkeypatch.setattr(psycopg, "connect", stop_before_libpq)
    value = config()
    candidate = boundary.MembershipConnectionFactory(value)
    assert not captured
    try:
        with pytest.raises(WorkerDenied), candidate.connect():
            pytest.fail("Unexpected connection")
        assert len(captured) == 1
        args, kwargs = captured[0]
        assert args == ()
        assert kwargs["host"] == value.host and kwargs["hostaddr"] == value.hostaddr
        assert kwargs["password"] == value.password and kwargs["dbname"] == value.database
        assert kwargs["user"] == value.username and kwargs["port"] == value.port
        assert kwargs["sslmode"] == "verify-full"
        assert kwargs["sslrootcert"] == value.ca_file
        assert kwargs["ssl_min_protocol_version"] == "TLSv1.3"
        assert kwargs["gssencmode"] == "disable" and kwargs["connect_timeout"] == 2
        assert kwargs["options"] == "-csearch_path=" and kwargs["passfile"] == "/dev/null"
        assert kwargs["sslcertmode"] == "disable"
    finally:
        candidate.close()
