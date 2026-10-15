# Personas and workflows

Status: Draft for Product Phase P0  
Last updated: 15 October 2026

## Design principles

- Optimise for evidence review, not chatbot conversation.
- Show the source, extracted fact, rule, calculation, and recommendation as one
  connected chain.
- Put missing information and contradictions ahead of confident prose.
- Keep final authority and irreversible actions visibly human.
- Make the common path fast without hiding exceptional cases.
- Reveal sensitive data only when the role and task require it.

## Processor

The processor manages a high-volume queue and needs to determine whether a case
is complete and routine.

Needs:

- SLA-ordered queue with filters, assignment, and bulk-safe operations;
- missing-document and missing-field summary;
- compact member and policy context;
- a clear distinction between system facts and model-generated explanation;
- one-click query templates that remain editable;
- no access to restricted clinical details unless policy permits it.

The processor may validate, comment, raise a query, and prepare a draft. The
processor cannot perform a medical referral outcome or final approval unless a
tenant explicitly grants that authority.

## Medical officer

The medical officer resolves clinically ambiguous, waiting-period, and
exception cases.

Needs:

- original document and extracted fact side by side;
- condition, diagnosis, disclosure, and claim timeline;
- exact policy wording with page and version;
- deterministic calculation breakdown;
- clear referral reason and processor notes;
- ability to edit the recommendation with a mandatory reason.

## Auditor

The auditor reconstructs decisions without changing them.

Needs:

- immutable chronological event history;
- before-and-after values for material edits;
- identity, role, policy version, rule version, and model version;
- source and citation access subject to masking;
- exportable evidence package with integrity metadata.

## Policy analyst and approver

The analyst proposes clauses and rules. A separate approver activates them.

Needs:

- clause-level document navigation;
- human-readable rule parameters;
- supported versus unsupported classification;
- semantic diff against the active version;
- affected-case analysis and regression results;
- explicit approve, reject, and return-for-change actions.

## Operations lead

Needs:

- queue load, aging, and SLA-risk distribution;
- assignment and escalation controls;
- extraction, search, agent, and rules-engine health;
- quality metrics segmented by product and workflow stage;
- no clinical text in aggregate telemetry.

## Reviewer workspace information architecture

The production workspace should use four coordinated regions:

1. **Queue context:** status, SLA, priority, assignment, and next action.
2. **Request and member context:** submitted facts, original document, member
   history, policy coverage, and prior claims.
3. **Recommendation:** outcome, line-item calculation, missing information, and
   confidence expressed as evidence completeness rather than a vague AI score.
4. **Evidence rail:** policy clause, governed record, rule output, version, and
   link to source.

The primary action bar remains pinned and contains only actions authorised for
the current role and state.

## Canonical workflow states

```text
RECEIVED
  -> VALIDATING
  -> REJECTED_INPUT            invalid file, duplicate, or unsafe payload
  -> EXTRACTING
  -> NEEDS_INFORMATION         required facts or documents missing
  -> READY_FOR_ASSESSMENT
  -> ASSESSING
  -> DRAFT_READY
  -> IN_REVIEW
  -> QUERY_SENT                waits for new information
  -> REFERRED                  waits for authorised medical review
  -> APPROVED
  -> APPROVED_WITH_DEDUCTIONS
  -> CANCELLED                 administrative closure only
```

`DENIED` is deliberately absent. A future claim-adjudication product would
require a separate legal, clinical, and product review rather than adding a
state to this workflow.

## Exception journeys

### Missing information

- Identify exactly which required fields or documents are missing.
- Do not calculate a payable amount from incomplete cost data.
- Preserve the last complete extraction when additional files arrive.
- Re-run only affected stages and link the new run to the earlier attempt.

### Conflicting evidence

- Show both values and their sources.
- Stop automatic progression.
- Require a reviewer to select or correct the governed fact with a reason.

### Policy ambiguity

- Do not invent an executable rule.
- Retrieve the relevant clause and route to `REFER`.
- Capture the resolution as a policy-operations follow-up, not as an invisible
  prompt change.

### Concurrent review

- Show that another reviewer holds the case.
- Allow read-only inspection.
- Require an explicit takeover with an audit event if the tenant permits it.

## UX research plan

Before building detailed screens, conduct five to eight workflow interviews
across processors, medical officers, policy analysts, and operations leads.
Observe anonymised or synthetic case handling rather than asking only for
feature preferences.

Validate:

- terminology and actual state transitions;
- which evidence is reviewed first;
- acceptable keyboard and bulk workflows;
- escalation and assignment rules;
- what constitutes a material edit;
- expected integrations and the system of record;
- role-specific masking expectations.

The first usability test should measure completion and error rates for three
tasks: routine approval with deductions, missing-information query, and PED
medical referral.
