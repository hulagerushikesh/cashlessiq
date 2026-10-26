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

The same CI job now also creates a **second, independent Compose project with a
new empty PostgreSQL volume**. It restores the saved dump there before starting
that project's API, web and loopback gateway, compares all 17 table manifests,
then repeats the fresh-browser saved-workflow check on port 3081. The original
preview remains available on port 3080. Both CI volumes are removed after the
test. This exercises recovery when the original database volume is unavailable,
without deleting the owner's local data or requiring cloud infrastructure.

This proves that the current synthetic data can be backed up and restored, and
that the disposable preview can restart with saved data. The fresh-volume step
checks a replacement volume in the same CI runner; it does not yet prove
off-machine backup custody, loss of the whole host, application compatibility
with a future migration, or uptime during restart.
The owner should keep using the local app for testing; no GCP resource, billing
link or paid service is involved.

## Verified result

The existing local sandbox restored and matched all **17** MVP public tables in
a separate temporary database; its database and application services were not
restarted. The accepted code at `0aa135a` passed
[disposable owner-preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40291695183):
37 gateway HTTP checks, 13 full MVP browser journeys, a consistent backup and
restore matching all 17 tables, a database restart with all tables still equal,
and one fresh-browser check that reopened the previously saved request, active
policy, released fictional PDF and final review. The preview volume and services
were removed after the run.

The same accepted revision passed
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40291695193):
915 root tests, 1,521 API tests, 72 membership checks, 35 PostgreSQL catalog
checks, 41 client checks, 26 existing browser checks, 15 source UI checks and
13 MVP browser checks, plus the type, lint, contract and production build gates.
