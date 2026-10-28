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

Each new `verified.json` binds the restored table inventory to the exact
`current.dump` byte count and SHA-256 digest. After copying both files together
to a private directory on another local filesystem, check the copy offline with:

```sh
python -m scripts.verify_mvp_backup /path/to/copied-backup-directory
```

The verifier needs no Docker, database or credentials. It refuses missing or
legacy manifests, changed dump bytes, symlinks and group/world-readable files.
Use a private filesystem that preserves restrictive file permissions (directory
0700, files 0600); encrypt before transferring beyond this Mac. A matching hash
detects accidental damage, but a manifest stored beside its dump is not a
cryptographic signature against someone who can alter both. No remote copy or
off-machine custody has yet been completed.

For an owner-selected off-machine destination, the local transfer helper can
encrypt a verified backup to a single GPG file. First make an encryption-capable
GPG public key available and check its **full fingerprint** with the key owner.
Keep the corresponding private key and its recovery method somewhere other than
the backup destination. The helper does not generate, export or upload keys.

```sh
python -m scripts.mvp_backup_transfer encrypt \
  output/mvp-recovery/REPLACE_WITH_BACKUP_ID \
  /path/to/private/backup.gpg \
  --recipient REPLACE_WITH_FULL_40_CHARACTER_FINGERPRINT
```

Only the verified `current.dump` and `verified.json` are included. The GPG file
is created privately and never overwrites an existing path. Copy that encrypted
file to the chosen storage by the owner's usual method. On a recovery host with
the matching private key, decrypt into a **new** private directory:

```sh
python -m scripts.mvp_backup_transfer decrypt \
  /path/to/backup.gpg \
  /path/to/new-recovered-backup
python -m scripts.verify_mvp_backup /path/to/new-recovered-backup
```

The helper bounds decrypted size, rejects unexpected archive members, and runs
the independent manifest check before exposing the recovered directory. It does
not restore a database. An exported GPG file is not an off-machine backup until
it has been copied, retrieved and decrypted with the intended recovery key on a
different host; those steps remain unverified for the owner's data. Losing that
private key can make the encrypted backup unrecoverable. The synthetic-only
limit and manifest authenticity limitation above still apply.
The current 17-table local backup completed one temporary-key encryption,
decryption and package-verification round trip on this Mac; its temporary key
and recovered copy were removed. This validates the helper against real
synthetic backup bytes, not cross-host key custody.
The automated transfer check also encrypts with a public-key-only GPG home,
confirms that home cannot decrypt, and recovers with a separate private-key
home. Both homes remain disposable and on one test host.

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

The fresh-volume job now routes those same backup bytes through the encrypted
transfer helper first: it generates a disposable GPG key, imports only its public
key into a separate encryption keyring, encrypts the verified package, decrypts
with the private keyring, checks the recovered manifest and uses **that recovered
dump** for the second volume. Temporary keyrings and plaintext transfer files
are removed after the restore. This is a same-runner CI recovery test; it does
not establish external custody or recovery on a different host.
The [accepted run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40693580097)
passed the encrypted restore, then reopened the saved synthetic request, policy,
PDF and final review in a fresh browser on the restored volume.

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

## Fresh-volume result

The accepted [fresh-volume preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40330569264)
at `7181939` passed all 13 initial MVP browser journeys, restored and matched
all 17 tables in a temporary database, restarted the original database and app,
and restored the same dump into a separate PostgreSQL volume. A fresh browser
reopened the saved request, policy, PDF and final review on both the restarted
original preview and the recovered preview. Each recovery browser check passed.
CI removed both disposable volumes afterward.

[Full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40331362155)
passed at `a64f8d1`: 916 root tests, 1,521 API tests, 72 membership checks,
35 catalog checks, 41 client checks, 26 browser checks, 15 source UI checks and
13 MVP browser checks, plus types, lint, contracts and build. The prior full
run at `7181939` caught a guard-test mistake under GitHub's CI environment;
`a64f8d1` corrected that test without changing the accepted recovery behavior.

## Local copy-integrity checkpoint — 27 October

The current local synthetic database was backed up, restored into a temporary
database and compared across all 17 tables. The resulting dump and manifest
passed the independent offline verifier, including a separate private copy.
The temporary database was removed;
the original app still returned HTTP 200. The verifier's focused tests reject
same-size dump corruption, missing hash metadata, public file permissions and
symlinks. This is a local package-integrity check, not an off-machine backup.
The code also passed the
[disposable private preview](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40511629064),
including the full MVP journey, backup/restore, restart and fresh-volume browser
recovery. [Full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40511628981)
passed its foundation and database-catalog jobs at `80fe291`.
