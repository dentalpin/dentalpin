# Backup & disaster recovery — DentalPin

> **Audience:** clinic operators and self-hosters (not DBAs). If you run
> DentalPin with real patient data, this page is mandatory reading.
> The one command that matters: `dentalpin db backup`.

DentalPin keeps **two kinds of data in two places**, and a backup that
covers only one of them will lose patient files:

| What | Where | Example |
|---|---|---|
| Relational data (patients, invoices, schedules, …) | PostgreSQL (`db` service) | everything you see in the UI lists |
| Files (documents, DICOM bytes, RVG imports, module dumps) | `storage_data` volume (`/app/storage` in backend) | PDFs, X-rays, `storage/backups/` |

Module uninstalls already auto-dump their own tables to
`storage/backups/` (see the operations manual §8) — that protects you
from a bad module removal, **not** from a dead disk.

## 1. Taking a backup

Inside the backend container (or via `docker compose exec backend`):

```bash
dentalpin db backup
# db backup: database -> /app/storage/backups/full_20260907T230000Z.dump
# db backup: storage -> /app/storage/backups/storage_20260907T230000Z.tar.gz
```

- `full_<ts>.dump` — whole-database `pg_dump --format=custom`.
- `storage_<ts>.tar.gz` — the storage volume **minus `backups/` itself**
  (no recursion).
- `--out-dir` overrides the destination; `--skip-storage` dumps the
  database only; `--keep N` retains the newest N of each kind
  (default 7, older ones pruned automatically).
- Exit non-zero when `pg_dump` is missing or fails — wire your cron
  alert to the exit code, not to the log.

Schedule it nightly (host cron hitting the container is enough):

```bash
0 2 * * * docker compose -f /srv/dentalpin/docker-compose.yml exec -T backend dentalpin db backup >> /var/log/dentalpin-backup.log 2>&1
```

## 2. Getting backups off the machine

A backup on the same disk as the clinic is not a backup. Copy the two
newest files off-host after every run (`rsync`, `rclone`, USB rotation —
any is fine). Encrypt before untrusted storage:

```bash
age -r <recipient> -o full_20260907T230000Z.dump.age full_20260907T230000Z.dump
```

Suggested rhythm: **RPO 24 h (nightly), RTO ~1 h** (restore below).
Keep 7 daily + 4 weekly off-host.

## 3. Restoring on a fresh host (hardware migration)

Prerequisites: Docker + this repo checked out at the same release tag,
`.env` re-created (**`.env` is never backed up** — copy
`DATABASE_URL`, `SECRET_KEY`, `*_DSN`/VAPID keys manually; without the
original `SECRET_KEY`, Fernet-encrypted fields — bank accounts, tax
ids, Verifactu certificates — are unrecoverable).

```bash
# 1. Start only the database, with an empty volume.
docker compose up -d db
# 2. Restore the dump (custom format needs pg_restore).
docker compose exec -T db pg_restore -U dental -d dental_clinic \
  -c < full_20260907T230000Z.dump
# 3. Restore files over the fresh storage volume.
docker compose exec -T backend tar -xz -C /app/storage < storage_20260907T230000Z.tar.gz
# 4. Boot the stack; entrypoint runs `db upgrade` (no-op on a current dump).
docker compose up -d
# 5. Sanity: log in, open a patient with documents, check an X-ray renders.
```

Never copy a raw `pgdata` directory between architectures or major
Postgres versions — dump + restore is the portable path.

## 4. After an unclean shutdown (power outage)

1. `docker compose up -d` and watch `docker compose logs backend`.
2. Postgres replays its WAL on start; if it refuses, restore last
   night's dump (step 3 above) rather than hand-editing data files.
3. Confirm Alembic state matches the tree:
   `docker compose exec backend python -m app.cli db upgrade`
   must print no targets (a no-op). If it wants to apply migrations,
   the dump predates the code — upgrade forward, never downgrade
   production data.
4. Spot-check storage vs DB: a recently uploaded document must open;
   if files are newer than the dump (uploaded after 02:00), re-upload
   from the source device.

## 5. Verify your backups (monthly)

An untested backup is a rumour. Monthly, on any spare machine:

1. Restore the newest pair per §3 into a throwaway compose project.
2. Log in, open 2–3 patients with documents, run one report.
3. Delete the throwaway. If any step fails, the backup pipeline is
   broken — fix it before you need it.

## 6. What is NOT covered

- Secrets (`.env`, VAPID/SMTP/API keys): re-create by hand, §3.
- Point-in-time recovery between nightlies: needs WAL archiving
  (out of scope for the built-in command; standard Postgres docs apply).
- Per-module dumps (`module_<name>_<ts>.sql`): for module reinstalls,
  schema must exist first (reinstall the module, then restore).
