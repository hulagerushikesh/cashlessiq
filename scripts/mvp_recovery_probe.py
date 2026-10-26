"""Read-only, in-container snapshot probe used by check_mvp_recovery.

Only hashes, counts and fictional record identifiers leave the container. The
exporting transaction remains open until the host finishes pg_dump.
"""

import hashlib
import json
import re
import sys


def main():
    import psycopg
    from ciq_api.config import Settings
    from psycopg import sql
    from sqlalchemy.engine import make_url

    settings = Settings()
    target = sys.argv[1]
    url = make_url(settings.database_url.get_secret_value())
    if (
        not settings.synthetic_workflows
        or settings.environment not in {"local", "test"}
        or settings.auth_mode != "local"
        or url.database != "cashlessiq"
        or url.host != "db"
        or not (
            target in {"source", "checkpoint"}
            or re.fullmatch(r"ciq_rehearsal_[a-f0-9]{24}", target)
        )
    ):
        raise ValueError("Expected synthetic MVP database and owned rehearsal target")
    with psycopg.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=url.database if target in {"source", "checkpoint"} else target,
        connect_timeout=3,
        options=(
            "-c statement_timeout=30000 -c lock_timeout=3000 "
            "-c idle_in_transaction_session_timeout=120000 -c timezone=UTC"
        ),
    ) as conn:
        conn.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        snapshot = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
        revision = conn.execute("SELECT version_num FROM alembic_version").fetchall()
        if revision != [("0003_mvp",)]:
            raise ValueError("Expected current MVP schema")
        tables = conn.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname COLLATE \"C\""
        ).fetchall()
        if not 10 <= len(tables) <= 100:
            raise ValueError("Unexpected MVP table inventory")
        manifest, total_bytes = {}, 0
        for (table,) in tables:
            columns = conn.execute(
                "SELECT a.attname, format_type(a.atttypid,a.atttypmod), a.attnotnull "
                "FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relname=%s AND a.attnum>0 "
                "AND NOT a.attisdropped ORDER BY a.attnum",
                (table,),
            ).fetchall()
            digest, count = hashlib.sha256(), 0
            with conn.cursor(name="recovery_rows") as rows:
                rows.execute(
                    sql.SQL(
                        "SELECT row_to_json(t)::text AS value FROM public.{} t "
                        'ORDER BY row_to_json(t)::text COLLATE "C"'
                    ).format(sql.Identifier(table))
                )
                for (value,) in rows:
                    data = value.encode("utf-8")
                    total_bytes += len(data)
                    count += 1
                    if total_bytes > 100 * 1024**2 or count > 100000:
                        raise ValueError("Synthetic rehearsal size limit")
                    digest.update(len(data).to_bytes(8, "big"))
                    digest.update(data)
            manifest[table] = {"columns": columns, "rows": count, "sha256": digest.hexdigest()}
        sample = conn.execute(
            "SELECT s.request_id, s.policy_id::text, d.id::text FROM submitted_case s "
            "JOIN review_case r USING(tenant_id, request_id) "
            "JOIN document_upload d USING(tenant_id, request_id) "
            "JOIN policy_active p ON p.tenant_id=s.tenant_id AND p.version_id=s.policy_id "
            "WHERE r.state='APPROVED_WITH_DEDUCTIONS' AND r.final_payable_inr=95000 "
            "AND d.state='extracted' AND d.extracted_text="
            "'Fictional policy wording for synthetic testing.' "
            "ORDER BY s.created_at DESC LIMIT 1"
        ).fetchone()
        result = {"manifest": manifest, "snapshot": snapshot}
        if sample:
            result["sample"] = dict(
                zip(("requestId", "policyId", "documentId"), sample, strict=True)
            )
        print(json.dumps(result), flush=True)
        if target == "source" and sys.stdin.readline().strip() != "release":
            raise ValueError("Snapshot owner disconnected")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # No SQL, connection details or submitted values belong in CI logs.
        print("MVP snapshot probe failed", file=sys.stderr)
        raise SystemExit(1) from None
