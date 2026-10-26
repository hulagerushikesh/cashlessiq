# Synthetic MVP recovery rehearsal — 26 October 2026

The earlier restore check proved that a pre-MVP `0001_identity` backup could
migrate forward. This check covers **current `0003_mvp` data**, including
requests, policy versions and activation, documents, job results, input history,
review decisions, comments, audit, command receipts and outbox events.

`python -m scripts.check_mvp_recovery --stack product` identifies the existing
owned Docker database and API containers, opens one read-only PostgreSQL
snapshot, and makes a private `pg_dump` from that exact snapshot. It restores
the dump into a new, uniquely named database on the same PostgreSQL server.
For every public table it compares column definitions, row counts and SHA-256
digests of sorted complete rows. The temporary database is then dropped.
The active database is never replaced, and the local web/API containers are not
restarted. The uniquely named private dump and hash manifest remain under ignored
`output/mvp-recovery/` for local recovery; the backup is limited to 100 MiB and
this rehearsal is limited to synthetic data. Backups contain the full fictional
records and should be handled as private files.

The disposable GitHub owner-preview workflow adds a second check. After its
normal end-to-end browser suite creates a complete fictional journey, it runs
the same backup/restore comparison. It then stops application writers, verifies
the database checkpoint, restarts PostgreSQL, verifies all tables again,
restarts API/web/gateway, and uses a fresh browser session to open the existing
request, active pinned policy, extracted PDF and saved medical review. The
restart option refuses to run outside the dedicated preview stack on GitHub
Actions. CI removes its entire disposable stack afterward.

This proves that the current synthetic data can be backed up and restored, and
that the disposable preview can restart with saved data. It does not yet prove
an off-machine backup, disaster recovery after loss of the source volume,
application compatibility with a future migration, or uptime during restart.
The owner should keep using the local app for testing; no GCP resource, billing
link or paid service is involved.
