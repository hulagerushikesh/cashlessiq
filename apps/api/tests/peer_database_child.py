"""Fixed dummy integration helper, never installed as a service or packaged."""

import base64
import hashlib
import json
import os
import signal
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from ciq_api.agent_admission import FakeEpochPin, FakeReceiptJournal
from ciq_api.agent_contracts import AgentContractError, AgentInput
from ciq_api.agent_controller_capture import ControllerCapture
from ciq_api.agent_custody_recovery import FakeCustodyRecovery
from ciq_api.agent_custody_submission import FakeCustodySubmission
from ciq_api.agent_executor import BoundedFakeProcess, FakeProcessRequest
from ciq_api.agent_ledger import ClaimReceipt, FakeAgentLedger
from ciq_api.agent_receipt_peer import FakeReceiptPeerClient
from ciq_api.agent_receipt_verifier import FakeReceiptVerifier

ROOT = Path(__file__).resolve().parents[3]


def forbidden(*_args, **_kwargs):
    raise AssertionError("owner_or_direct_journal_runtime")


def main():
    config = json.loads(sys.stdin.readline())
    uid = os.getuid()
    assert uid > 0 and os.getresuid() == (uid, uid, uid)
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    assert all(int(status[k].strip(), 16) == 0 for k in ("CapEff", "CapPrm", "CapAmb"))
    assert status["NoNewPrivs"].strip() == "1"
    signal.alarm(35)
    # A runtime fallback to owner methods or the same-process journal is fatal.
    for cls in (FakeAgentLedger, FakeReceiptJournal):
        for name, method in vars(cls).items():
            if callable(method) and not name.startswith("__"):
                setattr(cls, name, forbidden)
    for path in (Path(config["directory"]) / "fake-receipts.sqlite3",
                 Path(config["other_secret"])):
        try:
            path.read_bytes()
        except PermissionError:
            pass
        else:
            raise AssertionError("cross_uid_file_access")
    url = make_url(config["runtime_url"])
    clinical = config["action"] == "clinical"
    prefix = "ciq_scope_login_" if clinical else "ciq_receipt_login_"
    assert url.host == "127.0.0.1" and url.port == 5432
    assert url.database.startswith("ciq_controller_") and url.username.startswith(prefix)
    assert not set(os.environ) & {"DATABASE_URL", "TEST_DATABASE_URL",
                                  "SNOWFLAKE_TOKEN", "GOOGLE_APPLICATION_CREDENTIALS"}
    engine = create_engine(url, connect_args={
        "options": "-cstatement_timeout=5000 -cidle_in_transaction_session_timeout=10000",
    })
    try:
        with engine.connect() as db:
            assert db.scalar(text("SELECT session_user")) == url.username
            assert db.scalar(text("SELECT current_user")) == url.username
        for statement in (
            f'SELECT * FROM "{config["product"]}".submitted_case',
            f'SELECT * FROM "{config["schema"]}".principal',
        ):
            try:
                with engine.begin() as db:
                    db.execute(text(statement))
            except DBAPIError as exc:
                assert exc.orig.sqlstate == "42501"
            else:
                raise AssertionError("direct_table_access")
        if clinical:
            snapshot = ControllerCapture(engine, schema=config["capture"]).capture("REQ-FAKE-0")
            expected = AgentInput.model_validate(config["snapshot"])
            assert snapshot.facts_json == expected.facts_json
            assert snapshot.policy_json == expected.policy_json
            assert snapshot.binding.model_dump(exclude={"correlation_id"}) == (
                expected.binding.model_dump(exclude={"correlation_id"})
            )
            print("PASS", flush=True)
            return
        pin = FakeEpochPin.model_validate(config["pin"])
        client = FakeReceiptPeerClient(
            config["path"], pin, server_uid=config["server_uid"],
            custody_uid=config["custody_uid"],
        )
        claim = ClaimReceipt.model_validate(config["claim"])
        fixture = Path(config["fixture"])
        transport = BoundedFakeProcess((
            sys.executable, "-I", str(ROOT / "apps/agent-transport/tests/exchange_fixture.py"),
            str(ROOT / "apps/agent-transport/fake_transport.py"), str(fixture),
        ))
        exchange = transport.exchange
        exchanges = 0

        def canned(raw, *, timeout):
            nonlocal exchanges
            packet = FakeProcessRequest.model_validate_json(raw)
            assert packet.operation_id == claim.operation_id
            assert packet.snapshot == AgentInput.model_validate(config["snapshot"])
            exchanges += 1
            assert exchanges == 1
            fixture.write_text(json.dumps({
                "request_sha256": hashlib.sha256(raw).hexdigest(),
                "candidate_base64": base64.b64encode(json.dumps(config["candidate"]).encode())
                .decode(),
            }))
            fixture.chmod(0o600)
            return exchange(raw, timeout=timeout)

        transport.exchange = canned

        def coordinator():
            return FakeCustodySubmission(engine, client, schema=config["schema"],
                                         request_id="REQ-FAKE-0", claim=claim,
                                         transport=transport)

        original = coordinator()
        recovery = FakeCustodyRecovery(
            engine, client, schema=config["schema"], request_id="REQ-FAKE-0",
            operation_id=UUID(config["claim"]["operation_id"]),
        )
        verifier = FakeReceiptVerifier(engine, client, schema=config["schema"])
        print("READY", flush=True)
        for line in sys.stdin:
            command = line.strip()
            if command == "exit":
                break
            actions = {
                "prepare": original.prepare, "dispatch": original.dispatch,
                "publish": original.publish, "heartbeat": original.heartbeat,
                "recover": recovery.recover, "verify": verifier.check,
                "replacement": coordinator().dispatch,
            }
            assert command in actions
            try:
                assert actions[command]() is None
            except AgentContractError:
                print("DENIED", flush=True)
            else:
                print("OK", flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        # No dummy passwords, SQL, clinical packets or exception values in logs.
        print("FAIL:" + type(exc).__name__, flush=True)
        sys.exit(1)
