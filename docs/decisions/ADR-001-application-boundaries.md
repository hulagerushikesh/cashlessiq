# ADR-001: Separate product UI and API from Snowflake sessions

- Status: Accepted by Rushikesh on 18 October 2026
- Date: 15 October 2026

## Context

The hackathon reviewer console is a Streamlit-in-Snowflake application. It
successfully demonstrates governed access and decision review, but it couples
browser UX, Snowflake identity, SQL access, agent execution, and persistence.
That coupling makes public application identity, asynchronous work, integration
APIs, frontend performance, and independent scaling difficult.

## Decision

Build a Next.js web application that communicates with a FastAPI application
service. The browser does not connect directly to Snowflake. Snowflake access is
implemented through backend gateway interfaces and worker processes.

Streamlit remains a demonstration and internal diagnostic surface during the
migration; it is not the long-term transactional product interface.

## Consequences

Positive:

- product identity is independent from Snowflake users;
- frontend and backend can be tested, deployed, and scaled independently;
- long-running work can move to queues and workers;
- integrations receive stable versioned APIs;
- Snowflake remains replaceable behind testable ports where appropriate.

Costs:

- an additional application and identity tier must be operated;
- authorisation must be implemented consistently outside Snowflake as well as
  within governed Snowflake access;
- data synchronisation boundaries must be explicit.

## Guardrails

- No browser-held Snowflake credential.
- No policy arithmetic in frontend or route handlers.
- No duplicate authorisation rules scattered across pages.
- Snowflake masking and row controls remain defence in depth, not the sole
  application authorisation mechanism.
