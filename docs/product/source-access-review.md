# P2 source-access review packet

Date: 19 October 2026  
Status: repository/design review prepared; **live CoCo review pending**.

## Decision boundary

The operator spike passed three-case repository parity. This does not approve
an unattended service identity, public source endpoints, customer data, or
production tenant isolation. HTTP source reads remain disabled by default and
repository injection is restricted to local/test. No grant, identity, policy,
resource or deployment change is authorised by this packet.

Keep the existing human OAuth operator connection only for explicit bounded
synthetic checks. Do not copy its credentials into API containers or the public
site. Do not treat a server-supplied TPA predicate as database-enforced isolation.

## Known evidence, not a new live inspection

- CIQ_PRODUCT_READER has 13 previously verified direct privileges: USAGE on
  CIQ_WH, CASHLESSIQ and APP/CORE/DOCS schemas; SELECT on the eight objects below.
- Its only reported grantee is RUSHIKESH2001, with no grant options. Direct grant
  reports are not a complete effective-privilege or production-security verdict.
- Prior PUBLIC inspection found AI/Cortex and other capabilities. Secondary
  roles NONE does not remove PUBLIC inheritance. Under the current documented
  UBAC model, direct user privileges are considered with secondary roles ALL;
  disabling them does not revoke grants or prevent the human from switching
  roles later. CoCo must verify the account's actual behaviour/settings.
- The repository allows only TPA001/GOL001 and TPA003/GOL024,GOL027, using separate
  application tenant UUIDs. These are application guards, not Snowflake RLS.
- GOL001 has a validated saved recommendation; GOL024/GOL027 explicitly lack one.
  No source backfill is required or authorised.

| Required source | Purpose |
| --- | --- |
| CORE.POLICY | Owner, product/member context and cover metadata |
| CORE.POLICY_PRODUCT | Product name/version |
| DOCS.PREAUTH_REQUEST | Request-to-policy relationship |
| DOCS.PREAUTH_FACTS | Admission date and supplied estimate |
| CORE.CLAIM | Bounded prior-claim aggregate |
| CORE.MEMBER_CONDITION | Role-restricted condition history |
| APP.DECISION | Latest saved recommendation, revalidated locally |
| DOCS.POLICY_CLAUSE | Scoped clause-reference register |

All objects are in CASHLESSIQ. No MEMBER demographic table, stage, procedure,
agent, search service or new future/all-table grant is required by this slice.

## Paste this entire prompt into CoCo

```text
Perform a READ-ONLY security review for CashlessIQ product P2. Do not create,
alter, grant, revoke, drop, seed, deploy, run AI/extraction, or start Streamlit,
search or compute pools. Do not fix findings automatically. Do not request or
print passwords, tokens, keys, raw decision JSON or clinical rows. No local
repository attachment is needed: all review context is below.

Known role CIQ_PRODUCT_READER is held only by operator RUSHIKESH2001. Expected
13 direct grants are USAGE on CIQ_WH, CASHLESSIQ, schemas CASHLESSIQ.APP/CORE/DOCS,
and SELECT on CASHLESSIQ.CORE.POLICY, CORE.POLICY_PRODUCT, CORE.CLAIM,
CORE.MEMBER_CONDITION, DOCS.PREAUTH_REQUEST, DOCS.PREAUTH_FACTS,
DOCS.POLICY_CLAUSE, APP.DECISION. No grant option or inherited runtime/admin role
is intended. Direct grants alone do not prove effective read-only/no-AI access.

Use administrative visibility only for metadata inspection, not application
data reads. Inspect SHOW GRANTS TO ROLE CIQ_PRODUCT_READER;
SHOW GRANTS OF ROLE CIQ_PRODUCT_READER; SHOW GRANTS TO ROLE PUBLIC;
SHOW GRANTS TO USER RUSHIKESH2001; and SHOW GRANTS OF ROLE PUBLIC.
Follow relevant inherited account/database roles to establish effective access;
report visibility gaps rather than treating absent SHOW rows as proof. Inspect
relevant secondary-role/UBAC settings and enabled behaviour changes read-only.
Avoid warehouse-backed account-history queries unless necessary; ask first if
the metadata review cannot be completed without them. Do not test AI access by
calling an AI function, or test writes by attempting a write.

The local repository binds ownership to CORE.POLICY.TPA_ID. Separate app tenants
allow only TPA001/GOL001 and TPA003/GOL024,GOL027; unknown/cross-owner IDs do no I/O.
This is synthetic-only application filtering, NOT Snowflake tenant RLS. Current
sessions explicitly use CIQ_PRODUCT_READER and USE SECONDARY ROLES NONE. Prior
PUBLIC inspection found Cortex/USE AI FUNCTIONS and other capabilities.

Return: (1) actual direct grant delta and all role grantees, (2) effective PUBLIC,
inherited-role and direct-user access with activation conditions, (3) whether
the current human operator connection is acceptable ONLY for explicitly
supervised local synthetic checks, (4) a proposed least-privilege service design
with database-enforced tenant isolation, and (5) findings blocking any customer
or unattended deployment. Mark unknowns explicitly; do not declare production
readiness from the three-case allowlist.

For the proposed service design, compare per-TPA service identities/roles with
restricted secure views against an independently governed row-access design.
Do not trust a browser header or a caller-set session variable as a tenant
identity. A secure view alone does not provide isolation if all tenants can
read it or its base tables. Require cross-tenant and base-table-bypass negative
tests, no direct base-table grants to the service, and reviewed PUBLIC access.
Prefer workload identity federation if the eventual hosting supports it;
otherwise evaluate managed key-pair authentication/rotation. Hosting is not
selected, so do not create a user or choose cloud-specific configuration yet.
Neither a new service user nor secondary roles NONE removes PUBLIC privileges.

Do not revoke PUBLIC grants: existing Streamlit, CoCo and tools may depend on
them. Any remediation needs a separate impact review and human approval. If
strict service isolation cannot be achieved safely in this shared trial account,
recommend an isolated environment rather than weakening the requirement.
End with proposed changes and tests ONLY, requiring approval before execution.
```

## Review acceptance checklist

- [ ] CoCo report received; review date and metadata-visibility limits recorded.
- [ ] All direct grants, grantees and inherited roles reconciled.
- [ ] PUBLIC and direct-user access distinguished from inactive secondary roles.
- [ ] Supervised synthetic-only use explicitly assessed; no production waiver.
- [ ] Proposed service authentication and tenant-isolation design reviewed.
- [ ] Required remediation/change approval identified; no broad revocations run.

The review does not itself provision a service. Production acceptance separately
requires approved authentication, effective-privilege evidence, database-enforced
cross-tenant/base-table denial tests, credential rotation/revocation, query limits,
and deployment/privacy gates. Existing API membership/revocation tests remain
necessary but are not substitutes for those database checks.

## References

- [Current progress](progress.md) and [P2 evidence](phase-p2-checklist.md).
- [Snowflake access control / UBAC](https://docs.snowflake.com/en/user-guide/security-access-control-overview).
- [Secondary roles](https://docs.snowflake.com/en/sql-reference/sql/use-secondary-roles).
- [SHOW GRANTS visibility](https://docs.snowflake.com/en/sql-reference/sql/show-grants).
- [Inbound workload identity federation](https://docs.snowflake.com/en/user-guide/workload-identity-federation).
