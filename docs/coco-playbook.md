# CoCo prompt playbook

Record every meaningful Snowflake-side interaction so the build is auditable
and reproducible. Append entries; do not rewrite successful history.

## Entry template

- **Date/time (IST):** YYYY-MM-DD HH:MM
- **Phase:** 0–5
- **Goal:** What this interaction must establish
- **CoCo prompt:** Exact prompt, including requested plan/skill
- **Skill used:** For example `agent-studio` or `developing-with-streamlit`
- **Result:** Objects created, checks returned, errors, and decisions
- **SQL saved to:** Repository path, or `N/A` with reason
- **Follow-up / verification:** Remaining check and owner

## 2026-09-29 — Phase 0 account and runtime verification

- **Date/time (IST):** 2026-09-29 23:00
- **Phase:** 0
- **Goal:** Verify account capabilities, foundation SQL, Cortex Agent syntax,
  and container-runtime Streamlit deployment before mutation.
- **CoCo prompt:** Read-only review of `sql/00_account.sql` through
  `sql/04_app_eval_tables.sql`, `snowflake.yml`, and
  `app/streamlit_app.py`; identify current Agent and container-runtime syntax
  without editing files or executing SQL.
- **Skill used:** CoCo CLI repository review; Agent and Streamlit guidance.
- **Result:** CoCo correctly identified the missing container `compute_pool` and
  `runtime_name`, future grants, and the need for native HTTP in the container.
  It incorrectly claimed that `SNOWFLAKE.CORTEX_AGENT_USER` did not exist and
  suggested `CREATE CORTEX AGENT`; both were rejected after live account and
  official-documentation checks. The account contains the database role and
  Snowflake 10.34 accepts `CREATE AGENT ... FROM SPECIFICATION`.
- **SQL saved to:** `sql/00_account.sql`, `sql/01_database.sql`, and
  `sql/05_spike_agent.sql`.
- **Follow-up / verification:** Completed. `make setup` succeeded twice,
  `DATA_AGENT_RUN` returned `CashlessIQ spike connected.`, and the deployed
  container-runtime Streamlit app returned the same response through its UI.

## 2026-09-30 — Phase 2 document and retrieval review

- **Date/time (IST):** 2026-09-30 08:50
- **Phase:** 2
- **Goal:** Review current syntax for document parsing, structured extraction,
  Cortex Search, and the native semantic view before live deployment.
- **CoCo prompt:** Read-only repository review of the proposed Phase 2 objects;
  identify syntax and privilege risks without editing files or executing SQL.
- **Skill used:** CoCo CLI repository review and agent-studio guidance.
- **Result:** CoCo proposed legacy forms for `AI_PARSE_DOCUMENT`, `AI_EXTRACT`,
  and YAML-backed semantic models. Those suggestions were rejected after
  checking current Snowflake documentation and live compilation. The deployed
  account-specific syntax uses object-returning `AI_PARSE_DOCUMENT`, JSON Schema
  `AI_EXTRACT`, native `CREATE SEMANTIC VIEW`, and a minimum Cortex Search
  `AUTO_SUSPEND` of 1,800 seconds.
- **SQL saved to:** `sql/20_extract_preauth.sql`,
  `sql/21_policy_clauses.sql`, `sql/22_search_service.sql`, and
  `sql/30_semantic_view.sql`.
- **Follow-up / verification:** Completed. Extraction accuracy 206/210 (98.1%);
  search probes correct in top three 10/10; verified SQL queries 10/10.

## 2026-09-30 — Phase 3b tools and agent deployment

- **Date/time (IST):** 2026-09-30 15:30
- **Phase:** 3b
- **Goal:** Deploy caller-rights deterministic tools and a tool-first Cortex
  Agent using current account syntax.
- **CoCo prompt:** Review the four Snowpark procedure contracts and the Agent
  specification; confirm generic procedure resources, execution environments,
  and `DATA_AGENT_RUN` invocation.
- **Skill used:** Agent-studio guidance, checked against current official docs
  and live Snowflake compilation.
- **Result:** Four Python 3.11 procedures compiled and returned non-PII VARIANT
  payloads. Live testing found and fixed comma-formatted extracted rupees. Agent
  creation succeeded after replacing YAML anchors/flow lists that collided with
  Snow CLI templating and adding warehouse execution environments to Analyst
  and Search. `DATA_AGENT_RUN` completed with all tools available.
- **SQL saved to:** `sql/40_tools.sql` and `sql/50_agent.sql`.
- **Follow-up / verification:** Run the ten-case `eval.phase3b_acceptance` gate
  after local Snowpark connector OAuth is cached; target is schema-valid 10/10
  and outcome-correct at least 8/10.

### Phase 3b tuning result

The first agent smoke run returned an extra top-level `citations` field and
mislabelled a ₹100,000 claimed / ₹95,000 payable result as `APPROVE`. The
response contract was tightened to enumerate every permitted JSON key and to
require `APPROVE_WITH_DEDUCTIONS` whenever the tool totals differ. The corrected
smoke case passed, followed by the full exit gate: schema-valid 10/10 and
outcome-correct 10/10. Decisions were persisted to `APP.DECISION`.

## 2026-09-30 — Phase 4 app and governance

- **Date/time (IST):** 2026-09-30 18:30
- **Phase:** 4
- **Goal:** Deploy the reviewer console with viewer-context masking and verify
  all three governance personas without exposing synthetic PII in test output.
- **CoCo prompt:** Review the container Streamlit role model, masking-policy
  bodies, persona grants, and the policy-onboarding workflow. Confirm that the
  app uses restricted caller rights and that proposed policy rules require
  human approval before merge.
- **Skill used:** Streamlit container-runtime and governance guidance, checked
  against current Snowflake documentation and live account compilation.
- **Result:** The app was recreated with `CIQ_ADMIN` ownership because this
  account rejects direct ownership transfer for Streamlit objects. Restricted
  caller grants were limited to the named Phase 4 tables, stage, agent, search
  service, semantic view, and procedures. The live Queue, Case, and Decision
  Log pages loaded successfully. Label-only role checks returned
  medical=clear/clear/clear, processor=partial/partial/masked, and
  auditor=masked/masked/masked for name/phone/clinical note.
- **SQL saved to:** `sql/60_governance.sql`, `sql/61_governance_check.sql`, and
  `sql/62_app_caller_grants.sql`.
- **Follow-up / verification:** Authentication was configured outside the
  repository for `CIQ_MO_USER`, `CIQ_PROC_USER`, and `CIQ_AUDIT_USER`.
  On 2026-09-30 the human reviewer exercised the deployed console as all three
  personas and confirmed the expected masking and action differences passed.
  The first `policy-onboarding` proposal was stopped at its human-review gate:
  it proposed six executable rule types not supported by the live table
  constraint or deterministic engine. No permanent policy rows were changed.
  The skill was tightened to classify such benefits as searchable clauses only.
  Rerun the corrected onboarding flow and append its approval, object counts,
  probes, and three synthetic decisions here before tagging Phase 4.

## 2026-10-03 — Governed policy-onboarding rehearsal

- **Goal:** Complete the corrected Arogya Sanjeevani onboarding rehearsal while
  preserving the human approval gate and deterministic-rule boundary.
- **Prompt:** Stage a diff from the public policy PDF, classify unsupported
  benefits as searchable clauses only, stop for approval, then merge only the
  approved diff and validate search plus three fixed-seed cases.
- **Human approval:** Rushikesh explicitly approved: “I approve the 25
  clause-only additions and zero rule changes.”
- **Skill used:** Repository skill `policy-onboarding`.
- **Result:** The transaction inserted 25 clause-only rows. The product now has
  35 clauses; its 10 existing executable rules were unchanged. Six benefits
  (ambulance, AYUSH, pre/post hospitalisation, special procedures, and
  cumulative bonus) remain searchable but non-executable, and 19 individually
  numbered exclusions were added as searchable evidence. The refreshed search
  corpus contained 35 rows and the standard ten product-filtered probes passed
  10/10 at rank 1. `CLAUSE_SEARCH` was suspended after testing.
- **Synthetic decisions:** All three fixed-seed cases completed through the live
  agent and passed the repository decision validator. `GOL002` returned
  `APPROVE_WITH_DEDUCTIONS` (INR 100,000 claimed; INR 95,000 payable; mandatory
  5% co-pay only). This is the policy-correct cleanest case: a literal
  zero-deduction `APPROVE` is impossible while clause NIA-9.5 applies to every
  claim. `GOL007` returned `APPROVE_WITH_DEDUCTIONS` (INR 120,000 claimed; INR
  79,800 payable; room cap, proportionate deduction, and co-pay). `GOL027`
  returned `QUERY` for missing `cost_breakup`. No `DENY` was produced. The first
  two GOL007 attempts hit the Agent API time limit because the warehouse was
  cold; warming the exact tools allowed the bounded final retry to complete.
- **SQL saved to:** `sql/63_policy_onboarding_run.sql`.
- **Follow-up / verification:** Final live counts were 35 clauses and 10 rules.
  The search service was suspended after validation for cost control. Local
  verification finished with 57 tests passing and Ruff clean.
