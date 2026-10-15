# ADR-003: Application identity with tenant-scoped authorisation

- Status: Accepted by Rushikesh on 18 October 2026
- Date: 15 October 2026

## Context

The prototype uses separate Snowflake users and default roles for processor,
medical officer, and auditor personas. A product must integrate with customer
workforce identity, support multiple organisations, revoke access centrally,
and prevent cross-tenant access without provisioning every reviewer as a direct
Snowflake application user.

## Decision

Use OIDC-based application identity. Map each authenticated subject to an
application user, one or more tenant memberships, and explicit capabilities.
Tenant context is derived and validated server-side for every operation.

Use RBAC for understandable job roles and targeted attributes for constraints
such as TPA, insurer, product, region, assignment, and case state. Backend
services access Snowflake using scoped service identities or approved delegated
mechanisms, with tenant filters and Snowflake governance as defence in depth.

## Consequences

Positive:

- customer SSO and lifecycle management become possible;
- reviewers do not need Snowflake credentials;
- API, storage, queue, and export authorisation share one application context;
- tenant isolation can be tested systematically.

Costs:

- identity mapping, role administration, and SSO configuration become product
  capabilities;
- service-to-service identity needs independent design and rotation;
- support and emergency access require explicit audited procedures.

## Guardrails

- Never accept a tenant identifier as sufficient proof of access.
- Every repository query is tenant scoped.
- Object-storage paths, queue messages, cache keys, and Snowflake requests carry
  validated tenant context.
- Cross-tenant support access is disabled by default and cannot be hidden from
  the audit trail.
