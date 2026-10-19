# P2 metadata preflight: report reconciliation

Date: 19 October 2026. Status: owner-supplied report reviewed; partial evidence,
not isolation acceptance or provisioning approval.

Rushikesh explicitly approved the 24-statement/five-minute read-only preflight.
The supplied 246-line CoCo report records 21 attempted statements, including one
failed RESULT_SCAN filter, under RUSHIKESH2001 / ACCOUNTADMIN with secondary
roles empty. It reports no mutations, source-row reads, warehouse resume or AI
invocation. These execution claims were not independently rerun here. The report
contains statement labels, but no query IDs, start/end timestamps or elapsed
time; the statement cap is reported satisfied, the time cap is not evidenced.
There is no remaining execution allowance to reuse automatically in a later run.

## Repository comparison

Compared the report with sql/02_core_tables.sql, sql/03_docs_tables.sql and
sql/04_app_eval_tables.sql. All eight reported column-name inventories match,
including integer-scale INR fields, ownership keys and nullable clinical facts.
Reported NOT NULL source PAYABLE_INR is consistent with the canonical adapter's
separate null-payable representation for validated uncomputed QUERY/REFER.

One report inconsistency: APP.DECISION has ten columns and names only
AGENT_RUN_ID and MODEL as nullable, yet says seven NOT NULL. Repository DDL has
eight NOT NULL. Treat the seven-count as an unresolved summary error, not a
reason to change source DDL. Raw DESCRIBE evidence was not attached. Repository
constraints and reported constraint labels are not proof of actual source-row
uniqueness, ownership integrity or constraint enforcement.

## Security findings and limits

- PUBLIC: reported 109 grants, including 12 database roles and one separate
  application role. This matches the prior independently observed category
  counts. The report attributes the earlier omission to CORE_VIEWER; that
  historical explanation is not independently established. No targeted inherited
  role grant inspection appears in the statement log. Effective dependency and
  no-AI/compute claims remain unresolved; no revocations are approved.
- Human defaults/passkey: report agrees with earlier verified reader/empty-
  secondary stored defaults and HAS_MFA true. Its actual ACCOUNTADMIN context
  is an inspection context, not proof of an unmodified fresh login.
- Policies: statement log says SHOW AUTHENTICATION POLICIES and SHOW SESSION
  POLICIES, without explicit account scope. Zero returned rows cannot establish
  an account-wide inventory or effective user-policy absence from this supplied
  log. Effective attachments, built-in enforcement and client-path compatibility
  remain unknown. MFA parameter values are not functional enforcement evidence.
- The BCR function's alleged compute requirement and categorical user-type
  enforcement claims are unverified report assertions; do not promote them to
  account-specific facts or run additional probes without a new bounded scope.
- Masking: report describes CIQ_ADMIN-owned MASK_CLINICAL_TEXT and MASK_PII.
  Clinical-note attachment is consistent with prior evidence. The current log
  does not include a policy-reference query to independently establish that
  MASK_PII is unattached everywhere. Retain that as earlier attributed evidence.
  Runtime access to raw decisions/other clinical fields still requires isolation.
- Statement categories used seven authentication checks and three governance
  checks versus allocations of six and two; these consume the two reserve slots.
  Total 21 remains below 24. The report's three remaining total slots are not an
  unused two-statement reserve or authorisation for further inspection.

## Disposition and next step

- [x] Architecture approval and separate preflight execution approval recorded.
- [x] Supplied column inventory compared with repository DDL; no schema edits.
- [x] PUBLIC category-count correction reconciled.
- [ ] Query-ID/time evidence, exact policy scope/attachments and inherited-role
  capabilities remain incomplete. Request existing evidence if available, not
  an automatic rerun or another account scan.
- [ ] Specify local validation hosting, invocation authorisation, clinical trust
  and isolated credential custody before preparing implementation SQL.
- [ ] Review exact provisioning/rollback package and approve functional tests.

Next design increment is local-only validation-worker/secret-boundary planning,
not a new cloud environment or backend reuse of operator OAuth. Keep canonical
Python validation, per-TPA separation and current v2 summary-only disclosure.
No new identity, credential, grant, policy, view, service startup, source
activation, push, website deployment or P3 work is authorised by this report.
No fresh Snowflake calls or runtime tests were performed during reconciliation.
