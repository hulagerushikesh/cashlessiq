# Atomic private-plan delivery in disposable CI

24 November 2026. This is a trusted synthetic test-fixture improvement, not
production credential delivery, rotation or service activation.

`scripts/agent_service_plans.py` stages complete in-memory dummy plans at four
fixed targets: clinical claim, custody, receipt and canned candidate. Each has
a fixed service UID/GID and size bound. Its entry point requires root Linux,
the exact opted-in GitHub repository and complete-journey opt-in. There is no
CLI, caller-supplied path, password source, database call or activation command.

The complete journey requires stopped-service evidence before delivery, including
the custody unit for its candidate. The trusted fixture must still exclude
concurrent activation and pin account identity and installed code separately.
The observation is not a lock or authorization for production use or UID reuse.

Delivery walks `/`, `/run` and the fixed parent through directory descriptors.
Every directory must be root-owned, without group/other write permission;
symlinks are refused. A random exclusive staging leaf starts private, receives
all bytes with short-write handling, then receives the fixed ownership, exact
`0600` mode and file sync. Its type, ownership, link count and size are checked.
An atomic hard link publishes the complete inode only if the final name is
absent; existing files, directories and dangling symlinks cannot be replaced.
The temporary name is removed, the directory synced and final inode identity
and single-link status confirmed. No service starts inside this helper.

Any error denies delivery with one fixed diagnostic. Failure after publication
can leave the final name present, or two links after temporary-unlink failure;
neither permits activation or automatic retry. Owned temporary/final evidence is
retained for the supervising fixture's later, independently quiescent cleanup.
No private bytes, hashes, filenames from exceptions or underlying errors are
printed. Retention is not secure erasure or independent backup.

The primitive does not validate clinical/credential JSON semantics; the installed
runner retains its strict schema and private-file validation. Service UIDs and
root remain trusted. This does not defend against same-UID mutation, concurrent
root changes, compromised local PostgreSQL, process-memory disclosure or host
loss. Production protected-source acquisition, activation exclusion, identity
incarnation, database/session retirement, rotation and restore reauthorization
remain open. There is no new browser capability, live secret or provider call.

Local acceptance passes 126 focused service checks, including 34 delivery cases,
plus changed-file Ruff and whitespace checks. The Linux complete service journey
is the integration gate for actual ownership, fixed paths and packaged readers.
No local Docker, GCP resource, application runtime or service policy changed.

The [Linux service journey](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45382439775/job/138404649536)
passes at source `f074b8fc0e1f8dead3a754c51f96985e644d1544`: all three scenarios
and fifteen actual service invocations accept the delivered files under unchanged
unit policies. Source-matched installation and owned service, plan, account,
runtime and loopback database/tmpfs cleanup all pass (seven fixed markers).
The broader foundation and ledger/peer jobs remain in progress at this receipt;
their completion must be checked before claiming the whole workflow passed.
