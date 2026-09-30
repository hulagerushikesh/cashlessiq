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
