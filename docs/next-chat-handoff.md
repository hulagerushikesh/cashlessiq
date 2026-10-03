# CashlessIQ handoff — 2026-09-30

Paste the **Next-chat prompt** below into the new account/chat. Do not share or
commit any Snowflake passwords; they exist only in the user's private Snowsight
`auth.sql` worksheet.

## Current state

- Repository: `/Users/rushikeshhulage/Documents/Quant/cashlessiq`
- Branch: `main`, three committed Phase 4 changes ahead of `origin/main`.
- Do not push or tag Phase 4 yet.
- Local Phase 4 commits:
  - `e372aef feat(app): build reviewer console`
  - `4474752 feat(governance): enforce persona masking`
  - `6fe5ef0 feat(skill): add policy onboarding workflow`
- Uncommitted, intentional edits:
  - `.cortex/skills/policy-onboarding/SKILL.md`
  - `docs/coco-playbook.md`
- Latest local verification: 57 tests passed and Ruff passed.
- Deployed reviewer console:
  `https://app.snowflake.com/me-central2.gcp/ca31605/#/streamlit-apps/CASHLESSIQ.APP.CIQ_REVIEWER_APP`
- The user tested all three personas in private sessions and confirmed they pass:
  medical officer = full data/all actions; processor = partial/masked/query only;
  auditor = masked/read-only/Decision Log visible.
- `CIQ_MO_USER`, `CIQ_PROC_USER`, and `CIQ_AUDIT_USER` are enabled and each has
  a password. `CIQ_JUDGE` intentionally has no password yet (Phase 5).
- Last measured Snowflake usage was 10.744 credits over seven days.

## Policy-onboarding status

The first CoCo rehearsal stopped correctly at the human-review gate. It staged
temporary data only and made no permanent policy changes. It proposed six new
executable rule types that are not accepted by the `POLICY_RULE` constraint and
not implemented by the deterministic Python core. Therefore the proposal was
not approved.

The skill has now been tightened: a rule type must be supported by both the live
table constraint and Python engine; otherwise the benefit must be reported as
`CLAUSE_ONLY_UNSUPPORTED`. `docs/coco-playbook.md` records the rejected run and
the successful persona test.

A corrected CoCo run was started but deliberately interrupted to conserve the
remaining Codex weekly limit. Treat any temporary objects from it as disposable
and rerun cleanly. Never merge policy rows without showing Rushikesh the exact
corrected diff and obtaining approval specific to that diff.

## Exact next steps

1. Read `docs/build-plan.md`, `docs/strategy.md`, this file, and the complete
   `.cortex/skills/policy-onboarding/SKILL.md` before acting.
2. Review the two uncommitted edits, run `make test` and `make lint`, then commit
   them as a small conventional commit if green.
3. Rerun the policy-onboarding skill as an idempotent rehearsal for the public
   Arogya Sanjeevani PDF. Stage temporary objects only and present a corrected
   diff. Unsupported benefits may be searchable clauses but not executable
   rules.
4. Stop for Rushikesh's explicit approval of that exact diff.
5. Only after approval: merge transactionally, set verification metadata,
   refresh search, run 10 probes, and run exactly three fixed-seed synthetic
   cases (clean approval, deduction, and QUERY/REFER). Validate the decision
   schema and ensure no `DENY` outcome.
6. Save reproducible SQL as `sql/63_policy_onboarding_run.sql`, append results to
   `docs/coco-playbook.md`, rerun tests/lint, check spend, and evaluate every
   Phase 4 exit criterion.
7. Tell the user when it is safe to push and tag `phase-4`. Do not begin Phase 5
   until Phase 4 is green.

## Next-chat prompt

> Continue CashlessIQ from `docs/next-chat-handoff.md`. Read it and the two source
> documents fully before acting. Work strictly phase-by-phase. We are finishing
> Phase 4; do not begin Phase 5. Preserve the human approval gate for policy
> onboarding and never merge unsupported rule types. Inspect the worktree first,
> verify the two intentional uncommitted edits, then continue from the exact next
> steps in the handoff. Keep Snowflake usage economical and tell me before I
> should push or tag.
