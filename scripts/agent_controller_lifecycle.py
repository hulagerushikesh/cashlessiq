"""Inactive, DISPOSABLE-CI-ONLY operator rehearsal; never an application service.

The caller owns the transaction and credentials. Nothing connects, commits,
creates a login, stages approval, enables a binding or alters agent accounting.
Production installation/peer isolation and secret delivery remain separate gates.
"""

import os
import re
import sys
from dataclasses import dataclass
from functools import wraps
from pathlib import Path

from psycopg import sql
from psycopg.pq import TransactionStatus

PACKAGES = Path(__file__).resolve().parents[1] / "deploy/agent-controller"
CLINICAL = ("capture(text)", "reserve_fake(text, integer)", "lease_fake(text, uuid, integer, uuid)")
CUSTODY = (
    "inventory_fake()",
    "checkpoint_fake(text, uuid, integer, uuid)",
    "issue_fake(text, uuid, integer, uuid, uuid)",
    "publication_context_fake(text, uuid, integer, uuid, uuid)",
    "heartbeat_submitted_fake(text, uuid, integer, uuid, uuid)",
    "publish_comparison_fake(text, uuid, integer, uuid, uuid, jsonb)",
    "recover_submitted_fake(text, uuid)",
    "recover_verified_fake(text, uuid)",
)
PRIVATE_CLINICAL = (
    "_capture_bound(oid, text)",
    "_reservation_context_for(oid, text)",
    "_reservation_context(text)",
)
PRIVATE_CUSTODY = (
    "_submission_context(text, uuid, integer, uuid, text)",
    "_recover_fake(text, uuid, boolean)",
)
ERROR = "fake_installation_rejected"


class InstallationRejected(ValueError):
    """Only a fixed policy category is exposed, never SQL/role/credential data."""


def require(condition, category):
    if not condition:
        raise InstallationRejected(f"{ERROR}:{category}") from None


@dataclass(frozen=True)
class RolePin:
    name: str
    oid: int


@dataclass(frozen=True)
class Target:
    database: str
    database_oid: int
    product: str
    capture: str
    receipts: str
    installer: RolePin
    clinical_definer: RolePin
    custody_definer: RolePin
    clinical: RolePin
    custody: RolePin


def guard(raw):
    # These checks precede all queries/DDL. No arbitrary or live target accepted.
    require(
        sys.platform == "linux"
        and os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_REPOSITORY") == "hulagerushikesh/cashlessiq"
        and os.environ.get("CIQ_AGENT_CONTROLLER_TEST") == "1"
        and raw.info.host == "127.0.0.1"
        and raw.info.port == 5432
        and re.fullmatch(r"ciq_controller_[0-9a-f]{24}", raw.info.dbname) is not None
        and raw.info.user == "postgres"
        and raw.info.password == "ciq-disposable-agent-ledger"
        and not raw.autocommit
        and raw.info.transaction_status == TransactionStatus.INTRANS,
        "disposable_target",
    )


def operator_savepoint(action):
    @wraps(action)
    def guarded(raw, *args, **kwargs):
        guard(raw)
        # An existing transaction is REQUIRED: this is only a nested SAVEPOINT.
        # Even a caller catching a policy failure cannot commit a partial install.
        with raw.transaction():
            return action(raw, *args, **kwargs)

    return guarded


def role_pin(raw, name):
    require(isinstance(name, str) and re.fullmatch(r"[a-z_][a-z_0-9]{0,62}", name), "name")
    row = raw.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (name,)).fetchone()
    require(row is not None, "role_identity")
    return RolePin(name, row[0])


def check_target(raw, target):
    guard(raw)
    row = raw.execute("SELECT oid FROM pg_database WHERE datname=current_database()").fetchone()
    require((raw.info.dbname, row[0]) == (target.database, target.database_oid), "database_pin")
    pins = (
        target.installer,
        target.clinical_definer,
        target.custody_definer,
        target.clinical,
        target.custody,
    )
    require(len({p.oid for p in pins}) == 5 and len({p.name for p in pins}) == 5, "separation")
    for pin in pins:
        require(role_pin(raw, pin.name) == pin, "role_identity")
    require(
        raw.execute(
            "SELECT current_user=session_user AND current_user=%s", (target.installer.name,)
        ).fetchone()[0],
        "installer_identity",
    )


def command(raw, verb, schema, signature, role):
    # All signatures are internal fixed constants. Identifiers never become SQL text.
    guard(raw)
    require(verb in ("GRANT", "REVOKE"), "command")
    require(signature in (*CLINICAL, *CUSTODY), "command")
    raw.execute(
        sql.SQL("{} EXECUTE ON FUNCTION {}.{} {} {}").format(
            sql.SQL(verb),
            sql.Identifier(schema),
            sql.SQL(signature),
            sql.SQL("TO" if verb == "GRANT" else "FROM"),
            sql.Identifier(role),
        )
    )


@operator_savepoint
def install_empty_fake(
    raw, *, product, capture, receipts, clinical, custody, clinical_definer, custody_definer
):
    """Install all six packages in ONE caller transaction, with EMPTY registries.

    Only fresh random disposable schemas/definers and existing dummy logins are
    accepted. A failed audit must abort the caller transaction, not be caught and
    committed. No production default ACL or migration is modified by this helper.
    """
    guard(raw)
    require(re.fullmatch(r"test_[0-9a-f]{32}", product) is not None, "product_schema")
    for name in (capture, receipts, clinical_definer, custody_definer):
        require(re.fullmatch(r"ciq_[a-z_]+_[0-9a-f]{24}", name) is not None, "fresh_name")
    require(len({product, capture, receipts, clinical_definer, custody_definer}) == 5, "separation")
    require(
        raw.execute(
            sql.SQL("SELECT version_num FROM {}.alembic_version").format(sql.Identifier(product))
        ).fetchone()
        == ("0005_agent_admission",),
        "schema_version",
    )
    for name in (clinical_definer, custody_definer):
        require(
            raw.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (name,)).fetchone() is None,
            "fresh_role",
        )
    for name in (capture, receipts):
        require(
            raw.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (name,)).fetchone() is None,
            "fresh_schema",
        )
    for file, owner in (
        ("scope-capture.sql", clinical_definer),
        ("reservation.sql", clinical_definer),
        ("receipt-observer.sql", custody_definer),
        ("custody-submission.sql", custody_definer),
        ("custody-publication.sql", custody_definer),
        ("custody-recovery.sql", custody_definer),
    ):
        raw.execute(
            sql.SQL((PACKAGES / file).read_text()).format(
                owner=sql.Identifier(owner),
                product=sql.Identifier(product),
                capture=sql.Identifier(capture),
                receipts=sql.Identifier(receipts),
            )
        )
    installer = raw.execute("SELECT current_user").fetchone()[0]
    target = Target(
        raw.info.dbname,
        raw.execute("SELECT oid FROM pg_database WHERE datname=current_database()").fetchone()[0],
        product,
        capture,
        receipts,
        role_pin(raw, installer),
        role_pin(raw, clinical_definer),
        role_pin(raw, custody_definer),
        role_pin(raw, clinical),
        role_pin(raw, custody),
    )
    # Only this NEW disposable database. Production PUBLIC/default ACL decisions
    # require a separately reviewed inventory and change, not this broad revoke.
    raw.execute(
        sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(target.database))
    )
    raw.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
    raw.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(sql.Identifier(product)))
    raw.execute(
        sql.SQL("REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA {} FROM PUBLIC").format(
            sql.Identifier(product)
        )
    )
    for creator in (target.installer, target.clinical_definer, target.custody_definer):
        for objects in ("TABLES", "SEQUENCES", "FUNCTIONS", "SCHEMAS"):
            raw.execute(
                sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} REVOKE ALL ON {} FROM PUBLIC").format(
                    sql.Identifier(creator.name), sql.SQL(objects)
                )
            )
            # Per-schema grants are ADDITIVE; a global revoke cannot undo them.
            if objects != "SCHEMAS":
                for schema in (product, capture, receipts):
                    raw.execute(
                        sql.SQL(
                            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
                            "REVOKE ALL ON {} FROM PUBLIC"
                        ).format(
                            sql.Identifier(creator.name), sql.Identifier(schema), sql.SQL(objects)
                        )
                    )
    for role, schema, signatures in (
        (clinical, capture, CLINICAL),
        (custody, receipts, CUSTODY),
    ):
        raw.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(target.database), sql.Identifier(role)
            )
        )
        raw.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(schema), sql.Identifier(role)
            )
        )
        for signature in signatures:
            command(raw, "GRANT", schema, signature, role)
    audit(raw, target)
    for schema, table in (
        (capture, "principal"),
        (capture, "reservation_scope"),
        (receipts, "principal"),
        (receipts, "submission_scope"),
    ):
        require(
            raw.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(
                    sql.Identifier(schema), sql.Identifier(table)
                )
            ).fetchone()[0]
            == 0,
            "empty_registry",
        )
    return target


# Exact effective product column rights, including the current whole-table grants.
# Never expand '*' from a drifted database: newly added columns need review too.
GRANT_COLUMNS = (
    "tenant_id id mode approval_ref operation_keys config_digest source_digest starts_at ends_at "
    "case_limit concurrency_limit units_per_attempt unit_limit admitted in_flight reserved_units "
    "consumed_units uncertain_units"
)
OPERATION_COLUMNS = (
    "tenant_id id request_id actor_id grant_id operation_key config_digest source_digest snapshot "
    "state version created_at deadline fence_id lease_until"
)
ATTEMPT_COLUMNS = "tenant_id id operation_id attempt_number submission_id fence_id submitted_at"
COMPARISON_COLUMNS = "tenant_id operation_id attempt_id candidate published_at"
CLINICAL_COLUMNS = {
    "tenant": ("id active", "", "id"),
    "app_user": ("id active", "", "id"),
    "tenant_membership": ("tenant_id user_id role active", "", "tenant_id"),
    "submitted_case": ("tenant_id request_id policy_id inputs record", "", "tenant_id"),
    "policy_version": ("tenant_id id proposal", "", "id"),
    "review_case": ("tenant_id request_id version state assignee_id", "", "tenant_id"),
    "case_input_revision": ("tenant_id request_id revision inputs digest", "", ""),
    "mvp_event": ("tenant_id subject_id action", "", ""),
    "agent_admission_epoch": ("id mode database_id epoch_id", "", "id"),
    "agent_execution_grant": (GRANT_COLUMNS, "", "admitted in_flight reserved_units"),
    "agent_operation": (OPERATION_COLUMNS, OPERATION_COLUMNS, "version fence_id lease_until"),
}
CUSTODY_COLUMNS = {
    "agent_admission_epoch": ("id mode database_id epoch_id", "", "id"),
    "agent_execution_grant": (
        "tenant_id id mode approval_ref starts_at ends_at case_limit concurrency_limit "
        "unit_limit units_per_attempt config_digest source_digest operation_keys "
        "in_flight reserved_units consumed_units uncertain_units",
        "",
        "id in_flight reserved_units consumed_units uncertain_units",
    ),
    "agent_operation": (OPERATION_COLUMNS, "", "state version lease_until"),
    "agent_attempt": (ATTEMPT_COLUMNS, ATTEMPT_COLUMNS, ""),
    "agent_comparison": ("", COMPARISON_COLUMNS, ""),
}


def routine_oids(raw, schema, signatures):
    result = set()
    for signature in signatures:
        name = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.SQL(signature)).as_string(raw)
        row = raw.execute("SELECT to_regprocedure(%s)::oid", (name,)).fetchone()
        require(row[0] is not None, "routine_inventory")
        result.add(row[0])
    return result


def routine_sources(raw, target):
    """Compare installed bodies/languages/results with these exact local packages."""
    sources = {}
    pattern = re.compile(
        r'CREATE FUNCTION "(?P<schema>[a-z_0-9]+)"\.(?P<name>[a-z_]+)\(.*?\) '
        r"RETURNS (?P<result>jsonb|void)\nLANGUAGE (?P<language>sql|plpgsql) .*?\n"
        r"AS (?P<tag>\$[a-z_]+\$)(?P<body>.*?)(?P=tag);",
        re.DOTALL,
    )
    for file, owner in (
        ("scope-capture.sql", target.clinical_definer),
        ("reservation.sql", target.clinical_definer),
        ("receipt-observer.sql", target.custody_definer),
        ("custody-submission.sql", target.custody_definer),
        ("custody-publication.sql", target.custody_definer),
        ("custody-recovery.sql", target.custody_definer),
    ):
        rendered = (
            sql.SQL((PACKAGES / file).read_text())
            .format(
                owner=sql.Identifier(owner.name),
                product=sql.Identifier(target.product),
                capture=sql.Identifier(target.capture),
                receipts=sql.Identifier(target.receipts),
            )
            .as_string(raw)
        )
        for match in pattern.finditer(rendered):
            values = match.groupdict()
            key = (values["schema"], values["name"])
            require(key not in sources, "source_inventory")
            sources[key] = (values["body"], values["language"], values["result"])
    names = {(target.capture, s.split("(")[0]) for s in (*CLINICAL, *PRIVATE_CLINICAL)} | {
        (target.receipts, s.split("(")[0]) for s in (*CUSTODY, *PRIVATE_CUSTODY)
    }
    require(set(sources) == names, "source_inventory")
    return sources


def audit(raw, target):
    """Read-only effective catalog review, including defaults; returns no authority.

    This is a point-in-time operator check. It is NOT protection against later
    trusted administrator/DDL changes, process compromise or live deployment proof.
    """
    check_target(raw, target)
    sources = routine_sources(raw, target)
    definitions = (target.clinical_definer, target.custody_definer)
    logins = (target.clinical, target.custody)
    pins = (*definitions, *logins)
    for pin in pins:
        row = raw.execute(
            "SELECT rolcanlogin,rolsuper,rolinherit,rolcreatedb,rolcreaterole,"
            "rolreplication,rolbypassrls FROM pg_roles WHERE oid=%s",
            (pin.oid,),
        ).fetchone()
        require(row == (pin in logins, False, False, False, False, False, False), "role_profile")
    require(
        not raw.execute(
            "SELECT 1 FROM pg_auth_members WHERE member=ANY(%s) OR roleid=ANY(%s) LIMIT 1",
            ([p.oid for p in pins], [p.oid for p in pins]),
        ).fetchone(),
        "role_membership",
    )
    expected = {
        target.capture: (
            target.clinical_definer,
            (*CLINICAL, *PRIVATE_CLINICAL),
            {"principal", "reservation_scope"},
        ),
        target.receipts: (
            target.custody_definer,
            (*CUSTODY, *PRIVATE_CUSTODY),
            {"principal", "submission_scope"},
        ),
    }
    function_sets = {}
    for schema, (owner, signatures, tables) in expected.items():
        require(
            raw.execute("SELECT nspowner FROM pg_namespace WHERE nspname=%s", (schema,)).fetchone()
            == (owner.oid,),
            "schema_owner",
        )
        functions = routine_oids(raw, schema, signatures)
        function_sets[schema] = functions
        rows = raw.execute(
            "SELECT p.oid,p.proowner,p.prosecdef,p.provolatile,p.proparallel,p.proleakproof,"
            "p.prokind,p.proconfig,p.proname,p.prosrc,l.lanname,t.typname,p.pronargdefaults,"
            "p.provariadic,p.proretset,p.prosupport::oid FROM pg_proc p "
            "JOIN pg_language l ON l.oid=p.prolang JOIN pg_type t ON t.oid=p.prorettype "
            "JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname=%s",
            (schema,),
        ).fetchall()
        require({row[0] for row in rows} == functions, "routine_inventory")
        for row in rows:
            require(
                row[1:7] == (owner.oid, True, "v", "u", False, "f")
                and set(row[7] or ())
                == {
                    "search_path=pg_catalog, pg_temp",
                    "row_security=on",
                    "lock_timeout=2s",
                },
                "routine_properties",
            )
            require(
                row[9:12] == sources[(schema, row[8])] and row[12:] == (0, 0, False, 0),
                "routine_source",
            )
            allowed_grantees = {owner.oid, target.installer.oid}
            runtime_pin = target.clinical if schema == target.capture else target.custody
            commands = CLINICAL if schema == target.capture else CUSTODY
            if row[0] in routine_oids(raw, schema, commands):
                allowed_grantees.add(runtime_pin.oid)
            if schema == target.capture and row[0] in routine_oids(
                raw, schema, ("_reservation_context_for(oid, text)",)
            ):
                allowed_grantees.add(target.custody_definer.oid)
            grantees = raw.execute(
                "SELECT a.grantee FROM pg_proc p CROSS JOIN LATERAL "
                "aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s",
                (row[0],),
            ).fetchall()
            require(all(r[0] in allowed_grantees for r in grantees), "routine_grantee")
        rows = raw.execute(
            "SELECT c.relname,c.relowner,c.relkind,c.relrowsecurity,c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s "
            "AND c.relkind NOT IN ('i','I')",
            (schema,),
        ).fetchall()
        require(
            {r[0] for r in rows} == tables
            and all(r[1:] == (owner.oid, "r", False, False) for r in rows),
            "private_inventory",
        )
        require(
            not raw.execute(
                "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a "
                "WHERE n.nspname=%s AND a.grantee NOT IN (%s,%s) LIMIT 1",
                (schema, owner.oid, target.installer.oid),
            ).fetchone(),
            "private_acl",
        )
        require(
            not raw.execute(
                "SELECT 1 FROM pg_attribute c JOIN pg_class t ON t.oid=c.attrelid "
                "JOIN pg_namespace n ON n.oid=t.relnamespace "
                "CROSS JOIN LATERAL aclexplode(c.attacl) a "
                "WHERE n.nspname=%s AND a.grantee NOT IN (%s,%s) LIMIT 1",
                (schema, owner.oid, target.installer.oid),
            ).fetchone(),
            "private_column_grantee",
        )
        schema_grantees = {
            owner.oid,
            target.installer.oid,
            (target.clinical if schema == target.capture else target.custody).oid,
        }
        if schema == target.capture:
            schema_grantees.add(target.custody_definer.oid)
        require(
            all(
                r[0] in schema_grantees
                for r in raw.execute(
                    "SELECT a.grantee FROM pg_namespace n CROSS JOIN LATERAL "
                    "aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a "
                    "WHERE n.nspname=%s",
                    (schema,),
                ).fetchall()
            ),
            "schema_grantee",
        )
    # Defaults apply to the role actually creating an object, not its later owner.
    # Check both global fallback defaults AND every additive per-schema entry.
    for creator in (target.installer, *definitions):
        for kind in ("r", "S", "f", "n"):
            rows = raw.execute(
                "SELECT a.grantee FROM aclexplode(coalesce((SELECT defaclacl "
                "FROM pg_default_acl WHERE defaclrole=%s AND defaclnamespace=0 "
                'AND defaclobjtype=%s),acldefault(%s::"char",%s))) a '
                "UNION ALL SELECT a.grantee FROM pg_default_acl d "
                "CROSS JOIN LATERAL aclexplode(d.defaclacl) a WHERE d.defaclrole=%s "
                "AND d.defaclobjtype=%s AND d.defaclnamespace<>0",
                (creator.oid, kind, kind, creator.oid, creator.oid, kind),
            ).fetchall()
            require(all(r[0] in (creator.oid, target.installer.oid) for r in rows), "default_acl")
    # Reject unexpected effective rights, including column-only grants and PUBLIC
    # grants on objects outside the three reviewed schemas.
    namespaces = raw.execute(
        "SELECT oid,nspname FROM pg_namespace WHERE nspname !~ '^pg_' "
        "AND nspname<>'information_schema'"
    ).fetchall()
    relations = raw.execute(
        "SELECT c.oid,n.nspname,c.relname,c.relkind FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname !~ '^pg_' "
        "AND n.nspname<>'information_schema' AND c.relkind IN ('r','p','v','m','f','S')"
    ).fetchall()
    routines = raw.execute(
        "SELECT p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'"
    ).fetchall()
    delegated = routine_oids(raw, target.capture, ("_reservation_context_for(oid, text)",))
    for pin in pins:
        is_clinical = pin == target.clinical
        own_schema = (
            target.capture if pin == target.clinical_definer or is_clinical else target.receipts
        )
        allowed_schemas = {own_schema}
        if pin in definitions:
            allowed_schemas.add(target.product)
        if pin == target.custody_definer:
            allowed_schemas.add(target.capture)
        for oid, schema in namespaces:
            privileges = raw.execute(
                "SELECT has_schema_privilege(%s,%s,'USAGE'),"
                "has_schema_privilege(%s,%s,'CREATE'),"
                "has_schema_privilege(%s,%s,'USAGE WITH GRANT OPTION')",
                (pin.oid, oid, pin.oid, oid, pin.oid, oid),
            ).fetchone()
            require(
                privileges
                == (
                    schema in allowed_schemas,
                    pin in definitions and schema == own_schema,
                    pin in definitions and schema == own_schema,
                ),
                "schema_acl",
            )
        if pin in logins:
            allowed_functions = routine_oids(raw, own_schema, CLINICAL if is_clinical else CUSTODY)
            require(
                raw.execute(
                    "SELECT has_database_privilege(%s,%s,'CONNECT'),"
                    "has_database_privilege(%s,%s,'CREATE,TEMP'),"
                    "has_database_privilege(%s,%s,'CONNECT WITH GRANT OPTION')",
                    (
                        pin.oid,
                        target.database_oid,
                        pin.oid,
                        target.database_oid,
                        pin.oid,
                        target.database_oid,
                    ),
                ).fetchone()
                == (True, False, False),
                "database_acl",
            )
        else:
            allowed_functions = function_sets[own_schema] | (
                delegated if pin == target.custody_definer else set()
            )
        for (oid,) in routines:
            rights = raw.execute(
                "SELECT has_function_privilege(%s,%s,'EXECUTE'),"
                "has_function_privilege(%s,%s,'EXECUTE WITH GRANT OPTION')",
                (pin.oid, oid, pin.oid, oid),
            ).fetchone()
            require(
                rights
                == (
                    oid in allowed_functions,
                    pin in definitions and oid in function_sets[own_schema],
                ),
                "routine_acl",
            )
        for oid, schema, name, kind in relations:
            if kind == "S":
                require(
                    not raw.execute(
                        "SELECT has_sequence_privilege(%s,%s,'USAGE,SELECT,UPDATE')", (pin.oid, oid)
                    ).fetchone()[0],
                    "sequence_acl",
                )
                continue
            if pin in definitions and schema == own_schema:
                continue  # Private owned tables are checked above.
            require(
                not raw.execute(
                    "SELECT has_table_privilege(%s,%s,'DELETE,TRUNCATE,TRIGGER,MAINTAIN')",
                    (pin.oid, oid),
                ).fetchone()[0],
                "table_acl",
            )
            policy = CLINICAL_COLUMNS if pin == target.clinical_definer else CUSTODY_COLUMNS
            grants = (
                policy.get(name, ("", "", ""))
                if (pin in definitions and schema == target.product)
                else ("", "", "")
            )
            for index, privilege in enumerate(("SELECT", "INSERT", "UPDATE", "REFERENCES")):
                allowed = set(grants[index].split()) if index < 3 else set()
                columns = raw.execute(
                    "SELECT attname,has_column_privilege(%s,attrelid,attnum,%s),"
                    "has_column_privilege(%s,attrelid,attnum,%s) FROM pg_attribute "
                    "WHERE attrelid=%s AND attnum>0 AND NOT attisdropped",
                    (pin.oid, privilege, pin.oid, privilege + " WITH GRANT OPTION", oid),
                ).fetchall()
                for column, actual, grantable in columns:
                    require(
                        (actual, grantable) == (column in allowed, False),
                        "column_acl",
                    )
    return None


@operator_savepoint
def revoke_fake(raw, target, *, clinical):
    """Explicit trusted revocation, epoch first; bounded wait and atomic rollback.

    Already completed/I/O work cannot be undone. No refunds, retries, deadline or
    receipt rewrites. Clinical revocation preserves independent custody status.
    Existing idle sessions need no cooperation to lose these command capabilities.
    """
    check_target(raw, target)
    require(type(clinical) is bool, "role_selector")
    raw.execute("SET LOCAL lock_timeout='2s'")
    require(
        raw.execute(
            sql.SQL("SELECT mode FROM {}.agent_admission_epoch WHERE id=1 FOR UPDATE").format(
                sql.Identifier(target.product)
            )
        ).fetchone()
        == ("fake-only",),
        "epoch",
    )
    pin = target.clinical if clinical else target.custody
    schema = target.capture if clinical else target.receipts
    raw.execute(
        sql.SQL("UPDATE {}.principal SET enabled=false WHERE login_oid=%s").format(
            sql.Identifier(schema)
        ),
        (pin.oid,),
    )
    table = "reservation_scope" if clinical else "submission_scope"
    raw.execute(
        sql.SQL("UPDATE {}.{} SET enabled=false WHERE login_oid=%s").format(
            sql.Identifier(schema), sql.Identifier(table)
        ),
        (pin.oid,),
    )
    raw.execute(
        sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
            sql.Identifier(schema), sql.Identifier(pin.name)
        )
    )
    raw.execute(
        sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(
            sql.Identifier(schema), sql.Identifier(pin.name)
        )
    )
    raw.execute(
        sql.SQL("REVOKE ALL ON DATABASE {} FROM {}").format(
            sql.Identifier(target.database), sql.Identifier(pin.name)
        )
    )
    raw.execute(sql.SQL("ALTER ROLE {} NOLOGIN").format(sql.Identifier(pin.name)))
