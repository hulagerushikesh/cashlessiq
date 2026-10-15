# ADR-002: Use PostgreSQL for operational workflow state

- Status: Accepted by Rushikesh on 18 October 2026
- Date: 15 October 2026

## Context

Reviewer assignment, comments, idempotent commands, state transitions,
optimistic locking, job status, and outbox delivery are transactional workloads.
The prototype stores decisions and actions in Snowflake, which is appropriate
for the demonstration and analytical record but is not the preferred primary
store for latency-sensitive operational coordination.

## Decision

Use PostgreSQL as the operational system of record for application workflow.
Use Snowflake for governed intelligence inputs, policy retrieval, evaluation,
analytical history, reporting, and customer data processing.

Synchronise approved operational events to Snowflake through a transactional
outbox and idempotent consumer. Do not use application-level dual writes.

## Consequences

Positive:

- strong transactional behaviour for human workflow;
- efficient indexed queue and case queries;
- standard optimistic locking and idempotency patterns;
- clear separation between operational and analytical workloads.

Costs:

- another managed data service and backup plan;
- defined replication and reconciliation are required;
- data ownership must be documented field by field.

## Revisit conditions

Revisit only if a design partner requires an entirely Snowflake-native
deployment and a measured proof shows Snowflake can satisfy the operational
latency, concurrency, isolation, and transaction requirements without coupling
application users directly to Snowflake.
