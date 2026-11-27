"""Offline provider identity framing; actual UID/file isolation runs in Linux CI."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from ciq_api import agent_provider_identity as identity

BODY = b'{"synthetic":"PRIVATE captured request"}'
TOKEN = b"DUMMY-private-provider-token"
HOST = "reviewed-account.snowflakecomputing.com"


@pytest.fixture
def harness(monkeypatch):
    state = {"reads": [], "exchanges": [], "constructs": [], "fault": None, "token": TOKEN,
             "plan": {"protocol": "ciq-private-provider-v1", "hostname": HOST,
                      "request_sha256": hashlib.sha256(BODY).hexdigest()}}
    monkeypatch.setattr(identity, "_guard", lambda: None)

    def plan(path, limit):
        assert path == identity.PLAN and limit == 1024
        state["reads"].append("plan")
        return state["plan"]

    def token(path, limit):
        assert path == identity.IDENTITY and limit == 8192
        state["reads"].append("token")
        if state["fault"] == "read":
            raise OSError("PRIVATE file diagnostic")
        return state["token"]

    class Transport(identity.BoundedHTTPSProcess):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            state["constructs"].append(set(kwargs))

        def exchange(self, *, timeout):
            state["exchanges"].append(timeout)
            if state["fault"] == "exchange":
                raise ValueError("PRIVATE transport diagnostic")
            return b'{"synthetic":"PRIVATE provider response"}'

    monkeypatch.setattr(identity, "private_object", plan)
    monkeypatch.setattr(identity, "read_private", token)
    monkeypatch.setattr(identity, "BoundedHTTPSProcess", Transport)
    return state


def test_identity_keeps_secret_in_provider_transport(harness):
    attempt = identity.PrivateProviderAttempt()
    assert TOKEN.decode() not in repr(attempt)
    assert attempt.exchange(BODY, timeout=2) == b'{"synthetic":"PRIVATE provider response"}'
    assert harness["reads"] == ["plan", "token"] and len(harness["exchanges"]) == 1
    assert 0 < harness["exchanges"][0] <= 2
    assert harness["constructs"] == [{"python", "hostname", "token", "request_sha256", "body"}]
    with pytest.raises(ValueError, match=f"^{identity.ERROR}$"):
        attempt.exchange(BODY, timeout=2)
    assert harness["reads"] == ["plan", "token"]


@pytest.mark.parametrize("plan", [
    {}, {"protocol": "ciq-private-provider-v1"},
    {"protocol": "other", "hostname": HOST, "request_sha256": hashlib.sha256(BODY).hexdigest()},
    {"protocol": "ciq-private-provider-v1", "hostname": "localhost",
     "request_sha256": hashlib.sha256(BODY).hexdigest()},
    {"protocol": "ciq-private-provider-v1", "hostname": HOST, "request_sha256": "a" * 64},
    {"protocol": "ciq-private-provider-v1", "hostname": HOST,
     "request_sha256": hashlib.sha256(BODY).hexdigest(), "token": "PRIVATE selector"},
])
def test_pin_faults_do_not_open_credential(harness, plan):
    harness["plan"] = plan
    with pytest.raises(ValueError, match=f"^{identity.ERROR}$"):
        identity.PrivateProviderAttempt().exchange(BODY, timeout=1)
    assert harness["reads"] == ["plan"] and not harness["constructs"]


@pytest.mark.parametrize("body,timeout", [
    (b"", 1), (bytearray(BODY), 1), (b"x" * 256_001, 1),
    (BODY, True), (BODY, 0), (BODY, 12.1), (BODY, float("nan")), (BODY, "1"),
])
def test_invalid_input_consumes_attempt_without_file_reads(harness, body, timeout):
    attempt = identity.PrivateProviderAttempt()
    for value, budget in ((body, timeout), (BODY, 1)):
        with pytest.raises(ValueError, match=f"^{identity.ERROR}$"):
            attempt.exchange(value, timeout=budget)
    assert not harness["reads"]


@pytest.mark.parametrize("token", [b"", b"PRIVATE\nheader", b"\xff", b"x" * 8193])
def test_invalid_credential_has_no_exchange(harness, token):
    harness["token"] = token
    with pytest.raises(ValueError, match=f"^{identity.ERROR}$"):
        identity.PrivateProviderAttempt().exchange(BODY, timeout=1)
    assert not harness["exchanges"]


@pytest.mark.parametrize("fault", ["read", "exchange"])
def test_private_failure_never_returns_details_or_reloads(harness, fault, capsys):
    harness["fault"] = fault
    attempt = identity.PrivateProviderAttempt()
    for _ in range(2):
        with pytest.raises(ValueError, match=f"^{identity.ERROR}$"):
            attempt.exchange(BODY, timeout=1)
    assert harness["reads"] == ["plan", "token"]
    assert capsys.readouterr() == ("", "")


def test_concurrent_attempts_read_identity_once(harness):
    attempt = identity.PrivateProviderAttempt()

    def exchange(_):
        try:
            return attempt.exchange(BODY, timeout=1)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(exchange, range(2)))
    assert sum(result is not None for result in results) == 1
    assert harness["reads"] == ["plan", "token"]


@pytest.mark.parametrize("fault", [
    None, "platform", "isolated", "bytecode", "uid", "saved_uid", "gid", "saved_gid",
    "groups", "core", "environment",
])
def test_exact_unprivileged_identity_and_clean_process(monkeypatch, fault):
    monkeypatch.setattr(identity, "sys", SimpleNamespace(
        platform="darwin" if fault == "platform" else "linux",
        flags=SimpleNamespace(isolated=fault != "isolated"),
        dont_write_bytecode=fault != "bytecode",
    ))
    uid = (0, 0, 0) if fault == "uid" else (53004, 53004, 0 if fault == "saved_uid" else 53004)
    gid = (0, 0, 0) if fault == "gid" else (53004, 53004, 0 if fault == "saved_gid" else 53004)
    monkeypatch.setattr(identity.os, "getresuid", lambda: uid, raising=False)
    monkeypatch.setattr(identity.os, "getresgid", lambda: gid, raising=False)
    monkeypatch.setattr(identity.os, "getgroups", lambda: [53002] if fault == "groups" else [])
    monkeypatch.setattr(identity.resource, "getrlimit",
                        lambda _: (1, 1) if fault == "core" else (0, 0))
    monkeypatch.setattr(identity.os, "environ", {"DATABASE_URL": "PRIVATE"}
                        if fault == "environment" else {"LANG": "C.UTF-8"})
    if fault:
        with pytest.raises(ValueError, match=f"^{identity.ERROR}$"):
            identity._guard()
    else:
        identity._guard()


def test_identity_denial_precedes_private_reads(harness, monkeypatch):
    def denied():
        raise PermissionError("PRIVATE identity diagnostic")

    monkeypatch.setattr(identity, "_guard", denied)
    with pytest.raises(ValueError, match=f"^{identity.ERROR}$"):
        identity.PrivateProviderAttempt().exchange(BODY, timeout=1)
    assert not harness["reads"]


@pytest.mark.parametrize("samples,reads,exchanges", [
    ([0, 2], ["plan"], []),
    ([0, 0.5, 2], ["plan", "token"], []),
    ([0, 0.5, 0.75], ["plan", "token"], [0.25]),
])
def test_preparation_consumes_original_budget(harness, monkeypatch, samples, reads, exchanges):
    clock = iter(samples)
    monkeypatch.setattr(identity.time, "monotonic", lambda: next(clock))
    attempt = identity.PrivateProviderAttempt()
    if exchanges:
        attempt.exchange(BODY, timeout=1)
    else:
        with pytest.raises(ValueError, match=f"^{identity.ERROR}$"):
            attempt.exchange(BODY, timeout=1)
    assert harness["reads"] == reads and harness["exchanges"] == exchanges


def test_reviewed_plan_pins_full_scope_and_cannot_switch_to_original_mode(harness):
    harness["plan"].update(protocol="ciq-private-provider-v2", pin_sha256="a" * 64)
    attempt = identity.PrivateProviderAttempt()
    assert attempt.exchange_reviewed(BODY, timeout=2, pin_sha256="a" * 64)
    with pytest.raises(ValueError, match=f"^{identity.ERROR}$"):
        attempt.exchange(BODY, timeout=2)
    assert harness["reads"] == ["plan", "token"] and len(harness["exchanges"]) == 1


@pytest.mark.parametrize("fault", ["wrong-pin", "v1-plan", "v1-entry", "extra", "body"])
def test_reviewed_plan_faults_never_open_credential(harness, fault):
    harness["plan"].update(protocol="ciq-private-provider-v2", pin_sha256="a" * 64)
    if fault == "wrong-pin":
        harness["plan"]["pin_sha256"] = "b" * 64
    elif fault == "v1-plan":
        harness["plan"].pop("pin_sha256")
        harness["plan"]["protocol"] = "ciq-private-provider-v1"
    elif fault == "extra":
        harness["plan"]["selector"] = "PRIVATE"
    elif fault == "body":
        harness["plan"]["request_sha256"] = "b" * 64
    attempt = identity.PrivateProviderAttempt()
    with pytest.raises(ValueError, match=f"^{identity.ERROR}$"):
        if fault == "v1-entry":
            attempt.exchange(BODY, timeout=2)
        else:
            attempt.exchange_reviewed(BODY, timeout=2, pin_sha256="a" * 64)
    assert harness["reads"] == ["plan"] and not harness["constructs"]


@pytest.mark.parametrize("pin", [None, b"a" * 64, "A" * 64, "g" * 64, "a" * 63, True])
def test_malformed_reviewed_pin_consumes_before_any_file_read(harness, pin):
    attempt = identity.PrivateProviderAttempt()
    for value in (pin, "a" * 64):
        with pytest.raises(ValueError, match=f"^{identity.ERROR}$"):
            attempt.exchange_reviewed(BODY, timeout=2, pin_sha256=value)
    assert not harness["reads"]
