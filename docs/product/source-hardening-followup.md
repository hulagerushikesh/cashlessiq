# P2 hardening follow-up: read-only review

Date: 19 October 2026. Status: prepared; live review not yet received.

## Current boundary

CoCo reports reader/empty-secondary user defaults applied with grants unchanged.
Rushikesh's screenshot verifies that context after explicit USE commands, not
unmodified login defaults. No automatic-default verification is claimed.
PUBLIC still applies; the human retains administrative roles. Source HTTP is
disabled by default. This review does not provision a product service.

## Paste into CoCo

```text
Continue CashlessIQ P2 with a bounded READ-ONLY hardening follow-up. Do not rerun
the completed full grant review. Do not change any object, user, policy, grant,
credential or account setting. Administrative metadata visibility is permitted;
do not read case data, invoke AI, start apps/services/pools or resume warehouses.
Use at most 30 metadata statements; if insufficient, report remaining unknowns.
Do not query warehouse-backed history or scan every account object. If a useful
check would require compute, stop that check and describe what is missing.

Known: RUSHIKESH2001 now has stored defaults CIQ_PRODUCT_READER and empty
secondary roles; admin memberships remain. Explicit worksheet role/NONE context
is verified, but automatic login defaults are not. CIQ_PRODUCT_READER has 13
direct USAGE/SELECT grants on CIQ_WH, CASHLESSIQ and eight source tables.
PUBLIC inherits Cortex/AI, agent-task, learning and compute capabilities. No
source row-access policies exist. Only PREAUTH_FACTS.CLINICAL_NOTE is masked.

Return three sections:

1. HUMAN MFA: use SHOW MFA METHODS FOR USER RUSHIKESH2001 and supported metadata
inspection to distinguish enrolled methods from effective user/account
authentication-policy enforcement. Report method types/counts only, no method
identifiers, comments, factors, codes, keys or tokens. Inspect only relevant
policy metadata where visible without compute. Mark upstream IdP enforcement,
client/OAuth scope and any unavailable evidence unknown. Do not infer enforcement
from enrollment alone or password-only auth from absent key-pair flags. Give
owner-only enrollment instructions and lockout precautions; no policy changes.

2. PUBLIC IMPACT: using known grants and bounded metadata, identify which AI,
agent-task, learning and compute privileges are inherited by a new product
service. Distinguish direct from inherited grants. For proposed restrictions,
list possible dependencies of CoCo, CIQ_REVIEWER_APP and the connectivity spike,
replacement explicit roles/grants, verification tests and rollback prerequisites.
Metadata alone cannot prove an unused privilege: label those dependencies
unknown, not safe to revoke. No revocations or functional capability tests.

3. TENANT ISOLATION: compare per-TPA identities/roles and restricted secure views
against an independently governed row-access design. TPA001 owns GOL001;
TPA003 owns GOL024/GOL027. Join ownership through CORE.POLICY.TPA_ID; constrain
history, decisions and evidence through that relationship. Restrict clinical
columns/conditions by service privilege, not only application presentation.
Do not trust browser headers or caller-set session variables as tenant identity.
No service may read other tenants' views or base tables, change the ownership
mapping, assume another tenant's role or inherit operator/admin roles. New users
still inherit PUBLIC, so views alone cannot establish no-AI isolation.
List required negative tests and propose the smallest reversible implementation
for review. Consider a separate environment if shared PUBLIC cannot be safely
restricted, but do not buy/provision anything. Hosting is undecided: compare
supported workload identity vs managed key-pair prerequisites without creating
credentials. Separate synthetic local acceptance from production acceptance.

Finish with observed evidence, unknowns, recommended next change and its exact
approval boundary. Do not implement the recommendation automatically.
```

## Design recommendation pending review

Prefer explicit per-TPA service identities and tenant-specific read projections
as the initial candidate, with a separate privileged clinical path if needed.
Never reuse RUSHIKESH2001 OAuth in a server. The API must resolve its verified
membership to a fixed server-side credential/role mapping; never accept that
choice from a header. This is a proposal, not a configured security boundary.

Acceptance requires cross-tenant known-ID and broad-query rejection/absence,
base-table denial, alternate-role rejection, missing-recommendation fidelity,
clinical column/condition restrictions, credential revocation, unchanged legacy
apps and effective PUBLIC/AI review. Run functional tests only after separate
implementation/test approval, within a bounded synthetic and compute budget.

## Owner MFA step (separate interactive workflow)

Check the user menu, Settings, Authentication, Multi-factor authentication.
Inspect current methods before adding anything. If none are enrolled, follow
the supported enrollment flow yourself. Keep the current authenticated admin
session open and recovery material private; verify a second login before
closing it. Do not delete existing methods or change enforcement here.
Enrollment is not proof of enforcement across all authentication methods.

## Completion checklist

- [x] Follow-up scope prepared; no further mutations authorised.
- [ ] MFA enrollment and enforcement evidence returned (unknowns explicit).
- [ ] PUBLIC dependency/impact matrix returned without revocations.
- [ ] Tenant-isolation candidate and negative-test plan reviewed.
- [ ] Narrow implementation proposal approved before provisioning.

## References

- [SHOW MFA METHODS](https://docs.snowflake.com/en/sql-reference/sql/show-mfa-methods).
- [User MFA settings](https://docs.snowflake.com/en/user-guide/ui-snowsight-profile).
- [Authentication policies](https://docs.snowflake.com/en/user-guide/authentication-policies).
- [Secure views](https://docs.snowflake.com/en/user-guide/views-secure).
