# P2 local validation and credential boundary

Date: 19 October 2026. Status: **design approved; first offline primitive implemented**.
Parent: [approved isolation architecture](../product/p2-isolation-proposal.md).
Scope: local-only synthetic P2; TPA001/GOL001 and TPA003/GOL024/GOL027.

Rushikesh explicitly approved this design, including two additional validator
identities. This approves offline implementation, not provisioning or live reads.
See the [implementation checkpoint](../product/p2-worker-boundary-checklist.md).
The offline broker now resolves fresh database membership with issuer-qualified
identity, issues internal-user UUID assertions and uses fixed summary routes.
Offline delegation is now implemented with a broker-signed read-detail assertion
enclosing a separately audience-bound summary capability. Their subject/tenant/
disclosure/case/lifetime and parent nonce must match. Readers only forward the
broker-signed child; they cannot mint capabilities. Fixed reader/disclosure
peer-policy checks initially used an injected test identity. An explicit loopback
mTLS adapter now tests certificate-derived identities on both worker hops, with
required certificates, pinned leaf/URI identities and server hostname checks.
See [transport evidence and remaining gates](p2-worker-transport.md).
Container/private-network transport, secret delivery and database isolation are
not implemented by this local composition; the design below remains the target.
An optional same-host SQLite replay candidate now passes atomic multiprocess and
retained-state restart tests. It is not activated; shared-file custody, mount and
lifecycle review remain required, and the default ledger is still process-local.

## Decision proposed

Use separate local worker containers for each tenant/disclosure class, plus a
separate trusted validator for each tenant. Keep the existing Next.js/FastAPI
application as the authenticated broker, not a holder of Snowflake credentials.
No public worker ports, cloud host, SPCS pool, new paid environment or persisted
assessment/projection table. This document does not edit Compose or start workers.

The approved architecture named four read identities but left the validator's
identity unresolved. This design proposes **two additional validator identities**:
six runtime Snowflake identities total, plus a separate non-runtime governance
owner. The owner approved this design expansion; exact principal/grant package
and provisioning still require their separate reviews. None was created here.

| Component | Count | Source authority and output |
| --- | --- | --- |
| Web | 1 existing | No Snowflake secrets; authenticated v2 presentation only |
| API broker | 1 existing | Fresh JWT/membership checks; fixed server routing; no Snowflake secrets or raw decision inputs |
| Nonclinical read worker | 2 | One tenant's metadata/history/clause-reference projections; no conditions, raw decisions or clinical fields |
| Medical read worker | 2 | One tenant's approved medical projections; conditions only for current medical membership; no arbitrary raw export |
| Trusted validator | 2 | One tenant's narrowly projected full saved decision and independent validation inputs; returns summary-only observation |
| Governance owner | Non-runtime | Owns reviewed definitions; never a runtime user role or mounted credential |

Processor and auditor use the same nonclinical disclosure class, not the same
application membership. Validators are clinically trusted processes even when
their output is nonclinical. Neither their identity nor their input views may
be reused by nonclinical readers. Medical readers do not inherit validator roles.

## Request path and invocation authority

1. Broker verifies the current application JWT and loads active PostgreSQL
   membership. Reject unknown/revoked membership before worker/source I/O.
2. Fixed server configuration selects tenant and disclosure worker. Browser
   headers, request parameters and tokens cannot select a Snowflake identity,
   SQL text, connection target, worker URL, role or clinical disclosure flag.
3. Broker issues a short-lived, audience-bound internal authorisation assertion
   with subject, tenant, disclosure class, operation, case/filter bounds, expiry
   and request nonce. No reusable Snowflake credential is in the assertion.
4. Worker verifies the assertion against a public verification key, pins its
   tenant/disclosure/audience and rechecks current membership via the trusted
   authorisation boundary. Failure or unavailable membership is denied, not cached.
   Queue calls do not invoke validators or infer recommendation availability.
5. On detail only, the read worker may invoke its own tenant's validator for a
   summary using an audience/operation-bound delegated assertion. Validator
   independently checks current membership and case allowlist before source I/O.
   Its only response operation is summary validation, never raw JSON/evidence.
6. Broker validates strict existing v2 output and rechecks active membership
   before delivery. Medical responses require medical membership at delivery.
   Return no-store; do not send raw exceptions, SQL or source payloads to clients.

Transport must authenticate both peers (proposed private-network mTLS with
per-worker certificates) and authorisation assertions must use asymmetric
signatures: verification-only workers cannot mint another identity's assertion.
Read workers hold no broker signing key. Do not reuse the shared local-auth
secret as a new cross-worker capability key. Existing local auth is a synthetic
test facility, not customer authentication or a sufficient worker trust boundary.
Internal assertion issuer, membership-check protocol, certificate/key lifecycle
and negative tests must be implemented offline before any live activation.

The broker is a trusted authorisation/clinical delivery boundary: it can see
approved medical responses, but no validator raw inputs. This does not claim
isolation from a compromised broker, host administrator or Docker daemon owner.
Container/network labels alone do not prove isolation; test peer denial.

## Snowflake access and credentials

For this local-only candidate, propose managed key-pair service authentication,
subject to CoCo review of exact supported setup and separate owner approval.
Workload identity remains preferred for a future compatible managed host, not
an assumption that this laptop has a workload identity provider. No key generation
or service-user creation is authorised here. Never mount operator OAuth/config,
the repository root, Docker socket or another worker's secret directory.

Owner-controlled encrypted secret storage must hold one distinct private key
per runtime identity. At activation, narrowly scoped read-only secret files are
mounted only into the matching non-root worker; no private keys in environment
strings, Git, images/build contexts, logs, browser bundles or ordinary .env files.
Exact secret-store/unlock/delivery mechanism and file ownership are approval
prerequisites, not an instruction to improvise a plaintext key directory.
The local host administrator remains in the trusted computing base.

Each worker pins its expected account/user/primary role and empty secondary
roles, verifies actual session context, and closes the session on mismatch.
No admin fallback, dynamic role switching, cross-tenant connection pool or
unbounded retries. Initially use one connection per operation, close on every
path, no persistent pool or warm-up query. Metadata privileges still include
PUBLIC; NONE does not remove PUBLIC. Do not claim no-AI/compute capabilities
until separately resolved. Workers contain no AI/app-startup execution path.

Readers get only approved explicit tenant views. Validators get only explicit
tenant input views sufficient for canonical checks, not eight base tables or
other tenants' views. No ownership, future grants, mapping writes, stage access,
alternate runtime roles or admin memberships. Match grants to actual view/column
inventory before SQL review; masking must not silently replace required inputs
with unusable strings. Do not grant CIQ_ADMIN to bypass masking.

## Validation semantics and consistent inputs

Package the existing cashlessiq-domain wheel with Python 3.11 in validators.
Connector/runtime dependencies belong to the worker package, not the pure domain
package or normal API image. Reuse canonical schema/arithmetic/citation/history
validation; never SQL scalar checks, SCHEMA_VALID, fabricated sanitized JSON,
LLM calculations or copied demo decisions as a substitute.

Each detail must validate independently owned, bounded input from a coherent
read. Require an implementation plan for one statement-level input snapshot
covering request/policy/product, estimate, saved decision selection and citation
registry; do not assume multiple SELECTs in a transaction share a snapshot.
Exact supported SQL and deterministic latest-row/duplicate handling need CoCo
review. If coherent input cannot be demonstrated, fail unavailable and do not
activate. No new persisted snapshot/backfill is permitted by current scope.

Validate the complete saved decision against that input, then return only the
existing immutable recommendation observation plus bounded scope/provenance
metadata for the read worker. No reasons, labels, raw JSON, clause text, record
payloads, calculation lines or validator input hashes exposed as clinical proxies.
No response cache initially. Any later cache requires a separate version-binding
and revocation design. Bound reads and memory; overflow/ambiguity fails closed.

SAVED means fresh canonical validation succeeded. MISSING requires confirmed
owned context and truly absent saved decision. Invalid, ambiguous, stale,
unresolved evidence, denied input or connection failure means unavailable, never
MISSING, empty success, zero payable, a demo fallback or DENY. Preserve integer
rupees and uncomputed QUERY/REFER null-payable semantics. No public v2 contract
change or full financial trace is approved by this design.

## Implementation and acceptance gates

1. Approve/revise this design, including two extra validator identities and the
   trusted broker/host boundaries. No provisioning follows automatically.
2. Implement internal invocation/authentication, strict observations and worker
   routing using fake gateways and disposable local tests only. Keep existing
   live routes disabled; do not install secrets or start Snowflake connections.
3. Prepare exact SQL/principal/view/column/secret-custody/rollback inventory and
   coherent-input query for CoCo review. Mark uncertain syntax VERIFY WITH COCO.
   Resolve relevant preflight gaps from existing evidence where available.
4. Obtain separate exact provisioning and statement/time/credit-capped functional
   test approvals. Retain $50 reserve; trial balance/expiry are not freshly measured.
5. Test foreign-known-ID/broad-read/base-table denial, direct peer access denial,
   forged/replayed/wrong-audience assertions, expired/revoked/downgraded membership,
   secret-mount separation, overflow, changed/ambiguous evidence and no-fallback
   states. Cross-tenant failure blocks activation. Retest medical delivery after
   downgrade; do not claim instantaneous cancellation of already-running reads.
6. Local live acceptance only after security tests pass. No website deployment,
   P3 or push without its separate authority. Rollback disables new routing first,
   stops workers, revokes only new runtime access and retires exact new secrets;
   owner/grant attachment changes restore captured original state.

Current code remains the operator-oriented SourceCaseRepository composition:
it receives raw inspection rows inside the API process. It is **not** the above
isolated runtime. Existing fake-gateway tests do not prove worker, credential,
Snowflake or snapshot isolation. No source activation can reuse that shortcut.
