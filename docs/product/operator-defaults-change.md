# Approved operator-default change

Date: 19 October 2026. Approved by Rushikesh in chat; CoCo reports applied and
stored values verified. Independent fresh-session verification remains pending.
This packet belongs to P2 and does not authorise P3 or production use.

## CoCo execution prompt

The following is retained as the execution specification, not a request to rerun
the change. Keep the existing administrative session open until a fresh login
is verified.

```text
Rushikesh approved exactly two user-default changes for RUSHIKESH2001:
DEFAULT_ROLE = CIQ_PRODUCT_READER and DEFAULT_SECONDARY_ROLES = ().

First inspect the user's current defaults and role grants using metadata only.
Report only the two defaults and relevant role memberships, not credentials or
the full user description. Verify CIQ_PRODUCT_READER and the existing admin
roles remain granted. Previously reported defaults were ACCOUNTADMIN and ALL;
if the current state differs, explain it and stop before applying changes.
Explain any known Snowsight/CLI impact: a tool explicitly selecting another
role or a reused session may not follow these defaults. Do not alter local
connection settings or authentication integrations. Stop if you identify an
unexpected authentication/access risk.

Apply only:
ALTER USER RUSHIKESH2001 SET
  DEFAULT_ROLE = CIQ_PRODUCT_READER
  DEFAULT_SECONDARY_ROLES = ();

Reinspect the two stored defaults and confirm role grants are unchanged.
Do not change passwords, MFA, role memberships, PUBLIC grants, masking,
policies, account settings or any other user. Do not read case tables, invoke
AI, start Streamlit, resume warehouses or start compute pools. Do not perform
any additional remediation automatically.

Report old/new defaults and statement success, distinguishing stored-default
verification from fresh-session verification. Ask Rushikesh to open a fresh
session without explicit role/secondary-role overrides and run:
SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_SECONDARY_ROLES();
Do not run USE ROLE or USE SECONDARY ROLES first: that would mask the test.
If the client restores or overrides role context, report that and do not claim
defaults are independently verified. Never request tokens or recovery codes.
```

## Expected result and limits

- Stored primary default: CIQ_PRODUCT_READER; stored secondary default: empty.
- Fresh session: RUSHIKESH2001, CIQ_PRODUCT_READER, no active secondary roles.
  Inspect the returned structure rather than assuming a particular JSON shape.
- Existing sessions can retain their previous context. Explicit client role
  settings take precedence over defaults. Admin membership remains available
  for deliberate administrative work; this is accident prevention, not isolation.
- PUBLIC inheritance remains. MFA, effective privileges and database tenant
  isolation are separate open gates. Source HTTP remains disabled by default.
- If login verification fails, preserve the working administrative session and
  report the issue before any rollback or further changes. Never revoke roles.

## Evidence checklist

- [x] Narrow human approval received.
- [x] Preflight defaults and memberships captured by CoCo (supplied report).
- [x] Two default properties applied and stored values verified (supplied report).
- [ ] Fresh-session role context independently checked without overrides.
- [x] Relevant role memberships confirmed unchanged (supplied report).
- [x] Explicit worksheet role/secondary context verified in supplied screenshot.
- [x] Stored reader/empty-secondary defaults independently verified locally.

## Report received

Rushikesh supplied CoCo's before/after report: DEFAULT_ROLE changed from
ACCOUNTADMIN to CIQ_PRODUCT_READER; DEFAULT_SECONDARY_ROLES changed from
["ALL"] to []. CoCo reports unchanged grants: three account-role memberships
(ACCOUNTADMIN, CIQ_PRODUCT_READER, ORGADMIN) and five personal workspace/database/
schema privileges. These are eight grants, not eight role memberships.
No other settings or grants were reported changed. This documentation update
did not independently query Snowflake or test clinical unmasking.

Do not treat the report's statement about every new session as unconditional:
explicit connector settings and restored client context can override defaults.
The initial supplied worksheet screenshot still showed ACCOUNTADMIN with empty
secondary roles. A later screenshot after selecting/executing both USE commands
showed CIQ_PRODUCT_READER and empty secondary roles. This verifies the explicitly
selected worksheet context, not automatic login behaviour; restored worksheet
state or another client override remains a possibility, not a proven cause.
Unmodified fresh-session default verification remains open. Do not repeatedly
ALTER USER or revoke admin membership to force that test to pass.

A subsequent local DESCRIBE USER independently confirmed stored defaults are
CIQ_PRODUCT_READER and []; the connector explicitly requested reader and issued
NONE, so that check still does not establish automatic login behaviour.

Syntax reference: [Snowflake ALTER USER](https://docs.snowflake.com/en/sql-reference/sql/alter-user).
