# CashlessIQ handoff — 2026-10-04

Do not share or commit Snowflake passwords; they exist only in the user's
private Snowsight `auth.sql` worksheet.

## Current state

- Repository: `/Users/rushikeshhulage/Documents/Quant/cashlessiq`
- Branch: `main`; remote Phase 4 commit and annotated `phase-4` tag are present.
- Phase 5 evaluator commit: `f0b92d9 feat(eval): add golden-set scorecard`.
- Latest local verification before packaging: 59 tests and Ruff passed.
- Deployed reviewer console:
  `https://app.snowflake.com/me-central2.gcp/ca31605/#/streamlit-apps/CASHLESSIQ_APP`
- Live evaluation run: `EVAL-E6E692A5D0E04347B06F` — schema 30/30,
  outcomes 27/30, amounts 29/30, strict citation recall 55%, average latency
  41.4 seconds. Details are in `docs/evaluation.md`.
- Scorecard is deployed and its EVAL-table caller grants are applied.
- Final seven-day warehouse usage was 4.996 credits; `CLAUSE_SEARCH` was
  confirmed `SUSPENDED` after evaluation.
- Submission deck: `submission/CashlessIQ-Hackathon-Deck-v2.pptx`.
- `CIQ_JUDGE` has the correct role but intentionally has no repository-managed
  password. Rushikesh must set and test a strong password privately.

## Known, disclosed gaps

- GOL024–026 miss REFER because extracted `ICD10_CODE` is the literal string
  `None`, preventing the deterministic PED match.
- GOL029 uses the loaded ₹644,100 remaining sum insured rather than the golden
  scenario's ₹45,000 override.
- Strict line-level citation recall undercounts QUERY/REFER responses because
  the output schema has no decision-level citation field.

## Exact next steps

1. Run final tests and lint; review and commit the Phase 5 documentation, deck,
   and caller grants.
2. Rushikesh sets a private `CIQ_JUDGE` password and tests the console in a
   private browser window.
3. Push the clean commits and create annotated tag `phase-5` only when all
   Phase 5 exit criteria are green.
4. Complete the hackathon submission form; do not begin any post-submission
   phase before the submission is confirmed.

## Next-chat prompt

> Continue CashlessIQ from `docs/next-chat-handoff.md`. Read it and
> `docs/build-plan.md` plus `docs/strategy.md` fully before acting. Work strictly
> phase-by-phase. Finish Phase 5 only: verify local checks, judge login,
> packaging, push and tag. Preserve the human approval
> gate and deterministic rule boundary. Keep Snowflake usage economical.
