# Initial field ownership and classification

Last updated: 19 October 2026

This matrix defines ownership for the P1 identity slice and the next case slices.
Only synthetic identity data is currently seeded. Rows marked planned do not
represent implemented storage or synchronisation.

| Fields | Classification | Authoritative owner | P1 storage / access |
| --- | --- | --- | --- |
| Tenant UUID, name, active status | Internal | Application tenant registry | PostgreSQL; validated membership |
| User issuer and subject | Personal / security identifier | Identity provider for identity; application for mapping | PostgreSQL; identity resolution only |
| User UUID, display name, active status | Personal | Application user registry | PostgreSQL; own identity response |
| Membership tenant/user IDs, role, active status | Internal / security | Application access administration | PostgreSQL; API resolves every request |
| JWT, local bootstrap key | Secret | Identity issuer / local launcher | Cookie or process environment; not PostgreSQL or logs |
| Database credentials | Secret | Local launcher / future secret manager | Ignored owner-only env file locally |
| External request/policy/member IDs | Internal / potentially personal | Customer system | Planned tenant-scoped integration mapping |
| Patient name, phone, DOB | Personal | Customer member system | Planned governed Snowflake read; role-masked |
| Diagnoses, clinical text | Clinical-sensitive | Submitted evidence and governed member sources | Planned approved storage/Snowflake; role-restricted |
| Policy wording, UIN, version, clause IDs | Public source / internal annotation | Versioned policy registry | Existing Snowflake; product mapping planned |
| Executable rule parameters, approvals | Internal / financial logic | Human-approved policy version | Existing Snowflake; activation workflow planned |
| Extracted facts and corrections | Clinical-sensitive / financial | Versioned extraction and reviewer corrections | Planned versioned evidence records |
| Claimed/payable INR and calculation trace | Financial / clinical-linked | Deterministic domain result | Planned operational result + governed analytics |
| Assignments, comments, workflow state | Internal / potentially clinical-sensitive | Application workflow | Planned PostgreSQL |
| Final reviewer outcome | Financial / clinical-linked | TPA/core legal record; application audit of action | Planned transactional audit/outbox |
| Model/prompt/tool versions, timing | Internal | Assessment runner | Planned run metadata; no clinical text in logs |

Resolve `(issuer, subject)` to a user, then validate membership in the signed
tenant context. Revoking user, membership, or tenant access takes effect on the
next request, even if the token has not expired. Role is database-owned; it is
not accepted from the browser or copied from a token without membership checks.

Application workflow and the customer's legal system of record have distinct
responsibilities. Future exports use versioned outbox events; do not introduce
uncoordinated writes to PostgreSQL and Snowflake. Customer retention and
residency requirements remain prerequisites for real data.
