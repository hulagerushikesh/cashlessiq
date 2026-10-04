# Three-minute demo script

## 0:00–0:25 — Problem

Open the CashlessIQ landing page. Explain that hospital cashless requests arrive
with clinical facts, benefit limits, waiting periods, and an IRDAI one-hour
decision window. Manual review is slow and difficult to audit.

## 0:25–1:25 — Review a deduction case

Open Queue, then GOL007 in Case. Run the copilot. Show the ₹120,000 claim and
₹79,800 recommendation. Expand the calculation lines: ₹5,000 daily room cap,
5,000/8,000 proportionate ratio on professional fees, and mandatory 5% co-pay.
Open the cited policy wording. State that Python computed every amount; the agent
only orchestrated tools and explained the evidence.

## 1:25–1:55 — Human control and governance

Show the available medical-officer actions and Decision Log. Explain that the
copilot never returns `DENY`; ambiguous or excluded cases go to `QUERY` or
`REFER`. Briefly contrast the processor's masked view and query-only action with
the auditor's masked, read-only view.

## 1:55–2:25 — Measured quality

Open Scorecard. Show the latest 30-case run: 30/30 schema-valid, 27/30 outcomes
correct, 29/30 payable amounts correct, and 41.4-second average latency. Call out
the 55% citation recall honestly: payable lines cite well, while QUERY/REFER and
exception explanations need a first-class decision-level citation field.

## 2:25–2:50 — CoCo policy onboarding

Explain the governed onboarding run: CoCo staged a diff from a public policy,
stopped for human approval, added 25 searchable clauses, and changed zero rules.
Unsupported benefits could not become executable calculations. Search probes
passed 10/10.

## 2:50–3:00 — Close

CashlessIQ combines Snowflake-native retrieval and agents with deterministic
insurance logic, role-aware review, and an auditable evaluation trail. It drafts
a defensible recommendation in under a minute while the human keeps authority.
