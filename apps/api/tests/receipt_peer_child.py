"""Fixed disposable Linux CI helper. Not packaged or used by application startup."""

import json
import os
import signal
import socket
import struct
import sys
from pathlib import Path
from uuid import UUID

from ciq_api.agent_admission import ERROR, FakeCheckpoint, FakeEpochPin, FakeReceiptJournal
from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_receipt_peer import MAX_PACKET, FakeReceiptPeer, FakeReceiptPeerClient


def main():
    config = json.loads(sys.stdin.readline())
    path, directory = Path(config["path"]), Path(config["directory"])
    pin = FakeEpochPin.model_validate(config["pin"])
    action = config["action"]
    signal.alarm(45)  # Owned test process cannot remain after a failed parent.
    if action == "provision":
        FakeReceiptJournal.provision(directory, pin).check(())
    elif action == "bind_denied":
        peer = FakeReceiptPeer(
            FakeReceiptJournal(directory, pin), custody_uid=config["custody_uid"],
        )
        try:
            peer.bind(path)
        except AgentContractError:
            print("DENIED", flush=True)
            return
        raise AssertionError("stale_listener_adopted")
    elif action == "server":
        journal = FakeReceiptJournal(directory, pin)
        peer = FakeReceiptPeer(journal, custody_uid=config["custody_uid"])
        with peer.bind(path) as listener:
            print("READY", flush=True)
            listener.settimeout(30)
            for _ in range(128):
                peer.serve_once(listener)
        return
    elif action == "rogue":
        # Same pinned path owner, WRONG peer UID. Must receive no payload.
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(path))
        path.chmod(0o666)
        listener.listen(1)
        print("READY", flush=True)
        connection, _ = listener.accept()
        with connection:
            connection.settimeout(3)
            assert connection.recv(1) == b""
        listener.close()
        return
    elif action == "raw":
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(4)
            connection.connect(str(path))
            raw = bytes.fromhex(config["raw"])
            if config.get("fd"):
                fd = os.open("/dev/null", os.O_RDONLY)
                try:
                    connection.sendmsg([raw], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                               struct.pack("i", fd))])
                finally:
                    os.close(fd)
            else:
                connection.sendall(raw)
            connection.shutdown(socket.SHUT_WR)
            if not config.get("drop_reply"):
                try:
                    reply = connection.recv(MAX_PACKET)
                    assert reply != b"OK\n"
                except ConnectionResetError:
                    pass  # Unauthorized UID is closed before reading bytes.
    elif action == "file_denials":
        # Neither coordinator, clinical peer nor transport can read retained DB.
        for candidate in (directory / "fake-receipts.sqlite3", Path(config["other_secret"])):
            try:
                candidate.read_bytes()
            except PermissionError:
                pass
            else:
                raise AssertionError("cross_uid_file_access")
        assert not set(os.environ) & {"DATABASE_URL", "SNOWFLAKE_TOKEN",
                                      "GOOGLE_APPLICATION_CREDENTIALS", "AWS_SECRET_ACCESS_KEY"}
    else:
        try:
            client = FakeReceiptPeerClient(path, pin, server_uid=config["server_uid"],
                                           custody_uid=config["custody_uid"])
        except AgentContractError as exc:
            assert str(exc) == ERROR and exc.__suppress_context__
            print("DENIED", flush=True)
            return
        if action == "coordinator":
            from test_agent_custody_submission_offline import Engine

            from ciq_api.agent_custody_submission import FakeCustodySubmission
            from ciq_api.agent_ledger import ClaimReceipt

            material = config["material"]
            engine = Engine(material)
            row = material["entries"][0]
            claim = ClaimReceipt(
                operation_id=UUID(row["operation"]["id"]), state="reserved", version=1,
                fence_id=UUID(row["attempt"]["fence_id"]),
            )
            original = FakeCustodySubmission(engine, client, request_id="SYN-PRIVATE", claim=claim)
            assert original.prepare() is None
            replacement = FakeCustodySubmission(engine, client,
                                                request_id="SYN-PRIVATE", claim=claim)
            try:
                replacement.issue()
            except AgentContractError:
                pass
            else:
                raise AssertionError("replacement_reconstructed_permission")
            assert original.issue() is None
            try:
                original.issue()
            except AgentContractError:
                pass
            else:
                raise AssertionError("original_repeated_issue")
            print("PASS", flush=True)
            return
        expected = tuple(FakeCheckpoint.model_validate(c) for c in config.get("expected", []))
        selected = (
            FakeCheckpoint.model_validate(config["selected"]) if config.get("selected") else None
        )
        try:
            if action == "check":
                result = client.check(expected)
            elif action == "check_issued":
                result = client.check_issued(expected, selected)
            elif action == "prepare":
                result = client.prepare(selected)
            elif action == "issue":
                result = client.issue(selected)
            else:
                raise AssertionError("bad_test_command")
            assert result is None
        except AgentContractError as exc:
            assert str(exc) == ERROR and exc.__suppress_context__
            # A failed client cannot recover by a later successful command.
            try:
                client.check(())
            except AgentContractError:
                print("DENIED", flush=True)
                return
            raise AssertionError("failed_instance_reused") from None
    print("PASS", flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # Never emit payloads/config/paths/Pydantic/SQL in CI failure output.
        print("FAIL", flush=True)
        sys.exit(1)
