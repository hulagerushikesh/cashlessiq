# CashlessIQ threat model

Status: Initial Product Phase P0 model  
Last updated: 15 October 2026

This document guides engineering design. It is not a legal, privacy, or
regulatory certification. Requirements must be reviewed with the customer's
security, privacy, medical, and legal owners before a real-data pilot.

## Protected assets

- patient and member identity and contact information;
- clinical notes, diagnoses, conditions, and supporting documents;
- policy, coverage, claims, and financial information;
- reviewer identity, comments, and decision history;
- policy clauses, executable rules, and activation history;
- credentials, tokens, signing keys, and integration secrets;
- model prompts, tool output, evaluation cases, and quality results;
- audit events and evidence packages.

## Trust boundaries

1. Browser to application edge.
2. Application API to transactional database.
3. API to object storage and queue.
4. Worker to Snowflake and model services.
5. Tenant data boundary.
6. Product control plane to customer data plane.
7. Human policy proposal to executable rule activation.
8. Operational telemetry to monitoring providers.

## Principal threats and controls

| Threat | Primary controls |
| --- | --- |
| Cross-tenant record access | tenant key on every aggregate, scoped repositories, database policies where supported, negative access tests |
| Broken object-level authorisation | derive tenant and actor server-side; never trust browser-supplied ownership |
| Privilege escalation | central RBAC/ABAC policy, least privilege, separation of analyst and approver |
| Credential theft | OIDC, short sessions, secure cookies, rotation, managed secret store, no browser Snowflake credentials |
| Malicious document | size/type limits, quarantine, malware scan, parser isolation, time and memory limits |
| Prompt or document injection | documents are evidence, never instructions; tool allowlists; structured outputs; deterministic validation |
| Model-generated money | reject values without matching deterministic calculation trace |
| Unsupported policy execution | allowlisted rule types, schema validation, human approval, regression gate |
| Audit tampering | append-only events, restricted writer, integrity metadata, independent export/retention |
| Sensitive data in logs | structured allowlist, redaction tests, no document or clinical content |
| Replay or duplicate submission | idempotency keys, content hashes, nonce and timestamp where integrations require signing |
| Concurrent reviewer overwrite | optimistic locking, assignment lease, explicit takeover event |
| Data exfiltration through exports | role checks, scoped export, watermark and audit, bounded signed URLs |
| Dependency or build compromise | lockfiles, scanning, provenance, protected CI, reviewed promotion |
| Availability exhaustion | tenant quotas, queue isolation, rate limits, file limits, circuit breakers, budgets |
| Inference or search data leakage | tenant-filtered retrieval, customer-approved regions, provider contract controls |

## Identity and authorisation

- Use customer OIDC/SSO for workforce users.
- Map external identities to an application user and tenant membership.
- Authorise every command and query in the API; hiding a UI control is not an
  authorisation control.
- Separate processor, medical officer, auditor, policy analyst, policy approver,
  operations lead, and tenant administrator capabilities.
- Require step-up authentication for policy activation and sensitive exports
  when the identity provider supports it.
- Service integrations use scoped, rotatable identities; never shared human
  credentials.

## Data handling

- Classify fields as public, internal, personal, clinical-sensitive, financial,
  or secret.
- Collect only fields required for the supported workflow.
- Encrypt data in transit and at rest using managed platform controls.
- Store original documents in tenant-scoped storage with short-lived access.
- Define retention, legal hold, deletion, and backup behaviour per tenant and
  data class before real data is accepted.
- Do not use customer documents or decisions for model training without an
  explicit separate agreement and technical control.
- Never copy production clinical data into development, test, demos, prompts,
  screenshots, or support tickets.

## AI-specific controls

- Treat uploaded documents, retrieved clauses, and model responses as untrusted
  inputs.
- Agent instructions cannot grant tools, data access, or authority.
- Tools expose the minimum typed input and output necessary.
- The rules engine is authoritative for waiting periods and money.
- Model output must pass versioned schema and semantic validation.
- Citation references must resolve to evidence available to the current tenant
  and actor.
- Store model, prompt, tool, rule, and evidence versions for reproducibility.
- Maintain golden, adversarial, injection, and tenant-isolation evaluations.

## Audit requirements

Record at minimum:

- authentication and sensitive authorisation failures;
- request creation and document lifecycle events;
- assignment and takeover;
- extraction correction;
- rule and evidence versions used;
- draft creation and validation failures;
- every reviewer action and material before/after value;
- policy proposal, approval, activation, rollback, and regression result;
- administrative and export actions.

Do not record secrets, raw tokens, or full clinical content in general logs.

## Security verification

Before a controlled real-data pilot:

- complete data-flow and privacy-impact reviews;
- test tenant isolation at API, database, object storage, search, and export
  boundaries;
- threat-model integrations and deployment topology;
- run static, dependency, container, infrastructure, and secret scanning;
- perform abuse-case and prompt-injection evaluations;
- complete an independent application penetration test;
- test backup restoration, key rotation, incident response, and access
  revocation;
- document breach and customer-notification responsibilities.

## Unresolved security decisions

1. Customer Snowflake account versus vendor-managed Snowflake account.
2. Required Indian data-residency and subprocessors for the first pilot.
3. Customer-controlled encryption keys, if required.
4. Record-retention period and legal system of record.
5. Whether support personnel may ever receive time-bound production access.
6. Which actions require four-eyes approval or step-up authentication.
