# CashlessIQ architecture

CashlessIQ keeps policy arithmetic deterministic and uses the Cortex Agent only
for orchestration and explanation.

```text
Synthetic pre-auth PDFs                 Public policy wording
          |                                      |
          v                                      v
  AI_PARSE_DOCUMENT                       POLICY_CLAUSE
  PREAUTH_FACTS                           CLAUSE_SEARCH
          |                                      |
          +---------- Cortex Agent --------------+
                         |
                 deterministic tools
            waiting periods | payable | SLA
                         |
                         v
             validated decision JSON
                         |
                         v
          Streamlit reviewer console + audit log
```

## Trust boundaries

- All member, claim, hospital, and request records are fixed-seed synthetic data.
- Only the public New India Assurance policy wording enters document retrieval.
- The pure-Python rules core has no Snowflake imports. Stored procedures wrap it
  without changing its calculations.
- Every rupee value comes from deterministic tools. The agent selects tools,
  retrieves evidence, and writes the explanation.
- The output contract permits `APPROVE`, `APPROVE_WITH_DEDUCTIONS`, `QUERY`, and
  `REFER`. It rejects `DENY`.
- A human reviewer owns the final action. The medical officer, processor, and
  auditor receive different data visibility and action permissions.
- Policy onboarding stops at a human approval gate. Unsupported benefits become
  searchable clauses and never executable rules.

## Snowflake objects

`CORE` stores synthetic members, policies, conditions, claims, hospitals, and
TPAs. `DOCS` stores requests, extracted facts, policy clauses, rules, and stages.
`AI` contains the semantic view, Cortex Search service, deterministic procedures,
and Cortex Agent. `APP` contains draft decisions and reviewer actions. `EVAL`
stores golden expectations and measured runs.

The container-runtime Streamlit app uses restricted caller rights, so Snowflake
masking policies and role grants still apply to the signed-in reviewer.
