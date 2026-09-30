---
name: policy-onboarding
description: Governed onboarding of a new health-policy wording into CashlessIQ.
---

# Policy onboarding

Use this workflow only with synthetic or public policy documents. Never ingest
member, patient, or claim data through this skill.

## Inputs

- Local path to the public policy wording PDF.
- Product ID, product name, insurer, UIN, version, effective date, and source URL.
- The human reviewer who will approve or reject proposed rules.

## Workflow

1. Confirm the active role is `CIQ_ADMIN`, database is `CASHLESSIQ`, warehouse
   is `CIQ_WH`, and the source metadata is complete. Stop if any value is
   missing.
2. Upload the PDF to `@CASHLESSIQ.DOCS.POLICY_STAGE/<PRODUCT_ID>/`. Refresh the
   directory and record the exact staged path.
3. Parse the wording in layout mode with `AI_PARSE_DOCUMENT`. Split on numbered
   headings and produce stable clause IDs using `<PRODUCT_ID>-<VERSION>-<SECTION>`.
4. Stage proposed clauses in a temporary table. Show the reviewer a diff against
   `DOCS.POLICY_CLAUSE`; do not merge yet.
5. Propose `POLICY_RULE` rows for caps, proportions, sub-limits, co-pay,
   waiting periods, and exclusions. Every rule must reference a staged clause
   and keep all thresholds in `PARAMS`.
6. Present a human-readable rule diff including source text, extracted value,
   rule type, parameters, and clause ID. Stop and ask for explicit approval.
   Never insert or merge unapproved rules.
7. After approval, transactionally merge the product, clauses, and rules. Set
   `VERIFIED_BY` and `VERIFIED_AT` from the approval record.
8. Refresh `AI.CLAUSE_SEARCH`, then run the standard ten search probes adjusted
   to the new product. Each expected clause must appear in the top three.
9. Generate exactly three fixed-seed synthetic requests for the product: one
   clean approval, one deduction, and one QUERY or REFER. Run all three through
   the deterministic tools and agent; validate the decision schema.
10. Write the prompt, approval, object counts, probe results, three decisions,
    and saved SQL paths to `docs/coco-playbook.md`.

## Safety gates

- Never invent a threshold absent from the wording.
- Never let an LLM calculate payable amounts.
- Never create a `DENY` expectation or outcome.
- Never auto-approve proposed clauses or rules.
- Roll back the merge if any rule lacks a valid clause or any test fails.
