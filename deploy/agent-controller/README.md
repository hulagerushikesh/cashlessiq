# Agent activation review package

25 November 2026. Source review and rebuild inputs for the synthetic agent
services. Installation and activation remain disabled. The service runners
accept only the fake protocol; this package does not enable Snowflake execution.

## Prepare and verify

From a checkout containing the independently selected full commit SHA:

```sh
python -m scripts.package_agent_review create --revision FULL_COMMIT_SHA
python -m scripts.package_agent_review verify output/agent-review/cashlessiq-agent-review-FULL_COMMIT_SHA.tar.gz --revision FULL_COMMIT_SHA
```

Replace `FULL_COMMIT_SHA` with the reviewed forty-character commit. Verification
requires that commit in the local Git object database. Select it from the review
or CI receipt, rather than trusting the revision claimed by an incoming archive.
The tool does not fetch commits, extract files, execute packaged code, install
units, change accounts/grants or contact a cloud/provider.

The archive contains committed API/domain wheel build inputs, the API's frozen
runtime lock, migrations, six restricted-command SQL definitions, three manual
unit examples and this guide. Its fixed allowlist excludes owner media, working
files, credentials, generated output, legacy invocation helpers and test
launchers. Only Python/JSON files in the named code trees are admitted; other
assets require a reviewed allowlist change. Git blobs are read directly, without
working-tree substitutions or Git export transformations. Included source files
must be ordinary nonexecutable blobs. Dirty and untracked files cannot enter it.

`agent-review.json` pins the exact revision, each file's SHA-256 and disabled
activation state. Tar metadata and gzip timestamp are normalized, so repeated
packaging of the same revision in the same Python environment produces the same
bytes. Verification bounds compressed/uncompressed sizes and entries, rejects
links, duplicates, unexpected members, changed metadata and missing files, and
compares every byte against the independently selected Git revision. Updating
an archive's own hashes cannot conceal changed content. Existing destinations
are never replaced. No digest is an approval, signature or proof of source trust.

This is a review artifact, not a runnable offline installation: interpreter,
third-party wheels, built first-party wheels and deployment-specific private
material are absent. A later release builder must pin and verify those runtime
artifacts on the selected Linux target. The current Ubuntu systemd/loopback
PostgreSQL CI topology is not yet integrated into the Debian GCP preview.

## Operator handoff before installation

The existing Linux receipt is recorded in
[the source handoff acceptance](../../docs/architecture/agent-service-source.md).
It demonstrates synthetic service isolation and cleanup; it does not supply the
following deployment evidence:

| Item | Required operator/release evidence |
| --- | --- |
| Runtime | Reviewed revision, exact wheel/dependency/interpreter hashes, target OS/Python/systemd/cgroup support, bounded resources and verified installed bytes. |
| Linux identities | Three distinct static accounts with no extra groups, no conflicting names/UIDs, no prior installation, and confirmed whole-service quiescence. CI UIDs 53001–53003 are fixture assignments, not permission to reuse an account. |
| Database identities | Freshly verified database and LOGIN role OIDs, least effective grants, explicit clinical/custody assignment and approved immutable fake epoch. A restored name/password does not establish original identity or authority. |
| Private source | Selected protected custody, independently authorized acquisition, root-only input and service-owned atomic delivery. Current `scripts/agent_service_*` helpers are CI-only and must not be activated by removing their guards. |
| Receipts | Independently retained journal/storage, approved epoch/history and a fresh endpoint. Restoring product tables alone cannot reconstruct receipts, reset history or authorize another submission. |
| Coordination | One authorized supervisor through acquisition, delivery, starts, retirement and cleanup; stable stopped-unit/cgroup evidence. A cooperative lock does not exclude unrelated root or manual activation. |
| Spending | Exact cases, identities, attempt/allowance ceiling, test window, expected charges and explicit owner approval before any paid action. |

## Activation and retirement sequence to implement

1. Review the artifact and the evidence above. A missing or ambiguous item keeps
   activation closed; a successful package check cannot override it.
2. In a separately authorized inactive installation, verify code, accounts,
   database identities and existing state before creating any private inputs.
   Do not repair, adopt or overwrite an unknown installation or retained journal.
3. Acquire approved inputs through the selected protected source, then recheck
   coordination and stopped-service evidence before atomic delivery. Never place
   passwords in argv, environment, logs or the review package. Metadata checks
   supplement source authorization; they cannot create it.
4. For a bounded synthetic test only, confirm clinical claim and independent
   custody assignment, deliver required plans and the fixed canned candidate,
   then start receipts and verify readiness for that exact invocation before
   custody dispatch. The receipt idle window must not be consumed by preparation.
   Require a new explicit launch; no timer, boot enablement or automatic retry.
5. On uncertainty, hold accounting/state and block further delivery/activation.
   Stop owned units, verify stable empty cgroups, commit database revocation,
   close pools and establish session absence before credential retirement.
   Rotation alone does not restore approval. Keep retained receipts; never
   delete/recreate an endpoint or journal merely to make startup succeed.
6. Remove only invocation-owned disposable material after confirmed quiescence
   and authorization. Preserve uncertain/private retained state for reviewed
   reconciliation. Unlinking a file does not prove secure erasure. Stop the VM
   at the end of an approved test, with the automatic stop as a backstop.

This sequence is an implementation handoff, not shell instructions or an
installer. The synthetic fixture's successful cleanup is not a production
retirement/restore procedure.

## Source/provider work after the handoff

Follow the [source mapping contract](../../docs/architecture/agent-source-mapping.md)
and [integration sequence](../../docs/architecture/product-agent-integration.md).
First settle the exact governed registry, independently captured source
observations, tenant/clinical privileges and supported tool transport. Existing
Snowflake golden IDs and new PostgreSQL snapshots are separate input paths.
No implicit ID translation or legacy `run_agent` invocation is permitted.

The next provider adapter must preserve checkpoint-before-dispatch, uncertain
cost holds, strict money/citation validation and current human review authority.
Provider submission/status/reconciliation semantics and its latency budget still
need verification. Neither this review package nor the passing fake journeys
establish live provider parity or authorize another VM/build/Snowflake call.
