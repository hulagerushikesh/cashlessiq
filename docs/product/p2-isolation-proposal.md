# P2 source isolation: review-only implementation proposal

Date: 19 October 2026. Status: **draft for approval, not executable or applied**.
Scope: three synthetic cases, two TPAs, read-only P2. Website deployment and P3
are excluded. Approval to prepare this document is not approval to provision.

## Recommendation

Use explicit tenant-specific read projections for this bounded alpha, with
separate nonclinical and medical runtime identities for each TPA. Keep a
governed saved-decision validation boundary separate from ordinary read access.
Do not modify PUBLIC, existing source tables, legacy roles or account login
policies as part of this increment. Unresolved PUBLIC access blocks any claim
that these identities have no AI/compute capabilities.

No new account, paid environment, credentials, schemas, roles, views, policies,
source writes, source activation or functional Snowflake tests are authorised.
The existing operator OAuth connection must not become a backend credential.

## Reconciliation of the supplied CoCo report

The owner supplied a 363-line report dated 19 October, reporting 28 metadata
statements and no mutations. Its observations are attributed to CoCo, not
independently re-executed here. Prior passkey/default checks remain independent
evidence; no fresh Snowflake connection was made for this proposal.

| Report item | Disposition |
| --- | --- |
| No account authentication/session policies reported | Useful inventory, but effective user policy visibility and built-in defaults remain unresolved; not proof MFA is absent |
| OAuth/drivers categorically have no MFA | Not established across actual flows; inspect effective policy, client/authentication path and upstream controls before claiming coverage or bypass |
| Authentication policy allows PASSWORD/SAML only | Do not apply: restrictive allowlists can break other login paths; a recovery-tested change needs separate approval |
| Client type SNOW_SQL | Not the documented SNOWSQL value; SNOWFLAKE_CLI is separately documented |
| Row-access policies cannot query ownership tables | Incorrect: mapping-table subqueries are supported; retain RAP as a viable alternative |
| PUBLIC grants are safe to restrict | Not established by metadata; all replacement/dependency/rollback tests remain prerequisites |
| Database-role inventory | Report lists 12 names but summarizes 11; reconcile before using totals for acceptance |
| Mask bypass with secondary roles | Privileged roles intentionally permit cleartext; reader/NONE defaults reduce accidents, not the human admin's authority |
| Scalar decision view is validated | A stored SCHEMA_VALID flag or extracted JSON scalar is not fresh canonical validation |
| New isolated account recommended | Option only, not required or approved; do not purchase/provision against the trial budget |

Live definitions must be checked against repository DDL before writing grants
or projections; report prose is not an executable column specification. Existing
repository decision row PAYABLE_INR is NOT NULL, whereas uncomputed QUERY/REFER is exposed as null
only after canonical validation. Do not change source storage to match the UI.

References checked against official documentation:
[authentication policy syntax and warnings](https://docs.snowflake.com/en/sql-reference/sql/create-authentication-policy),
[MFA hardening](https://docs.snowflake.com/en/user-guide/authentication-policies),
[mapping-table row policies](https://docs.snowflake.com/en/user-guide/security-row-using).
Rollout-dependent authentication behaviour remains account-specific.

## Trust boundary and proposed principals

Fresh API JWT verification and PostgreSQL membership resolution precede every
source request. A fixed, server-owned mapping selects tenant and disclosure
class. The browser cannot select credentials, role, TPA or clinical privilege.
Unknown/revoked membership fails before source I/O. Role changes require a new
authorisation decision; pooled connections must never leak prior tenant state.

Proposed names below are inventory labels, not created Snowflake identifiers:

| Principal class | Count | Permitted source surface |
| --- | --- | --- |
| Nonclinical read service | Two, one per TPA | Own metadata/history and approved nonclinical validated projection only |
| Medical read service | Two, one per TPA | Own read surface plus separately approved clinical projection |
| Governance owner | Separate from runtime | Own projection definitions and controlled validation boundary; never assigned to runtime users |

Processor and auditor share the nonclinical source disclosure class; application
membership remains distinct. Medical service credentials must not be present in
nonclinical deployments/workers. A single process possessing every credential
does not establish process-level clinical isolation; deployment/secret boundaries
need review before activation. A read service gets no ownership, grant option,
source writes, mapping writes, other tenant roles or admin/operator membership.
Capture effective privileges including PUBLIC and direct user grants, not just
the new role's direct grants. No future-table/all-table wildcard grants.

## Projection inventory and ownership predicates

Use explicit column allowlists, never SELECT *. Retain the three-case manifest
in addition to TPA ownership for this alpha; this is not a general entitlement
registry. Any duplicate, ambiguous, missing or changed ownership fails closed.
Do not rely on declared foreign/primary keys as proof of actual data uniqueness.

| Logical read model | Ownership and permitted content |
| --- | --- |
| Queue/request | REQUEST -> POLICY.TPA_ID and allowlisted REQUEST_ID; identifiers, policy/product version, dates and supplied estimate; no file path/raw facts |
| Policy/product | POLICY.TPA_ID then authorised PRODUCT_ID; explicit policy and product metadata; shared products do not permit another tenant's policy access |
| Claim history | CLAIM.POLICY_ID -> owned POLICY; recorded financial/date/status fields only; exclude ICD10_CODE for nonclinical reads |
| Conditions | Medical-only; MEMBER_ID must resolve to the owned policy/member pair; cross-TPA member ambiguity is unavailable until a governed provenance decision, not implicit sharing |
| Recommendation | DECISION.REQUEST_ID -> owned REQUEST -> POLICY; no raw DECISION_JSON through ordinary nonclinical access |
| Clause register | Owned request -> policy product -> POLICY_CLAUSE; ID/title/page/source metadata only until text access is separately approved |

Nonclinical exclusions include diagnoses, ICD codes, procedures, clinical notes,
RAW_EXTRACT, COST_BREAKUP, free-text reasons, condition details and raw decision
JSON. A monetary total is not permission to return its clinical descriptions.
URLs must come from the approved policy-product source, not request input or
raw document paths. References are not proof of narrative grounding.

Secure views are a candidate because predicates can be audited for this small
slice; SECURE alone is not tenant isolation. RAP with protected mapping-table
subqueries remains an alternative, subject to supported syntax/performance and
complete attachment coverage. Neither approach solves column disclosure,
PUBLIC inheritance, application membership or credential isolation on its own.

## Saved recommendation and financial-trace boundary

Keep the current canonical Python validator authoritative. Do not duplicate
arithmetic in SQL/TypeScript/LLM, trust SCHEMA_VALID, or synthesize a sanitized
decision and validate that in place of the full saved decision.

Recommended next design: a narrow tenant-scoped trusted validation component
can read the full saved decision and independently owned evidence, run canonical
validation, and return only an allowlisted immutable observation. Ordinary
nonclinical readers cannot access its raw inputs. This is a proposed service
boundary, not implemented validation inside a secure view.

Before any implementation approval, settle the component's hosting, identity,
invocation authorisation, clinical trust, package/runtime support and secret
isolation. It must validate current saved content on each read, or bind cached
results to decision/content/evidence versions and invalidate on any change.
Cached flags without trustworthy provenance are unacceptable. Do not add a
persisted projection table/backfill under P2's current read-only permission.

Initially return the existing v2 summary only. Full financial lines need a
separately approved contract for line identifiers, integer recorded amounts,
deductions and independently resolved citations; free text may be clinical.
Do not add financial trace fields or weaken validation in this document change.

Required states: valid saved -> SAVED; truly absent decision -> MISSING;
malformed, ambiguous, stale or unresolved evidence -> unavailable/error.
No replacement demo decision, AI call, zero-payable fiction or DENY outcome.
QUERY/REFER retain canonical uncomputed/null-payable semantics. Approved line
citations must resolve within the owned product/record registry; product clause
counts alone cannot prove reasons are supported.

## Authentication is a separate change stream

Prefer workload identity when the eventual host supports it; otherwise assess
managed key-pair authentication with an approved secret store, rotation and
revocation. No keys or credentials are created in this proposal. Local operator
OAuth is supervised inspection only. Keep the $50 reserve; do not open a paid
account or exhaust credits to resolve a design gap.

For human MFA, first reconcile actual effective policies and client paths.
Then prepare a user-scoped canary proposal before account-wide rollout, including
passkey/SSO/OAuth/CLI/connector compatibility, a second verified admin/recovery
path, captured original attachments and a tested rollback. Do not assume
unsetting a policy restores a prior attachment or disables built-in MFA.
Existing active sessions may not prove a new-login policy works. Demo-user
defaults and masking changes require separate named targets/approvals.

## Ordered implementation and approval packets

1. **Review now:** approve or revise this architecture only. Nothing applied.
2. **Preflight proposal:** CoCo reconciles the report's count/policy/definition
   gaps with a separately bounded metadata plan. No compute or mutation implied.
3. **DDL/auth package:** after validation-host and credential decisions, prepare
   numbered SQL, exact principal/object/column inventories, captured before state,
   grants and rollback for CoCo review. Mark uncertain syntax
   `-- VERIFY WITH COCO: <specific question>`. No auto-run Makefile hooks.
4. **Provisioning approval:** owner explicitly approves exact reviewed objects,
   service credential custody, synthetic-only scope and rollback. PUBLIC and
   account login changes are excluded unless separately named and approved.
5. **Test approval:** request a hard statement/time/credit cap before functional
   Snowflake reads. Stop on unexpected capabilities/cross-tenant disclosure;
   close connections and suspend only task-owned compute as authorised.
6. **Local live acceptance:** only after isolation tests pass, opt in source
   identities and verify API/UI parity. No website deployment. Review P2 exit
   and remote CI after separately approved push; do not start P3 automatically.

## Acceptance matrix (planned; none newly executed)

| Test | Required evidence |
| --- | --- |
| Own-tenant reads | TPA001 GOL001; TPA003 GOL024/027; recorded summary/history matches independent expectations |
| Broad query / known foreign ID | Other TPA data absent or denied without application WHERE predicates |
| Direct bypass | Eight base tables, other tenant projections, admin/alternate roles, mapping/definition writes denied |
| Clinical separation | Nonclinical credentials cannot retrieve excluded fields, conditions or raw decisions through any granted path; medical path remains same-tenant |
| Shared member/product | Ambiguous member ownership fails closed; shared product does not widen case access |
| Bad/stale recommendation | Canonical/schema/arithmetic/citation failures produce unavailable, never MISSING or fixture fallback |
| Missing recommendation | GOL024/027 remain MISSING; no AI/backfill or invented outcome |
| Membership/credential revocation | New reads stop; cached results/pooled connections do not bypass current authorisation |
| PUBLIC and login | Effective inherited capabilities documented; no no-AI claim until resolved; approved login paths/recovery tested separately |
| Regression/rollback | Legacy app/CoCo dependencies tested only under approved budget; restore exact captured state, not broad DROP/REVOKE commands |

The existing 15 fake-gateway API/UI tests are not these database isolation tests.
Record query IDs, assertion outcomes, timestamps and bounded cost observations,
not raw clinical payloads, credentials or factor identifiers. A failed test
blocks source activation. For rollback, disable the new source path first,
revoke only newly approved runtime access, restore any modified attachment to
its captured original, and remove only exact new objects after dependency review.
