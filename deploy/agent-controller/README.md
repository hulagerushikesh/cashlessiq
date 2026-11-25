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
material are absent. The separate dependency bundle below supplies locked
third-party wheels; committed interpreter/build-tool pins are described below.
The interpreter archive and build-tool wheels are still downloaded during CI
preparation, rather than shipped in the source artifact. The current Ubuntu systemd/loopback
PostgreSQL CI topology is not yet integrated into the Debian GCP preview.

## Linux dependency bundle

```sh
python -m scripts.package_agent_dependencies create output/agent-review/runtime-FULL_COMMIT_SHA --revision FULL_COMMIT_SHA
python -m scripts.package_agent_dependencies verify output/agent-review/runtime-FULL_COMMIT_SHA --revision FULL_COMMIT_SHA
```

Creation downloads public PyPI wheels into a new directory. Verification uses
the independently selected commit's lockfile and makes no network calls. Both
commands leave accounts, services, databases and provider execution unchanged.
Use an existing parent directory and a fresh destination. Failed downloads retain
the incomplete directory without a completion manifest; never reuse that output.

The target is CPython 3.11 on Linux x86-64 with glibc 2.36 (Debian 12 baseline).
Only compatible pure/CPython/limited-ABI manylinux wheels are selected; macOS,
musl, ARM and newer-glibc-only wheels are excluded. The graph starts at the API's
normal dependencies, follows explicitly requested extras and excludes developer
groups and the optional Snowflake provider. Unknown markers fail for review.
Current selection: 32 wheels, 20,086,288 bytes. Each filename, size, SHA-256 and
public download URL comes from the committed lockfile. Input/output sizes and
counts are bounded. The manifest and hash-pinned requirements must match fresh
derivation from that commit; incoming self-reported hashes are insufficient.
Missing/extra/changed files, symlinks, hardlinks and special files are rejected.

The existing disposable Linux package and full-journey fixtures now install these
dependencies with indexes, cache and source builds disabled, then check installed
dependency consistency. First-party source-matched wheels are installed separately.
This checks an offline runtime dependency installation. CI preparation still
fetches the pinned interpreter and hash-locked build tools; subsequent first-party
wheel builds disable network/index resolution and build isolation.
No interpreter, first-party wheels, service accounts, private plans or receipt
storage are included in this dependency directory. It is not a privileged host
installer or proof that a destination host is safe to activate.

At `e04d72c`, the [Linux package check](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45639811705/job/139295015283)
and [full service journey](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45639811705/job/139295015253)
both passed with verified offline dependency installation and source-matched
API/domain code. All nine workflow jobs passed. This receipt covers the disposable
Ubuntu fixture; it predates the interpreter/build-tool pinning below.

## Interpreter and first-party build pins

`python-downloads.json` contains one CPython 3.11.15/Linux x86-64 GNU artifact:
standalone build `20260623`, SHA-256
`0604cd029b142dc223e131f17f5941c0c8d2d5074997c8178b515b19eea2a6c2`.
Metadata was selected from the
[uv 0.11.25 download inventory](https://github.com/astral-sh/uv/blob/0.11.25/crates/uv-python/download-metadata.json).
The disposable package/journey fixtures require uv 0.11.25 and pass this
single-entry metadata explicitly, with cache/config discovery disabled. They
request the complete platform/version key rather than a moving `3.11` family.
uv checks the supplied archive hash; the final installed-code probe also checks
the interpreter's actual patch version.

`build-requirements.in` selects Hatchling 1.33.0. The generated
`build-requirements.txt` fixes all six build dependency versions and distribution
hashes for Python 3.11. Regenerate deliberately with the reviewed uv version:

```sh
uv pip compile deploy/agent-controller/build-requirements.in --python-version 3.11 --python-platform x86_64-manylinux_2_36 --generate-hashes --only-binary :all: --no-annotate --no-header --output-file deploy/agent-controller/build-requirements.txt
```

The fixture stages the two effective pin files directly from the selected Git
commit into its fresh invocation-owned base; working-tree edits cannot change
them. It installs build tools with required hashes, no source builds and no cache
into a separate temporary builder venv. Both API/domain wheels are then built
using that environment with `--offline --no-index --no-build-isolation` and their
complete source contents checked. Build tools stay outside the service venv.
Existing root/CI opt-ins, inactive service policy and owned cleanup still apply.

This pins preparation inputs; it does not provide a fully offline release,
reproducible wheel-byte attestation, an independently verified uv executable,
Debian service acceptance or a production installer. At `f5ef75b`, the
[Linux package job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45642371334/job/139304168423)
and [complete service journey](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45642371334/job/139304168594)
both passed with these pins. No account, service or paid resource is activated
by the source package.

## Build from the selected commit

```sh
python -m scripts.package_agent_review stage /existing-owned-parent/fresh-source --revision FULL_COMMIT_SHA
```

This materializes the same allowlisted Git blobs directly into a fresh source
tree, without extracting an incoming archive. All inputs are validated before
output creation. Existing directories and symlinks are refused; interrupted
output is retained, and completion metadata is written last. Keep its existing
parent under the preparing user's control. This is public build preparation,
not a privileged installer or protection against another writer with that user's
authority. The command runs no build, interpreter download, service or database.

The Debian and Ubuntu package/journey fixtures now build both first-party wheels
from this staged commit rather than the checkout. API byte/inventory checks and
domain canonical-module, initializer and dependency checks use that same tree.
Dirty, untracked or newer checkout code cannot become a wheel merely by matching
another dirty working-tree file. Interpreter/build pins and runtime dependencies
remain derived from the same full revision. This prepares immutable source inputs;
it does not make the complete release offline or authorize host installation.

## Inactive Debian runtime rehearsal

The separate `agent-debian-package` CI job uses a fresh Debian 12/glibc 2.36
container, capped at 768 MiB, one CPU, 128 PIDs and six minutes. It obtains only
public build prerequisites; checkout credentials are not persisted and caching
is disabled. The Mac's Docker and the paid GCP VM are not involved.

`scripts/test_agent_debian_package.py` requires the explicit repository/CI opt-in,
Linux root, the exact OS/architecture/libc and a non-systemd container context
before installation. Existing install paths, private plan paths, service
identities or unit entries deny the rehearsal. It installs the same pinned
interpreter, isolated builder, source-matched wheels and offline runtime wheels
as the service fixtures, then repeats the inactive-state checks. Success removes
both invocation-owned artifact directories. The job container is discarded on
failure or timeout too; uncertain runtime state is never adopted or repaired.

This tests artifact compatibility and absence of agent provisioning on the
target OS. It creates no agent accounts, unit files, private inputs, database
connections or receipt journal and launches no agent services. Actual Debian
systemd/cgroup behavior, retained storage, production credentials and an inactive
host installer remain separate acceptance work. At `64e33ec`, the
[Debian package job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45644026747/job/139310026130)
passes the pinned interpreter/build, 32-wheel offline install, source/installed
code verification, inactive-state check and owned artifact removal. This is
Debian artifact acceptance; the systemd service journeys still run on Ubuntu.

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
