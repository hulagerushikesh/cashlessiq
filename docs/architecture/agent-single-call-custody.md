# Prepared single-call custody — 27 November 2026

The captured-product comparison now has an **inactive assembled attempt**:
request preparation, matching receipt/provider scope, retained issue, one raw
response, retained observation and a consumed clinical candidate handoff.
No application route, worker, installer, runner or service selects it. It cannot
replace the fake-only controller or authorize a live call. In particular, supplied
`AgentContext` values remain trusted assertions, not fresh database authorization.

## Original attempt

[`PreparedSingleCallCustody`](../../apps/api/src/ciq_api/agent_single_call_custody.py)
requires the exact snapshot, one-shot configuration, reviewed call pin and exact
receipt/v2-provider client classes. Construction performs no IPC or provider I/O.
It recomputes the body/configuration/binding/source hashes, pins the internal
operation UUID and matches configured seconds/tokens to the reviewed ceiling.
For this profile, `source_sha256` hashes the entire canonical captured `AgentInput`.
It is **not** an independent Snowflake source observation or legacy ID mapping.
Both clients must match the SHA-256 of the full UTC-canonical reviewed call pin.

```mermaid
sequenceDiagram
    participant C as Original custody (53002)
    participant R as Retained receipt (53003)
    participant P as Provider (53004)
    C->>C: Consume private pending body; check supplied scope and deadline
    C->>R: Issue exact reviewed pin
    R->>R: Commit issue; hold full uncertainty
    R-->>C: Authenticated matching acknowledgment
    C->>P: Full pin + exact prepared body (one exchange)
    P->>P: Match private v2 plan before reading PAT
    P-->>C: Full pin + body digest + bounded raw response
    C->>R: Response digest + observed ID + unknown token counts
    R->>R: Commit immutable observation; retain full uncertainty
    R-->>C: Authenticated matching acknowledgment
    C->>C: Consume private reply under fresh supplied scope
    C->>C: Validate exact candidate; hand off once to future protected publisher
```

`dispatch(current)` returns `None`. It consumes the original pending body before
checking scope or making any call. Only a successful original issue acknowledgment
can precede provider exchange. A receipt status query, retained issued row or new
controller object cannot reconstruct permission after issue. No database connection is owned
by this assembly, and no caller can inject raw responses, callbacks or candidates
through its methods. Trusted code and shared-UID memory remain trusted boundaries.

The original monotonic deadline covers scope validation, issue IPC, provider I/O,
observation and candidate handoff. The total envelope is eighteen seconds: two
two-second receipt budgets, the twelve-second provider process budget, one second
for process cleanup and one second for validation margin. This is a conservative
admission envelope, not an absolute host scheduling or kernel syscall guarantee.
Receipt/preparation time is subtracted before provider launch, with four seconds
reserved afterwards. Provider budget is never extended beyond twelve seconds and
must exceed the configured model budget by more than two seconds. The one-shot
configuration must therefore fit the reviewed one-to-eight-second provider range.
The window and observed wall-clock rollback are checked between stages. A fresh
host/external clock fence, cancellation and live revocation remain separate work.

`take_candidate(current)` consumes only the original private reply. It validates
fresh supplied clinical context, the exact internal UUID/binding, shared-rule
money/outcome/ordered lines and owned hashed citations. It returns an advisory
comparison; it does not write a decision, comparison row, audit or outbox. A future
protected publisher must invoke it and persist the result inside its fresh locked
transaction. No candidate survives a denied/failed handoff for automatic retry.

## Provider scope and response association

[`ReviewedProviderPeerClient` and `ReviewedProviderPeer`](../../apps/api/src/ciq_api/agent_provider_peer.py)
use separate v2 request/response markers containing the full pin digest, followed
by the existing bounded body/digest framing. The endpoint, Linux `SO_PEERCRED`,
UID/GID/process/path guards and single-use lifetime remain the existing ones.
V1/v2 cannot downgrade into each other. The reviewed server calls only the
separate `PrivateProviderAttempt.exchange_reviewed` entry.

The private provider-owned `0600` plan contains the entire canonical reviewed pin,
with no separate host/body overrides or asserted hash. Its exact structure is:

```python
plan = {
    "protocol": "ciq-private-provider-v2",
    "pin": json.loads(reviewed_pin.canonical()),
}
```

The provider recomputes the full pin hash and derives its actual hostname and body
hash from that same committed object. Changing only the private hostname cannot
redirect an otherwise correctly pinned call. The private v2 file is bounded to
4096 bytes; duplicate keys and non-finite values fail before credential access.
The separate v1 entry still requires its exact v1 plan. All plan/pin/body/hostname
checks precede the private credential read. Plan matching does not prove owner
consent, actual PAT principal/role, immutable model revision or provider pricing.
Trusted future provisioning must establish those associations and outer policy.

[`agent_single_call_response.py`](../../apps/api/src/ciq_api/agent_single_call_response.py)
shares the strict bounded complete-envelope parser with captured response checks.
The first synchronous response has no independently known provider run ID. This
entry records that ID as **observed** and associates the raw response digest with
the original custody's authenticated, body/pin-matched exchange. It never copies
the ID into an expected-ID parameter and calls that verification. The captured
decoder's independent expected-ID requirement remains unchanged. Pure parsing
alone does not prove provenance; only the original custody owns these raw bytes.

There is no reviewed token-count mapping for the provider's variable usage
objects. Both normalized counts stay null, including when unverified fields
contain zero. No claim of zero cost or invoice reconciliation follows. The full
reserved units remain uncertain after observation. These units are not dollars.

A valid completed envelope with invalid clinical content can be retained as
observed and then rejected at handoff. Client tools, mixed tool/text, multiple
final texts, changed money/citations/bindings and stale scope cannot be accepted
or repaired. Failed/malformed aggregates stay issued with full uncertainty.
Observation failure or a lost acknowledgment prevents candidate handoff even if
the receipt commit succeeded. No retry, refund, reset or continuation is added.

## Acceptance and remaining activation gates

Offline acceptance exercises actual local sockets/SQLite with only the OS guards
and remote attempt replaced. It covers pin/type changes, original/reconstructed
controllers, competing dispatch/handoff, lost issue/observation ACKs, provider
failure, malformed/incorrect answers, revoked/stale scope and decreasing deadlines.
All thirty golden clinical cases also exercise the synchronous final decoder.

The existing bounded, network-disabled, read-only-root Linux receipt container
includes five assembled controls under actual custody/receipt/provider UIDs. They
use private random dummy credentials and the actual isolated HTTPS worker, replacing
only the worker's remote exchange. They check success/reconstruction denial,
private-plan mismatch before PAT access, lost issue ACK without a provider launch,
lost observation ACK and rejected clinical content. No new container or local
Docker invocation is needed. Hosted execution must pass before claiming Linux
acceptance; the `/run` fixture is not persistent/off-host recovery evidence.

The remaining steps are concrete and separate:

1. Implement protected product admission/dispatch/publication commands for the
   single-call profile: current owner consent, tenant/principal/policy/review
   state, revision/config/source/identity pins and revocation under locks. Supplied
   booleans/hashes are insufficient. Keep the existing fake-only SQL gates intact.
2. Provision the independent journal and reviewed v2 provider identity/plan under
   a manual supervised runtime, with retained-history recovery, credential
   delivery, UID ownership, outer filesystem/network/cgroup policy and deadline
   fencing. Missing/rolled-back retention must never become fresh authority.
3. Review the actual provider model/identity, supported aggregate shape, token
   reporting and expected latency using an explicitly approved synthetic call.
   Review exact attempts, time window and expected spend before any paid action.
4. Run bounded GCP and joint UI acceptance only after the protected integration
   and runtime package are reviewable. The generic three-attempt job worker must
   not acquire provider retry authority.

This completes prepared assembly, not live agent integration or source parity.
No paid resource, real credential, account setting or local container is activated.
