# Product Phase P0 checklist

Last updated: 18 October 2026

## Deliverables

- [x] Product statement and initial scope
- [x] User personas and canonical workflows
- [x] Target frontend, backend, worker, and Snowflake boundaries
- [x] Transactional and analytical data-store responsibilities
- [x] Hackathon-to-product migration sequence
- [x] Initial threat model and data-handling constraints
- [x] ADR for application boundaries
- [x] ADR for the transactional store
- [x] ADR for identity and tenancy
- [x] Initial non-functional requirements and launch gates

## Approved product-owner decisions

Approved by Rushikesh on 18 October 2026: “Approve the recommended P0 decisions and push.”

- [x] Indian TPA as the initial customer.
- [x] Hybrid managed application and customer-governed Snowflake as the default direction.
- [x] PostgreSQL as the operational workflow store.
- [x] Next.js plus FastAPI as the application stack.
- [x] The currently implemented and evaluated Arogya Sanjeevani policy as the first supported product.
- [x] Synthetic data for the initial pilot; controlled de-identified data follows the documented real-data launch gates.
- [x] The TPA/core system remains the legal system of record initially; CashlessIQ maintains its own immutable audit trail.

## Evidence required before Product Phase P1 exits

- Interview notes or validated assumptions from at least five target users.
- A selected identity provider approach for local, staging, and customer SSO.
- A field-level ownership and data-classification matrix.
- A working local web-to-API authenticated request.
- CI passing without a Snowflake account.
- No regression to the hackathon prototype or its golden rules tests.

## Phase state

Product Phase P0 is **complete**, with documentation and product-owner decisions
approved on 18 October 2026. Product Phase P1 may begin with contract protection
and the product foundation described in the migration plan. P1 exit evidence
above remains outstanding.
