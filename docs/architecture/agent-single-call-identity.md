# Prepared single-call identity launcher — 27 November 2026

`ciq_api.agent_single_call_identity` supplies the permanent numeric identity
transition needed by the reviewed custody, receipt and provider entries. It is
included in the public review source; no service, installer, route or host adapter
selects it. It does not install accounts, issue consent, stage private files,
provision history, enable SQL, launch a test session or grant network access.

## Fixed transition

A separately reviewed host must start a fresh, isolated `-I -B` Python process
as real/effective/saved UID and GID zero, with null stdin, separate private output
pipes and only the locale environment. The module imports only standard-library
code before privilege loss. The package, interpreter, dependencies and all parent
directories must be independently verified root-owned and immutable to all three
peer identities; this module does not attest its own installation. It must never
be made setuid, exposed through a general sudo rule or offered to browser/IPC
callers as a privilege service.

The sole argument selects one source-defined target: custody 53002, receipt
53003 or provider 53004. The host must reserve and verify those numeric identities
before any use. No UID, GID, command, module, path, plan, credential, environment,
retry or timeout selector is accepted. Unknown/additional arguments fail closed.
The old canned fake service units remain unchanged.

Before transitioning, the helper rejects nonisolated or multithreaded execution,
unexpected environment, inherited/ambient capabilities and inappropriate standard
streams. It closes every inherited descriptor above two using bounded `/proc`
inventory, makes the three standard descriptors survive exec, fixes core limits
to zero and file limits to 64, sets umask 0077 and changes directory to `/`.
The trusted fresh launcher must not install descriptor-opening signal handlers.
No private file or application entry is opened/imported while privileged.

It sets `no_new_privs`, disables keep-caps and clears ambient capabilities, then
clears supplementary groups **before** setting all three GIDs and all three UIDs
to the fixed identity. Every transition must succeed. Fresh kernel observations
must show the exact permanent identity, empty supplementary groups, no new
privileges, and zero inheritable/permitted/effective/ambient capability sets.
Any partial failure terminates without executing an application entry.

Only then does it exec `/opt/cashlessiq-agent/venv/bin/python -I -B -m` with the
selected fixed runner module and `LANG=C.UTF-8`. No fork, background process,
shell, PATH search, descriptor transfer, credential fallback or retry occurs.
An exec failure has one fixed redacted error. The existing runner guards remain
strict and run again in the new interpreter. Linux preserves `no_new_privs`
across exec and it prevents gaining privileges through setuid or file
capabilities ([Linux manual](https://man7.org/linux/man-pages/man2/PR_SET_NO_NEW_PRIVS.2const.html)).
UID transitions and capability retention have distinct rules, so checking all
four resulting sets is required rather than assuming a UID change suffices
([capabilities](https://man7.org/linux/man-pages/man7/capabilities.7.html)).

## Evidence and remaining host boundary

Offline checks exercise the fixed exec wiring, initial-state denials, permanent
transition order, inherited descriptor faults, syscall failures, residual
capabilities and fixed output. Network-disabled disposable Linux CI deliberately
starts with unwanted supplementary groups and an inherited root-only file
descriptor. Under each identity, the actual transition passes the unchanged
runner/peer guards, closes that descriptor, denies regaining root/groups, and
permits only its own dummy private file. Actual fixed-path exec enters each
selected runner and fails on its absent private plan. Unknown arguments and
inherited database configuration are rejected by the launcher itself.

The three-runner coordinator fixture now performs this actual transition before
running the runner compositions, replacing the earlier Popen UID/group setup.
It still substitutes SQL and HTTPS work and maps history to owned fixture
storage. It does not test real provider traffic or installed systemd operation.

The privileged host still needs its own bounded launch methods, exclusive lease,
fresh consent and plan/history checks, exact installed source verification,
separate credential delivery and effective whole-cgroup cleanup. The helper
neither creates nor verifies cgroups, read-only mounts, CPU/memory/task policy,
network isolation or original-incarnation ownership. A process group alone does
not establish whole-cgroup cleanup. Its process lifetime also needs an external
bound covering this transition and exec, before the runner's alarm is armed.
Filesystem isolation and a reviewed egress boundary remain necessary. No durable
clock or history rollback fence is established here. No live attempt is enabled.
