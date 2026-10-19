# Reviewer workflow validation kit

Status: Ready to use; no participant evidence collected  
Owner: Rushikesh  
Last updated: 19 October 2026

## Purpose and boundaries

Validate the first Indian TPA reviewer workflow before building the detailed
case workspace. This is research preparation within P1, not the start of P2.
The implemented product currently supports local identity and role context;
case review, approvals, and policy activation are not implemented in that UI.

Use five distinct people with relevant current or recent experience. Aim for
two processors (or one processor and an operations lead), one medical officer,
one policy analyst/approver, and one operations lead or auditor. Record actual
roles and gaps rather than relabelling participants to fit this coverage.

No Snowflake session, paid model, customer login, or real patient record is
required. Use the synthetic scenarios below. Obtain consent before retaining
anonymised notes; do not record audio/video without separate consent. Do not
commit names, contact details, employer-confidential material, or patient data.

## Invitation draft — not sent

> I am developing CashlessIQ, a reviewer workspace for cashless health-insurance
> pre-authorisation. Could you spare 20 minutes to explain how you handle a
> routine request, missing information, and a medical referral? We will use
> synthetic examples only; please do not share patient data or confidential
> employer documents. I am looking for workflow feedback, not a purchase
> commitment. With your permission, I will retain anonymised notes.

Rushikesh chooses contacts and sends invitations. This document does not
authorise outreach or claim that a design partner has agreed to participate.

## Twenty-minute session

1. Consent and background (2 minutes): role, relevant experience, and which
   parts of pre-authorisation the person actually handles.
2. Current workflow (5 minutes): ask them to describe the last typical case
   without identifying anyone. Capture tools, handoffs, waiting, and re-entry.
3. Scenario walkthrough (9 minutes): read the participant prompts below, not
   the facilitator notes. Ask what they would inspect and do next, and why.
4. Exceptions and close (4 minutes): concurrency, masking, material edits,
   final system of record, and the most costly avoidable step.

Do not pitch the proposed UI first or lead with “would you use AI?” Distinguish
what they do today from what they wish were possible. Domain disagreement is
evidence to investigate, not permission to change an approved policy rule.

## Synthetic scenario cards

Inputs come from `data_gen/golden_cases.yaml`. Facilitator expectations below
come from the frozen deterministic results in
`tests/fixtures/migration/v1.json`; no new amounts or policy rules are proposed.
Keep the fixed October 2026 admission dates when discussing waiting periods.
These cards validate workflow, not clinical correctness or real coverage.

### A — Routine request: GOL001

Participant prompt: A synthetic member has continuous cover from 1 January
2023. Admission is planned for 2 October 2026 for appendicitis treatment.
The hospital supplies a complete cost breakdown and supporting facts. Describe
your first checks, the evidence you need, and who can finalise the response.

Facilitator notes: The frozen result is `APPROVE_WITH_DEDUCTIONS`, with claimed
INR 100,000 and payable INR 95,000. It cites `NIA-4.1-A` and `NIA-9.5`, including
the approved 5% co-pay. Reveal this only after the participant explains their
workflow. Ask what they would need to verify before accepting that draft and
what authority the processor versus medical officer should have.

### B — Missing cost breakdown: GOL027

Participant prompt: The synthetic hospital provides an estimated total but no
cost breakdown. What do you do, whom do you contact, and what happens when a
corrected document arrives? What should happen to assignment and the SLA clock?

Facilitator notes: The frozen result is `QUERY`, with no payable calculation.
The query requests the cost breakdown. Check whether participants distinguish
unknown payable from zero payable. Capture required fields, query wording,
clock semantics, and whether reprocessing should preserve prior evidence.

### C — PED referral: GOL024

Participant prompt: A synthetic member declared diabetes before inception.
Continuous cover begins 1 January 2026, and admission for a related complication
is planned for 2 October 2026. Which facts and documents do you verify, who
resolves uncertainty, and what should be recorded in the handoff?

Facilitator notes: The frozen result is `REFER`, with no payable calculation,
under the approved 36-month PED rule and clause `NIA-6.1`. A referral is not a
denial. Capture the authorised recipient, necessary clinical visibility,
reason, and audit evidence. Do not turn participant feedback into a new rule
or bypass the policy approval gate.

## What to record

Use one copy of the record in [interview-template.md](interview-template.md)
per participant. For each scenario, add:

- first evidence inspected and its reason;
- next action, responsible role, and handoff;
- missing or confusing information;
- whether the walkthrough was completed independently, with prompting, or not
  completed; record elapsed time only if actually measured;
- one concrete workflow example or consented anonymised quote;
- consequence for requirements: keep, change, or investigate.

These are facilitated walkthroughs, not measured application usability tests.
Do not claim handling-time improvements from them. Async written answers are
acceptable evidence if role, context, date, consent, and concrete examples are
captured; generic endorsements or generated answers are not.

## Assumptions to reconcile before P2

| ID | Current hypothesis, not a finding | Evidence needed |
| --- | --- | --- |
| A01 | Indian TPA processors are the first daily users | Actual intake ownership, volume context, and repeated pain |
| A02 | Queue priority uses SLA risk and assignment | Actual clock start/pause rules, priority exceptions, handoffs |
| A03 | Evidence and deterministic traces are reviewed together | Which source is inspected first and why a draft is distrusted |
| A04 | Processor drafts; authorised medical officer finalises | Actual role boundaries, delegation, and material-edit rules |
| A05 | Core TPA system remains the legal record | Final decision ownership, re-entry fields, integration format |
| A06 | Clinical visibility differs by role | Minimum necessary fields, masking expectations, audit access |
| A07 | Policy proposer and activator are separate people | Actual approval practice, exceptions, and version controls |
| A08 | Concurrent edits require explicit conflict handling | Real examples of duplicate work, takeover, and correction |

In a dated synthesis, map each assumption to participant IDs, supporting and
contradicting evidence, the resulting decision, and any requirement change.
Do not equate five interviews with market validation or regulatory approval.
Conflicting findings remain open until explicitly resolved with the product
owner; policy execution changes still require their separate human gate.

## Exit and next implementation

P1 exits only after five evidence-backed target-user records are reconciled
and its engineering checks remain green. Research preparation alone does not
close that gate. If recruiting is not feasible, ask Rushikesh to explicitly
revise the phase gate and document the risk; do not silently waive it.

After P1 closes, the planned P2 slice is read-only: tenant-scoped queue,
case/member context, frozen decision trace, and policy evidence through API
contracts. Reviewer mutations, policy activation, and asynchronous assessment
remain later slices. No P2 code is introduced by this kit.
