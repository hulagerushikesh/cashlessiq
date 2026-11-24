"""Manually launched, fake-only clinical claim process; no service or queue loop.

The trusted operator supplies one private fixed-path plan and an independently
approved database binding. This process cannot stage authority or submit work.
"""

import json
import os
import resource
import signal
import stat
import sys
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, SecretStr
from sqlalchemy import URL, create_engine, event
from sqlalchemy.pool import NullPool

from ciq_api.agent_contracts import ImmutableContract
from ciq_api.agent_controller_reservation import ControllerReservation

PLAN = Path("/run/ciq-agent-claim/claim.json")
MAX_PLAN = 8192
PROCESS_SECONDS = 20
ERROR = "fake_claim_unavailable\n"
Identifier = Annotated[str, Field(strict=True, pattern=r"^[a-z_][a-z_0-9]{0,62}$")]
Oid = Annotated[int, Field(strict=True, ge=1, le=4_294_967_295)]


class ClaimPlan(ImmutableContract):
    protocol: Literal["ciq-fake-claim-v1"]
    database: Identifier
    database_oid: Oid
    login: Identifier
    login_oid: Oid
    password: SecretStr = Field(repr=False, min_length=1, max_length=1024)
    capture_schema: Annotated[str, Field(
        strict=True, pattern=r"^ciq_agent_capture(?:_[a-f0-9]{24})?$",
    )]
    request_id: Annotated[str, Field(strict=True, min_length=1, max_length=120)]
    job_id: UUID
    timeout_seconds: Annotated[int, Field(strict=True, ge=1, le=120)] = 120


def _require(value):
    if not value:
        raise ValueError("claim_denied")


def _directory(parent, name, uid):
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                 dir_fd=parent)
    try:
        item = os.fstat(fd)
        _require(item.st_uid in (0, uid) and not item.st_mode & 0o022)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _read_file(parent, uid):
    # Nonblocking prevents an untrusted FIFO from hanging before fstat rejects it.
    fd = os.open("claim.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                 dir_fd=parent)
    try:
        item = os.fstat(fd)
        _require(stat.S_ISREG(item.st_mode) and item.st_uid == uid and item.st_nlink == 1
                 and stat.S_IMODE(item.st_mode) == 0o600 and 0 < item.st_size <= MAX_PLAN)
        raw = os.read(fd, MAX_PLAN + 1)
        _require(0 < len(raw) <= MAX_PLAN)
        return raw
    finally:
        os.close(fd)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def read_plan():
    # Walk fixed absolute components using descriptors: no symlinked ancestor,
    # writable ancestor, path supplied by IPC, default credential or mkdir.
    uid = os.getuid()
    fd = _directory(None, "/", uid)
    try:
        for name in PLAN.parent.parts[1:]:
            child = _directory(fd, name, uid)
            os.close(fd)
            fd = child
        raw = _read_file(fd, uid)
    finally:
        os.close(fd)
    value = json.loads(raw, object_pairs_hook=_unique)
    _require(type(value) is dict)
    return ClaimPlan.model_validate(value)


def guard_process():
    _require(sys.platform == "linux" and sys.flags.isolated and sys.dont_write_bytecode
             and len(sys.argv) == 1)
    uid, gid = os.getuid(), os.getgid()
    _require(uid > 0 and gid > 0 and os.getresuid() == (uid,) * 3
             and os.getresgid() == (gid,) * 3 and set(os.getgroups()) <= {gid})
    # libpq/Python/cloud configuration cannot supply implicit alternate identities.
    _require(set(os.environ) <= {"PATH", "LANG", "LC_ALL"})
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    _require(status["NoNewPrivs"].strip() == "1" and all(
        int(status[key].strip(), 16) == 0 for key in ("CapInh", "CapPrm", "CapEff", "CapAmb")
    ))


def _identity(raw, plan):
    # On EVERY physical connection, before SQLAlchemy can expose it to a claim.
    # Pinned names alone cannot adopt a replaced same-name login/database.
    with raw.cursor() as cursor:
        cursor.execute(
            "SELECT d.datname,d.oid,r.rolname,r.oid FROM pg_catalog.pg_database d "
            "JOIN pg_catalog.pg_roles r ON r.rolname=session_user "
            "WHERE d.datname=current_database() AND current_user=session_user "
            "AND r.rolcanlogin AND NOT (r.rolsuper OR r.rolinherit OR r.rolcreaterole "
            "OR r.rolcreatedb OR r.rolreplication OR r.rolbypassrls) AND d.datdba<>r.oid "
            "AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m "
            "WHERE m.member=r.oid OR m.roleid=r.oid)"
        )
        _require(cursor.fetchone() == (
            plan.database, plan.database_oid, plan.login, plan.login_oid,
        ))
    raw.rollback()


def claim_once(plan):
    _require(type(plan) is ClaimPlan)
    # Build a URL from fields; there is no DSN/query/options/host/socket selector.
    engine = create_engine(URL.create(
        "postgresql+psycopg", username=plan.login, password=plan.password.get_secret_value(),
        host="127.0.0.1", port=5432, database=plan.database,
    ), poolclass=NullPool, connect_args={
        "connect_timeout": 3, "sslmode": "disable", "gssencmode": "disable",
        "options": "-cstatement_timeout=5000 -clock_timeout=2000 "
                   "-cidle_in_transaction_session_timeout=8000",
    })
    try:
        event.listen(engine, "connect", lambda raw, _: _identity(raw, plan))
        return ControllerReservation(engine, schema=plan.capture_schema).claim_requested(
            plan.request_id, plan.job_id, timeout_seconds=plan.timeout_seconds,
        )
    finally:
        engine.dispose()


def _alarm(_signum, _frame):
    raise TimeoutError


def main():
    try:
        guard_process()
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(PROCESS_SECONDS)
        claim = claim_once(read_plan())
        # Only after confirmed commit. Lost output is uncertainty, never a retry.
        packet = (claim.model_dump_json() + "\n").encode()
        _require(os.write(1, packet) == len(packet))
        return 0
    except Exception:
        # No traceback, driver error, plan, password, SQL or clinical data.
        try:
            sys.stderr.write(ERROR)
            sys.stderr.flush()
        except OSError:
            pass
        return 1
    finally:
        if sys.platform == "linux":
            signal.alarm(0)


if __name__ == "__main__":
    sys.exit(main())
