# CashlessIQ product requirements

Status: Product Phase P0 approved
Owner: Product and engineering  
Last updated: 18 October 2026

## Product statement

CashlessIQ is a human-in-the-loop pre-authorisation decision workspace for
health insurers and TPAs. It assembles the member record, validates the
hospital request, applies deterministic policy rules, retrieves the applicable
policy wording, and presents an auditable recommendation to an authorised
reviewer.

CashlessIQ does not make an autonomous denial. The supported recommendation
states remain `APPROVE`, `APPROVE_WITH_DEDUCTIONS`, `QUERY`, and `REFER`.

## Initial customer and deployment hypothesis

The approved initial customer direction is an Indian TPA operating cashless
pre-authorisation for one or more insurers. The approved deployment direction is hybrid:

- a managed application tier provides identity, workflow, and reviewer UX;
- Snowflake provides governed analytics, document intelligence, evidence
  retrieval, evaluation, and customer-isolated data processing;
- original clinical documents remain in customer-approved regional storage;
- a customer may later choose a dedicated application deployment.

These directions were approved by Rushikesh on 18 October 2026 and remain
assumptions to validate with design partners, not sales commitments.

## Users

| User | Primary objective | Authority |
| --- | --- | --- |
| Processor | Complete and triage requests quickly | Validate, request information, draft |
| Medical officer | Resolve clinical and policy ambiguity | Refer, edit, approve |
| Auditor | Reconstruct what happened and why | Read-only |
| Policy analyst | Onboard and maintain products | Propose rules and clauses |
| Policy approver | Control executable policy changes | Approve or reject versions |
| Operations lead | Manage queues, SLAs, and quality | Assign, escalate, report |
| Tenant administrator | Manage users and integrations | Configure tenant access |

## Initial product scope

The first production slice supports initial cashless pre-authorisation for one
TPA and one or two policy products.

Included:

- PDF and API request ingestion;
- request validation and missing-information detection;
- member and policy context assembly;
- deterministic waiting-period and payable calculations;
- cited policy evidence;
- processor and medical-officer review;
- query, referral, approval, and approval-with-deductions workflows;
- assignment, comments, audit history, and SLA monitoring;
- versioned policy onboarding with explicit approval;
- quality evaluation against a controlled case set.

Excluded from the initial product:

- autonomous denial;
- claim settlement or payment;
- final discharge authorisation;
- member-facing or hospital-facing portals;
- every insurer format or policy product;
- multilingual clinical documents;
- automated clinical diagnosis;
- replacing the insurer's core policy or claims system.

## Core user journeys

### Submit and prepare a request

1. A hospital or operator submits a request and supporting documents.
2. The system issues an idempotent request identifier.
3. Files are scanned, stored, classified, and extracted asynchronously.
4. Required facts are validated.
5. Incomplete requests enter `NEEDS_INFORMATION`; complete requests enter
   `READY_FOR_ASSESSMENT`.

### Review a recommendation

1. The reviewer opens an assigned case from an SLA-prioritised queue.
2. The workspace shows source documents, extracted facts, member history,
   calculations, and policy evidence without forcing navigation between tools.
3. The reviewer accepts, edits, queries, or refers the recommendation.
4. Material edits require a reason.
5. The action, actor, role, evidence, and versions are appended to the audit
   history.

### Onboard a policy version

1. An analyst uploads a versioned policy wording.
2. CashlessIQ extracts clauses and proposes supported rules.
3. Unsupported clauses remain searchable but never become executable rules.
4. An approver reviews a human-readable diff and regression results.
5. Only an approved, effective version can be used for new assessments.

## Functional requirements

### Workflow

- Every request has a tenant, source, priority, status, assignee, and SLA clock.
- State changes follow a defined state machine and reject invalid transitions.
- Reviewer writes support optimistic concurrency to prevent silent overwrite.
- Retried external submissions are idempotent.
- Long-running extraction and decision operations never hold open an HTTP
  request.

### Decision integrity

- All monetary values use integer minor-safe units; for INR the stored display
  unit remains integer rupees unless a contract requires paise.
- Every monetary result identifies the rule-set version and tool output used.
- Every decision line cites a policy clause or governed record reference.
- Missing or contradictory information produces `QUERY` or `REFER`.
- `DENY` is rejected by contracts, domain logic, and UI action controls.
- A human actor owns every final action.

### Policy management

- Products, wordings, clauses, and executable rules are versioned.
- Effective dates are explicit and historical versions are immutable.
- Activation requires a second human approval and a passing regression gate.
- Rollback creates a new activation event; it does not rewrite history.

### Audit and reporting

- Audit events are append-only and include actor, tenant, role, request ID,
  action, timestamp, correlation ID, and relevant version identifiers.
- Authorised users can reconstruct the inputs, rules, evidence, model, prompt,
  and tool results used for a draft.
- Product analytics never expose clinical or personal data by default.

## Non-functional requirements

Initial targets, to be validated with a pilot:

| Area | Initial target |
| --- | --- |
| Availability | 99.9% monthly for reviewer workflows |
| Queue and case reads | p95 under 500 ms, excluding document rendering |
| Reviewer writes | p95 under 1 second |
| Draft generation | asynchronous; p95 under 90 seconds |
| Durability | no acknowledged review action may be silently lost |
| Traceability | 100% of monetary values linked to deterministic output |
| Human authority | 100% of final decisions linked to a human actor |
| Tenant isolation | automated cross-tenant tests on every release |
| Accessibility | WCAG 2.2 AA target for core reviewer journeys |

## Product success measures

- median time from complete request to review-ready recommendation;
- reviewer handling time and cases per reviewer-hour;
- percentage of cases requiring manual data re-entry;
- recommendation outcome and payable-amount agreement;
- citation precision and recall;
- reviewer edit rate and edit reason distribution;
- query and referral rate;
- SLA breach rate;
- policy onboarding time and regression pass rate;
- severe audit, privacy, or cross-tenant incidents.

## Launch gates

- A design partner approves the supported workflow and terminology.
- Security, privacy, retention, and data-residency requirements are documented.
- The target policy products pass their approved regression suites.
- Pilot accuracy thresholds are agreed by clinical and policy owners.
- Incident response, backup, restore, and rollback procedures are exercised.
- The product is clearly positioned as decision support with mandatory human
  review.

## Approved initial product decisions

- The first supported product is the currently implemented and evaluated Arogya
  Sanjeevani policy, using the governed source documented in `docs/datasets.md`.
- The initial pilot uses synthetic data. Controlled de-identified data may follow
  after the documented real-data launch gates pass.
- The TPA/core system remains the legal system of record initially. CashlessIQ
  maintains its own immutable audit trail and operational workflow state.

## Remaining pilot decisions

1. Select the first customer integration format.
2. Agree pilot accuracy, latency, and availability thresholds.
