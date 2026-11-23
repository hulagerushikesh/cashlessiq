# Consuming an app request through the synthetic executor

23 November 2026. Source and disposable acceptance only. No deployed service,
new migration, live provider, credentials, paid allowance or GCP start is enabled.
The normal backup still contains 22 tables. This extends the
[held request workflow](agent-request-intent.md).

## One intent, one claim

`ControllerReservation.claim_requested(request_id, job_id)` uses a separately
authenticated clinical connection. This method calls only the protected
`claim_requested_fake(text, uuid, integer)` command; the runtime cannot read or
update queue tables directly. A saved intent is not authority: an independently
staged, enabled, exact fake reservation approval and principal binding must
already exist. Tenant, actor, grant, epoch, snapshot, configuration, source and
clock are never selected by browser fields or this method's arguments.

The command locks epoch, principal/approval and fresh clinical scope before the
intent and allowance/operation. It requires the exact assigned officer, current
approved input/review/evidence binding, held state, zero generic attempts, no
lease/result/error and the expected two-field intent payload. Any existing
operation for the request blocks consumption, including expired/unknown work.
Concurrent claimers serialize; only one can proceed.

Reservation, the original bounded lease and changing the intent to
`executor_claimed` commit together. The queue result is only the operation ID;
generic attempts stay zero. Python verifies the canonical binding digest before
commit, rolling back both the intent transition and hold on mismatch. No attempt,
external issue, comparison or human decision is created by claiming. A lost
acknowledgement/crashed claimant cannot claim the intent again or acquire a new
lease automatically. The recorded operation is status, not a replay permit.

## Separate original custody

The clinical claim cannot configure custody. A trusted operator must explicitly
pin the separate custody principal to that exact operation. This remains a
trusted disposable setup step in CI; no runtime self-grant or owner-connected
fallback was added. A production supervisor, secret delivery, bounded operator
installation and restore/reauthorization remain separate activation work.

`FakeCustodySubmission.run()` then performs prepare, fixed fake dispatch and
validated publication through one original coordinator. It accepts no arguments,
returns no permission or clinical candidate, stops on the first failed stage and
does not retry. Missing transport is rejected before preparing. Existing full
receipt-history verification, original deadline/fence, independent issue marker,
private response validation, exact money/evidence checks and atomic accounting
are reused. No database connection is held across child I/O. Invalid/uncertain
submitted work retains allowance; it is never automatically replayed/refunded.

The existing medical-officer read endpoint exposes the validated result after
publication and remains read-only. Human review/audit/outbox records stay intact.
The generic worker and its three-attempt retry are still excluded.

## Acceptance and limits

Accepted code `c980ff8e9db3fd449b284b8b59e2b81567f0358a` passes
[product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45219672723)
and [private-preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45219672827).
The restricted command suite passes 313 cases, including all 23 new intent-claim
cases; installation/ACL/retirement passes 53, restricted encrypted restore 27,
and combined peers/execution/restore 22. Product regression passes 2,407 API
checks, 69 client checks and eighteen MVP browser journeys. The private preview
also passes eighteen journeys, encrypted restoration and saved-workflow reopening
after restart/restore. Both workflows confirm owned stack cleanup. Offline
verification passes 199 selected reservation/custody checks and repository Ruff.

Offline tests cover strict intent IDs/timeouts, digest/projection validation
before commit, fixed errors and missing transport. Dedicated PostgreSQL tests
cover real HTTP intent, restricted atomic claim, concurrent claimers, stale or
malformed intent, disabled authority, existing operations and denied table access.
The combined peer acceptance adds an HTTP-to-result journey: a separate clinical
OS UID claims using only its own login, a trusted dummy operator pins custody,
and separate custody/receipt UIDs complete one bounded child exchange. A second
journey supplies invalid money and verifies no result, no retry and retained
allowance. Both assert unchanged human records and denied nonclinical reads.

The fixed canned child is not Snowflake/source parity or production transport
isolation. It still shares the custody UID in this combined harness; the separate
transport containment suite covers a different boundary. Same-host receipt
custody does not establish independent host-loss or both-store rollback safety.
No continuous queue scanner, worker startup, service, container activation or
deployment is supplied. Governed source mapping, live provider/checkpoint/usage
reconciliation and separately approved paid testing remain outstanding.
