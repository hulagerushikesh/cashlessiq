"""Offline entry wiring/denial tests; no database, credentials or provider I/O."""

import hashlib
import json
from types import SimpleNamespace

import pytest
from single_call_fixtures import call_material

from ciq_api import agent_single_call_provider_runner as provider
from ciq_api import agent_single_call_receipt_runner as receipt
from ciq_api import agent_single_call_runner as custody


@pytest.fixture
def values():
    return {
        "protocol": "ciq-single-call-custody-v1", "database": "ciq_dummy",
        "database_oid": 12001, "login": "ciq_custody", "login_oid": 12002,
        "password": "PRIVATE PASSWORD", "pin": json.loads(call_material()[2].canonical()),
    }


@pytest.mark.parametrize("field,value", [
    ("protocol", "ciq-fake-custody-v1"), ("database_oid", True), ("login_oid", 0),
    ("database", "dummy?host=remote"), ("login", "postgres;SET ROLE owner"),
    ("password", ""), ("password", "x" * 1025), ("pin", {}),
    ("dsn", "postgresql://owner"), ("host", "remote"), ("port", 9999),
    ("schema", "public"), ("journal", "/tmp/empty"), ("provider_uid", 1),
    ("retry", True), ("candidate", {}), ("response", "PRIVATE"),
])
def test_private_plan_rejects_selector_or_authority_injection(values, field, value):
    with pytest.raises(ValueError):
        custody.SingleCallPlan.model_validate_json(json.dumps({**values, field: value}))


def test_custody_reads_only_fixed_private_file_and_hides_secrets(values, monkeypatch):
    calls = []
    monkeypatch.setattr(custody, "private_object", lambda path, bound:
                        calls.append((path, bound)) or values)
    plan = custody.read_plan()
    assert calls == [(custody.PLAN, 8192)]
    assert "PRIVATE PASSWORD" not in repr(plan) and "hostname" not in repr(plan)


@pytest.mark.parametrize("fails", [False, True])
def test_custody_wires_exact_original_adapter_and_disposes_on_all_outcomes(
    values, monkeypatch, fails,
):
    plan = custody.SingleCallPlan.model_validate_json(json.dumps(values))
    calls = []
    engine = SimpleNamespace(dispose=lambda: calls.append("disposed"))
    monkeypatch.setattr(custody, "_guard", lambda uid: calls.append(("uid", uid)))

    def create(url, **options):
        assert (url.host, url.port, url.database, url.username, url.query) == (
            "127.0.0.1", 5432, plan.database, plan.login, {},
        )
        assert url.password == "PRIVATE PASSWORD" and options["poolclass"] is custody.NullPool
        assert options["connect_args"]["connect_timeout"] == 3
        assert "statement_timeout=5000" in options["connect_args"]["options"]
        calls.append("engine")
        return engine

    def listen(e, name, check):
        assert e is engine and name == "connect" and callable(check)
        calls.append("identity")

    class Original:
        def __init__(self, e, *, operation_id, receipt, provider):
            assert e is engine and operation_id == plan.pin.operation_id
            assert receipt.pin_sha256 == provider.pin_sha256 == hashlib.sha256(
                plan.pin.canonical().encode()).hexdigest()
            calls.append("original")

        def run(self):
            calls.append("run")
            if fails:
                raise ValueError("PRIVATE database diagnostic")

    monkeypatch.setattr(custody, "create_engine", create)
    monkeypatch.setattr(custody.event, "listen", listen)
    monkeypatch.setattr(custody, "ProductSingleCall", Original)
    if fails:
        with pytest.raises(ValueError):
            custody.run_once(plan)
    else:
        assert custody.run_once(plan) is None
    assert calls == [("uid", 53002), "engine", "identity", "original", "run", "disposed"]


@pytest.mark.parametrize("phase", ["ready", "issued", "observed"])
def test_receipt_uses_existing_history_and_only_ready_can_bind(values, monkeypatch, phase):
    plan = receipt.ReceiptPlan.model_validate_json(json.dumps(
        {"protocol": "ciq-single-call-receipt-v1", "pin": values["pin"]},
    ))
    calls = []
    monkeypatch.setattr(receipt, "_guard", lambda uid: calls.append(("uid", uid)))
    monkeypatch.setattr(receipt, "read_private", lambda path, bound:
                        calls.append(("file", path, bound)))

    class Journal:
        def __init__(self, path, pin):
            assert path == receipt.JOURNAL and pin == plan.pin
            calls.append("existing")

        def status(self):
            calls.append("status")
            return SimpleNamespace(phase=phase)

    class Peer:
        def __init__(self, journal):
            assert type(journal) is Journal
            calls.append("peer")

        def bind(self):
            calls.append("bind")

        def serve_attempt(self):
            calls.append("pair")

        def close(self):
            calls.append("close")

    monkeypatch.setattr(receipt, "SingleCallJournal", Journal)
    monkeypatch.setattr(receipt, "SingleCallReceiptPeer", Peer)
    monkeypatch.setattr(receipt.os, "write", lambda fd, raw:
                        calls.append(("ready", fd, raw)) or len(raw))
    if phase == "ready":
        assert receipt.serve(plan) is None
        assert calls[-5:] == ["peer", "bind", ("ready", 1, receipt.READY), "pair", "close"]
    else:
        with pytest.raises(ValueError):
            receipt.serve(plan)
        assert "peer" not in calls
    assert calls[:4] == [("uid", 53003),
                        ("file", receipt.JOURNAL / "single-call.sqlite3", 256 * 1024),
                        "existing", "status"]


@pytest.mark.parametrize("fault", [None, "protocol", "extra", "pin", "noncanonical"])
def test_provider_binds_full_private_pin_before_any_identity_io(values, monkeypatch, fault):
    plan = {"protocol": "ciq-private-provider-v2", "pin": values["pin"]}
    if fault == "protocol":
        plan["protocol"] = "ciq-private-provider-v1"
    elif fault == "extra":
        plan["hostname"] = "another.snowflakecomputing.com"
    elif fault == "pin":
        plan["pin"] = {}
    elif fault == "noncanonical":
        plan["pin"]["ends_at"] = plan["pin"]["ends_at"].replace("+00:00", "Z")
    calls = []
    monkeypatch.setattr(provider, "_guard", lambda: calls.append("guard"))
    monkeypatch.setattr(provider, "private_object", lambda path, bound:
                        calls.append((path, bound)) or plan)

    class Peer:
        def __init__(self, digest):
            assert digest == hashlib.sha256(
                json.dumps(plan["pin"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            calls.append("peer")

        def bind(self):
            calls.append("bind")

        def serve_once(self, *, timeout):
            assert timeout == 12.0
            calls.append("exchange")

        def close(self):
            calls.append("close")

    monkeypatch.setattr(provider, "ReviewedProviderPeer", Peer)
    monkeypatch.setattr(provider.os, "write", lambda fd, raw:
                        calls.append(("ready", fd, raw)) or len(raw))
    if fault:
        with pytest.raises(ValueError):
            provider.serve()
        assert "peer" not in calls
    else:
        assert provider.serve() is None
        assert calls == ["guard", (provider.PLAN, 4096), "peer", "bind",
                         ("ready", 1, provider.READY), "exchange", "close"]


@pytest.mark.parametrize("module", [custody, receipt, provider])
@pytest.mark.parametrize("fault", [None, "guard", "entry", "output"])
def test_manual_main_has_bounded_alarm_and_fixed_redacted_output(
    module, fault, monkeypatch, capfd,
):
    alarms = []

    def guard():
        if fault == "guard":
            raise ValueError("PRIVATE runtime identity")

    def entry(*args):
        if fault == "entry":
            raise ValueError("PRIVATE PASSWORD BODY SQL")

    monkeypatch.setattr(module, "guard_process", guard)
    monkeypatch.setattr(module, "_guard", lambda *args: None)
    monkeypatch.setattr(module.sys, "platform", "linux")
    monkeypatch.setattr(module.resource, "setrlimit", lambda *args: None)
    monkeypatch.setattr(module.signal, "signal", lambda *args: None)
    monkeypatch.setattr(module.signal, "alarm", alarms.append)
    if module is custody:
        monkeypatch.setattr(module, "read_plan", lambda: object())
        monkeypatch.setattr(module, "run_once", entry)
    elif module is receipt:
        monkeypatch.setattr(module, "private_object", lambda *args:
                            {"protocol": "ciq-single-call-receipt-v1",
                             "pin": json.loads(call_material()[2].canonical())})
        monkeypatch.setattr(module, "serve", entry)
    else:
        monkeypatch.setattr(module, "serve", entry)
    if fault == "output":
        # Receipt/provider readiness writes belong to their real serve method;
        # simulate that failure through the entry stub as well.
        if module is custody:
            write = module.os.write

            def fail_stdout(fd, raw):
                if fd == 1:
                    raise BrokenPipeError
                return write(fd, raw)

            monkeypatch.setattr(module.os, "write", fail_stdout)
        else:
            monkeypatch.setattr(module, "serve", lambda *args: (_ for _ in ()).throw(OSError()))
    assert module.main() == (1 if fault else 0)
    captured = capfd.readouterr()
    assert captured.err == (module.ERROR.decode() if fault else "")
    assert captured.out == (custody.SUCCESS.decode() if module is custody and not fault else "")
    assert alarms == ([0] if fault == "guard" else [module.PROCESS_SECONDS, 0])
