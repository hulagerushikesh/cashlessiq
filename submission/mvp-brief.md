# CashlessIQ — Prototype/MVP brief

CashlessIQ is a Snowflake-native copilot for hospital cashless pre-authorisation review. It combines synthetic pre-authorisation PDFs, a Member 360 semantic view, policy clauses in Cortex Search, deterministic Snowpark tools and a Cortex Agent. The agent orchestrates evidence and explanations, while pure Python calculates every rupee and validates the final JSON. The output contract never permits `DENY`; uncertain cases become `QUERY` or `REFER`, and a human reviewer makes the final decision.

The prototype serves medical officers, pre-authorisation processors and auditors. Role-aware masking and restricted caller rights give each persona the appropriate data and actions. A governed policy-onboarding workflow requires explicit human approval and prevents unsupported benefits from becoming executable rules.

The live evaluation processed 30 fixed-seed golden cases: 30/30 responses passed the schema, 27/30 outcomes matched, 29/30 payable amounts matched, and mean Agent latency was 41.4 seconds. The repository documents the remaining extraction, scenario-override and citation-recall gaps.

**Challenges:** Patient and Member 360; Clinical or Regulatory Document Copilot  
**Team:** HiggsBosons
**Repository:** https://github.com/hulagerushikesh/cashlessiq  
**Public prototype:** https://cashlessiq.hulage.in  
**Authenticated Snowflake app:** https://app.snowflake.com/streamlit/nooirvx/ca31605/#/apps/a3gfspf7joxnsjryt3pd
