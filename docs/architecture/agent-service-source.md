# Protected startup-plan handoff

24 November 2026. Disposable Linux CI acceptance; no live secret acquisition,
production installer, provider activation or cloud configuration change.

The service journey separates root-only acquisition from service-owned delivery.
Its trusted fixture atomically publishes the three dummy credential plans into
`/run/ciq-agent-supervisor`, a root-owned `0700` directory. Source leaves are
root-owned `0600` regular files with one link. Existing source directories,
including dangling symlinks, refuse installation before mutations. All source
files remain until confirmed service shutdown and coordinated teardown.

`scripts/agent_service_source.py` accepts only the three fixed credential roles
under the exact root/Linux/repository/CI opt-in. It walks directory descriptors
without following symlinks, refuses writable parents and requires the private
source directory. Leaves open read-only, nonblocking and close-on-exec. Before
reading it checks type, owner/group, permissions, links and the role's byte bound.
It reads at most the bound plus one byte, supports short reads, then compares
size, inode, metadata and modification/change timestamps against both the open
descriptor and the still-named entry. Descriptors close on success, ordinary
failure and interruption. Failures emit no source bytes or underlying exception;
the helper neither deletes nor repairs input files.

The cooperating supervisor checks its lease and stopped-service evidence both
before acquisition and again before atomic service-owned publication. Only the
canned candidate accepts a direct in-memory body; credential roles must use the
fixed source intake. Any uncertain acquisition/delivery/start permanently blocks
further delivery and activation. The service's existing strict JSON, protocol,
database/OID, authority and receipt validation remain required after delivery;
source metadata alone grants no authority.

For each source plan the Linux fixture attempts an actual read as each of the
three unprivileged service UIDs. All nine reads per scenario must fail with
`PermissionError` and no output before the source is delivered. Passwords and
source contents do not enter command arguments, environment or acceptance logs.
The existing three journeys then exercise installed units, SCRAM authentication,
publication/held results, revocation, password rotation and owned cleanup.

This is a tested local-file handoff boundary, not a selected live secret store.
The fixture creates random dummy credentials in trusted root memory. Root and
the installed service UIDs remain trusted; checks do not prevent hostile root,
transient root edits, UID reuse or reading one's own delivered plan. Retained
source and delivered copies are removed only by quiescent fixture cleanup;
neither unlink nor Python object disposal proves secure erasure. A live protected
source adapter, independent retained storage, real identity reauthorization and
governed provider integration remain separate engineering/deployment gates.

Local acceptance: 33 new checks cover fixed roles, unsafe objects, ownership,
bounded reads, changes during acquisition, descriptor closure on interruption,
early refusal, direct-credential bypass denial, permanent blocking and renewed
lease/quiescence evidence. All 150 focused source, coordination, delivery,
journey and quiescence checks and changed-file Ruff pass. Linux acceptance is
recorded separately after the pushed source completes its workflow.
