# One-shot clinical claim process

24 November 2026. Fake-only source preparation. No service, deployed activation,
SQL migration, new approval, live provider or paid cloud action is enabled.

`ciq_api.agent_claim_runner` replaces the test-only clinical claim helper in the
[app-to-executor acceptance](agent-request-execution.md). It claims one exact
operator-selected saved intent, emits the committed small `ClaimReceipt` and
exits. It cannot scan a queue, configure protected bindings, create allowance,
select a tenant/actor/grant, submit a child, retry, recover or finalize a review.
Independent database approval remains required; the plan is not that approval.

## Fixed operator delivery

An operator prepares `/run/ciq-agent-claim/claim.json` outside application data,
browser input, CLI arguments, logs and backups. Its strict bounded JSON contains
only protocol `ciq-fake-claim-v1`, database name/OID, clinical login name/OID and
password, capture schema, request ID, job UUID and timeout (1–120 seconds).
No DSN, connection options, host, socket, executable, grant or retry field is
accepted. The password is excluded from the plan representation.

The file must be a single-link regular file, owned by the runtime UID, mode
`0600`, nonempty and at most 8 KiB. Descriptor-relative opening rejects symlinks,
including every ancestor. Ancestors must belong to root or the runtime UID and
have no group/other write permission. A nonblocking open rejects FIFOs before
reading. Missing, malformed, duplicate-key, extra-field or unsafe plans fail;
there is no creation, default credential, fallback or repair path. The runtime
UID and host administrator remain trusted; this is not protection against either.

## Process and connection boundary

The trusted supervisor launches the installed Python environment with
`-I -B -m ciq_api.agent_claim_runner`, no arguments, stdin closed and a clean
environment containing only optional `PATH`, `LANG`, `LC_ALL` and `LC_CTYPE`
(which CPython can add during locale coercion). The runner
requires Linux, a single nonroot real/effective/saved UID and GID, no unrelated
supplementary groups, zero inherited/permitted/effective/ambient capabilities
and `NoNewPrivs=1`. It disables core dumps and arms a twenty-second alarm before
reading the plan. The supervisor must still bound resources and reap its child;
this module does not provide a service manager, container or production sandbox.

The connection is constructed from fields to fixed `127.0.0.1:5432`; no remote
host, Unix socket, libpq environment or service-file selector is accepted. It
uses no pool reuse, a three-second connection timeout, five-second statement
timeout, two-second lock timeout and eight-second idle transaction timeout.
On every physical connection, before exposing it to the claim command, a fixed
catalog query checks exact database/login names and OIDs, equal session/current
identity, a nonadmin NOINHERIT login, no role membership in either direction and
no database ownership. This does not replace the independently reviewed full
[installation/ACL inventory](agent-controller-installation.md).

The original protected `claim_requested_fake` still checks independent authority,
fresh clinical scope and exact queue contents. Python validates the canonical
intent digest before commit. Only a confirmed claim is written to stdout, with
no clinical snapshot, password or transferable submission permit. All failures
use one fixed error and exit status 1, with no traceback or driver detail. Lost
output after commit is uncertainty: launching again cannot adopt/reclaim it.
The engine is disposed on success or failure; no retry loop exists.

## Verification and next activation work

Offline checks cover plan selectors, secret representation, unsafe files and
ancestors, strict JSON, identity pins, fixed connection construction/disposal,
process restrictions and error redaction without connecting to PostgreSQL.
Disposable combined acceptance launches this packaged module under the actual
clinical UID with only its private dummy plan. It continues the existing valid
and invalid-result HTTP journeys and denies a second launch. Six extra actual
process cases deny changed database/login OIDs, public credentials, libpq
environment injection, a different UID and root before consuming the intent.
The trusted test supervisor kills/reaps each child and removes only its owned
plan directory. Existing outer container resource and cleanup guards remain.

This supplies the clinical one-shot process, not the full production operator.
Separate original-custody startup, trusted exact-operation assignment, receipt
peer supervision, production secret delivery/rotation, resource/quiescence and
restore/reauthorization remain to integrate. The combined canned child still
shares its custody UID; it is not live source/provider isolation. There is no
Compose/systemd/startup registration, runtime-bundle inclusion or GCP deployment.
Governed Snowflake source and provider status/usage reconciliation remain later
gates, followed by an explicitly approved build and joint testing window.
