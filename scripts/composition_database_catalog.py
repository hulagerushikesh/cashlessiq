"""Closed PostgreSQL 16 catalog assertion; never membership TLS readiness.

Executed once by the private bootstrap admin after the seed transaction commits.
Only catalog reads occur; a mismatch raises a redacted error and retains failure.
"""

CATALOG_SQL = b"""BEGIN READ ONLY;
SET LOCAL search_path = pg_catalog;
SET LOCAL statement_timeout = '3000ms';
DO $check$
DECLARE
    member_oid oid;
    relation record;
    col record;
BEGIN
    SELECT oid INTO STRICT member_oid FROM pg_authid
    WHERE rolname = 'membership_test' AND rolcanlogin
      AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit
               OR rolreplication OR rolbypassrls)
      AND rolpassword LIKE 'SCRAM-SHA-256$%';
    IF current_database() <> 'synthetic'
       OR EXISTS (SELECT FROM pg_auth_members WHERE pg_auth_members.member = member_oid)
    THEN
        RAISE EXCEPTION 'Disposable catalog denied';
    END IF;
    IF has_database_privilege(member_oid, 'synthetic', 'CONNECT') IS DISTINCT FROM true
       OR has_database_privilege(member_oid, 'synthetic', 'CREATE,TEMPORARY')
       OR has_schema_privilege(member_oid, 'ops', 'USAGE') IS DISTINCT FROM true
       OR has_schema_privilege(member_oid, 'ops', 'CREATE')
       OR has_schema_privilege(member_oid, 'public', 'USAGE,CREATE')
    THEN
        RAISE EXCEPTION 'Disposable catalog denied';
    END IF;
    IF (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='ops' AND c.relkind IN ('r','p','v','m','f','S')) <> 3
    THEN
        RAISE EXCEPTION 'Disposable catalog denied';
    END IF;
    FOR relation IN SELECT * FROM (VALUES
        ('tenant', ARRAY['id','active']),
        ('app_user', ARRAY['id','active']),
        ('tenant_membership', ARRAY['user_id','tenant_id','role','active'])
    ) AS expected(name, columns)
    LOOP
        IF NOT EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_roles r ON r.oid=c.relowner
            WHERE n.nspname='ops' AND c.relname=relation.name AND c.relkind='r'
              AND r.rolname='postgres' AND NOT c.relrowsecurity)
           OR has_table_privilege(member_oid, 'ops.' || relation.name,
                'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
           OR (SELECT count(*) FROM pg_attribute
               WHERE attrelid=('ops.' || relation.name)::regclass
                 AND attnum > 0 AND NOT attisdropped) <> cardinality(relation.columns)
        THEN
            RAISE EXCEPTION 'Disposable catalog denied';
        END IF;
        FOR col IN SELECT unnest(relation.columns) AS name
        LOOP
            IF has_column_privilege(member_oid, 'ops.' || relation.name, col.name,
                    'SELECT') IS DISTINCT FROM true
               OR has_column_privilege(member_oid, 'ops.' || relation.name, col.name,
                    'INSERT,UPDATE,REFERENCES,SELECT WITH GRANT OPTION')
            THEN
                RAISE EXCEPTION 'Disposable catalog denied';
            END IF;
        END LOOP;
    END LOOP;
END;
$check$;
COMMIT;
"""
