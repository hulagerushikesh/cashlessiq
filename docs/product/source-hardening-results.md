# P2 hardening results and isolation proposal

Date: 19 October 2026. Status: partial live review; no remediation performed.

## Latest checkpoint — owner passkey enrolled

Rushikesh reports enrolling a passkey. A subsequent independent local reader
OAuth connection executed three bounded metadata/session statements: USE
SECONDARY ROLES NONE, SHOW MFA METHODS and DESCRIBE USER RUSHIKESH2001.
Snowflake returned one method of type PASSKEY and HAS_MFA true. Stored defaults
remain CIQ_PRODUCT_READER and [] secondary roles. Only method count/type and
allowlisted user properties were printed; no factor identifiers or secrets.
The connection closed without source reads, AI, writes or app startup.

Enrollment is verified; the zero-method observation below is historical.
Effective authentication-policy enforcement and a second interactive login
with the passkey remain unverified. The existing OAuth connection does not
prove that the passkey was required or used. No authentication policy or grant
was changed by this verification.

## Independently observed metadata

Two explicit local OAuth connections used CIQ_PRODUCT_READER. Each disabled
secondary roles before inspection; no admin fallback was attempted. Nine SQL
statements total: two session guards, one session-context SELECT, SHOW MFA
METHODS, DESCRIBE USER, two SHOW GRANTS TO ROLE PUBLIC calls, SHOW WAREHOUSES
LIKE 'CIQ_WH', and SHOW AUTHENTICATION POLICIES IN ACCOUNT. Only metadata was
read. Connections closed. No AI, source-table reads, writes or app startup ran.
The second PUBLIC inspection repeated the first after its 100-row safety cap
was exceeded; the retry was bounded at 1,001 fetched rows. No raw user/MFA
descriptions, authentication factors, tokens or connection settings were logged.

| Check | Observed | Limit |
| --- | --- | --- |
| Stored DEFAULT_ROLE | CIQ_PRODUCT_READER | Verified independently with DESCRIBE USER |
| Stored DEFAULT_SECONDARY_ROLES | [] | Verified independently |
| Explicit session | RUSHIKESH2001, reader, secondary roles empty | Connector selected reader and guard selected NONE; not an unmodified login test |
| Enrolled MFA methods | 0; HAS_MFA false | Enrollment only; upstream IdP and effective policy enforcement not established |
| Visible authentication policies | 0 under reader role | Not proof no policy exists/applies; administrative visibility still needed |
| PUBLIC direct grants visible | 109 | Complete within fetch cap, but SHOW visibility may omit other metadata |
| CIQ_WH | SUSPENDED, X-Small, 0 started clusters/running/queued, auto-suspend 60 | Observed after first connection; second connection issued only session/SHOW metadata commands |

No current trial balance or exact incremental dollar charge is inferred.
The $205 planning baseline and $50 reserve are unchanged.

## PUBLIC inventory and impact

The 109 visible direct rows comprise 5 account privileges, 1 application role,
2 compute pools, 1 database, 12 database roles, 1 account role, 6 schemas,
80 tables and 1 warehouse. This supersedes the earlier reported count of 11
database roles; do not infer when or why the count changed.

PUBLIC directly holds USE AI FUNCTIONS, EXECUTE AGENT TASK, BIND SERVICE ENDPOINT,
MANAGE ARTIFACT PUBLICATION and VIEW LINEAGE. It has USAGE on both system CPU/GPU
pools, SYSTEM$STREAMLIT_NOTEBOOK_WH and SNOWFLAKE_SAMPLE_DATA. Its database-role
memberships include CORTEX_USER, COPILOT_USER, ML_USER, DATA_METRIC_USER,
ANACONDA_REPOSITORY_USER, PYPI_REPOSITORY_USER and six viewer roles. It also
inherits SNOWFLAKE_LEARNING_ROLE. Inherited role contents were not retraced in
this bounded pass; prior CoCo findings remain attributed to that supplied report.

| Surface | Potential dependency / repository evidence | Before any restriction |
| --- | --- | --- |
| AI/Cortex/Copilot | Reviewer app calls DATA_AGENT_RUN; CoCo/Copilot may depend on PUBLIC. SQL 00 explicitly grants CORTEX_AGENT_USER to CIQ_APP_USER, not proof all needed capabilities are explicit | CoCo must reconcile exact runtime roles and supported AI privileges; prepare replacement explicit grants and functional rollback tests |
| CPU/GPU pool USAGE | snowflake.yml specifies system CPU pool; SQL 62 explicitly grants CPU USAGE to CIQ_ADMIN. GPU dependency unknown | Verify live owner/caller privileges and the connectivity spike configuration without starting either app; CPU explicit grant alone does not prove PUBLIC removal safe |
| System notebook warehouse, learning and package roles | Interactive notebooks, tutorials and package provisioning may depend on these; actual use unknown | Identify users/apps and intended explicit replacement roles, including artifact/build paths |
| Agent tasks / endpoint binding / artifact publication | Expanded service surface; necessary companion privileges and actual consumers unknown | Review exact privilege semantics and deployment dependencies; do not test by creating or invoking services |
| Lineage / viewer / sample-data access | Metadata/tutorial capabilities; not evidence of writes to CASHLESSIQ | Classify required access and governance exposure separately from AI restrictions |

These are impact hypotheses, not a revocation plan approved for execution.
Runtime smoke tests and new grants themselves can cost credits or alter access;
neither is authorised by this review. A new role/user still inherits PUBLIC.

## Tenant-isolation proposal — not provisioned

Prefer per-TPA service identities/roles with tenant-specific secure projections
as the first candidate for this small synthetic slice. The API must resolve a
verified database membership to a fixed server-side identity; browser headers,
query parameters and caller-set session variables cannot choose that identity.
Each identity must lack other tenant roles, base-table access, mapping writes,
view ownership and operator/admin memberships. View ownership belongs to a
separately governed owner role, never the runtime. Shared PUBLIC remains an
independent unresolved surface, not something secure views remove.

| Read model | Required ownership boundary |
| --- | --- |
| Queue/case | PREAUTH_REQUEST to POLICY to TPA_ID; explicit nonclinical columns only |
| Member/claims | Resolve policy ownership first; claims restricted by policy; member conditions require medical privilege and verified member ownership |
| Saved recommendation | DECISION to request to policy owner; absent remains MISSING; raw DECISION_JSON may contain clinical text and cannot be granted broadly |
| Evidence | Resolve the authorised policy product before clause references; no unconstrained product/tenant browsing |

Member-condition sharing across policies must be assessed explicitly: MEMBER_ID
alone is not a tenant identity. The nonmedical service must not receive raw
conditions/clinical prose merely because the API would hide them. Our current
canonical decision validation consumes raw decision JSON internally; choose a
restricted clinical adapter or a governed validation/projection boundary before
claiming database-level clinical separation. Do not weaken canonical validation
or invent sanitized saved decisions to resolve this design gap.

An independently governed row-access policy is the alternative when shared
relations/tenant counts justify it. It requires trustworthy runtime identity,
complete attachment coverage, protected mapping tables and equivalent negative
tests; it does not by itself restrict clinical columns or PUBLIC AI capability.
Secure views must likewise be reviewed for their predicates and grants: the
SECURE keyword alone does not enforce tenant ownership.

Acceptance tests after separate implementation/test approval:

1. Own-tenant reads succeed; GOL001 cannot be accessed by TPA003 and GOL024/027
   cannot be accessed by TPA001, including broad queries without app predicates.
2. Other-tenant views, all eight base tables and alternate tenant/admin roles
   are denied to each service identity; inherited/direct-user grants reviewed.
3. Nonmedical identity cannot retrieve conditions, raw decision JSON or clinical
   fields through any granted view/path; unknown identity fails closed.
4. MISSING source decisions stay missing, invalid saved data stays an error,
   and revoked service credentials/membership cannot continue new reads.
5. Existing legacy app/CoCo dependencies survive any separately approved PUBLIC
   change; reversal script restores captured grants without changing other roles.

Hosting/authentication remains undecided: WIF depends on supported hosting and
provider trust; managed key pairs need a secret store, rotation/revocation and
no private keys in the repository. Human OAuth is not an unattended credential.
If shared-account PUBLIC cannot be restricted safely, assess an isolated
environment without purchasing/provisioning it or exceeding the credit reserve.

## Exact next boundary

Owner enrollment is now verified above. Preserve the working admin session
and recovery material. Verify a second login; never send factors/codes.
No enforcement change or role revocation is implied.

CoCo administrative follow-up is still needed for effective user/account
authentication-policy metadata and the live runtime dependency matrix. Ask for
metadata only, no case data/compute or automatic remediation. A report of no
visible policy under reader is not sufficient enforcement evidence.

No service identity, secure view, row-access policy, credential or PUBLIC grant
change is approved here. P2 remains open and P3 is not started. Continue local
offline work within existing boundaries; do not enable source HTTP/UI yet.

## References

- [Enrolled MFA method metadata](https://docs.snowflake.com/en/sql-reference/sql/show-mfa-methods).
- [Authentication policy enforcement](https://docs.snowflake.com/en/user-guide/authentication-policies).
- [PUBLIC inheritance](https://docs.snowflake.com/en/user-guide/security-access-control-overview).
- [Secure view behaviour](https://docs.snowflake.com/en/user-guide/views-secure).
