# Operating a DentalPin instance

Guide for admins and self-hosters: install and remove modules, trigger
restarts, take backups, recover from errors. Covers the commands an
operator runs — not the Python internals.

> **Audience**: ops-aware user with shell access to the host running
> `docker compose up`. For contributor-facing docs see
> `docs/technical/creating-modules.md`.

---

## 1. Prerequisites

- Docker + Docker Compose on the host.
- Cloned DentalPin repo (or equivalent deploy artefacts).
- `.env` filled in with `POSTGRES_PASSWORD`, `SECRET_KEY`, etc.
- A running stack: `docker compose up -d`.

Smoke-check:

```bash
curl -s http://localhost:8000/health
# {"status":"healthy","version":"0.1.0"}
```

---

## 2. Daily operations

### Listing modules

```bash
./bin/dentalpin modules list
```

Output (trimmed):

```
NAME            VERSION  STATE       CATEGORY  DEPENDS
billing         0.1.0    installed   official  clinical,catalog,budget
budget          0.1.0    installed   official  clinical,catalog
clinical        0.1.0    installed   official  -
```

JSON variant: `./bin/dentalpin modules list --json`.

### Inspecting one module

```bash
./bin/dentalpin modules info billing
```

Shows version, state, applied revision, last state change, errors.
JSON form: same command with `--json`.

### Status summary

```bash
./bin/dentalpin modules status
```

Counts by state plus pending + errored lists.

### Health check

```bash
./bin/dentalpin modules doctor
```

Surfaces:

- **Orphans** — rows in `core_module` whose code disappeared from disk.
- **Missing dependencies** — module X depends on Y that wasn't found.
- **Manifest errors** — schema violations in `MANIFEST`.
- **Errored modules** — rows where the last install/upgrade step failed.

Exit code is non-zero when any issue is reported; ideal for
monitoring scripts.

---

## 3. Installing a module

### Official modules

Bundled with every DentalPin release. They auto-install on the first
boot of a fresh database. Reinstall if they ended up in `uninstalled`:

```bash
./bin/dentalpin modules install billing
./bin/dentalpin modules restart
```

### Community modules

```bash
# 1. Install the Python package on the backend container
docker compose exec backend pip install dentalpin-my-module

# 2. Schedule the install
./bin/dentalpin modules install my_module

# 3. Restart the backend — applies migrations + seed + lifecycle
docker compose restart backend
# or: POST /api/v1/modules/-/restart

# 4. Rebuild the frontend if the module ships a Nuxt layer
docker compose build frontend && docker compose up -d frontend
```

Output of step 2 lists the dependency chain that will be touched:

```
Scheduled for install on next restart:
  - clinical
  - my_module
```

---

## 4. Upgrading a module

Bump the module's package (`pip install -U ...`) so the new version
appears on disk, then:

```bash
./bin/dentalpin modules upgrade my_module
./bin/dentalpin modules restart
```

The restart runs the new migrations, re-applies seeds, and calls the
module's `post_upgrade(ctx, from_version)` hook.

If the disk and DB versions already match, the command exits with
"Module is already at the declared version."

---

## 5. Uninstalling a module

```bash
./bin/dentalpin modules uninstall my_module
docker compose restart backend
```

The restart:

1. **Backs up** every table the module owns to
   `storage/backups/module_<name>_<timestamp>.sql` via `pg_dump --data-only`.
2. Calls the module's `uninstall(ctx)` hook.
3. Deletes every record tracked via `core_external_id`.
4. Runs `alembic downgrade <module>@base` — reverts the module's
   branch only.
5. Flips `core_module.state = uninstalled`.

### Why some modules refuse to uninstall

Two guardrails:

- `removable: false` in the manifest (officials). Override with
  `--force` if you really mean it.
- No Alembic branch (Fase A legacy modules). These cannot downgrade
  cleanly; uninstall is blocked even with `--force`. Wait for Fase B.
- Reverse dependencies — another installed module lists this one in
  its `depends`. Uninstall them first, or pass `--force`.

---

## 6. Restarts

Three ways, identical effect (SIGTERM the backend, let Docker respawn):

| Channel | Command |
|---------|---------|
| CLI hint | `./bin/dentalpin modules restart` prints next step |
| REST | `POST /api/v1/modules/-/restart` (admin token) |
| Host | `docker compose restart backend` |

Respawn takes 3-5 seconds. Lifespan processes every `to_*` row in
topological order before accepting traffic. Errors per module are
recorded in `core_module.error_message`; the rest of the stack still
comes up.

---

## 7. Frontend rebuilds

Community modules with a Nuxt layer require a frontend rebuild:

```bash
docker compose build frontend && docker compose up -d frontend
```

30-60s downtime on the UI. Official modules **don't** need a rebuild
— they're already in the bundle; toggling visibility is a filter on
`/api/v1/modules/-/active`.

If the frontend starts but a module doesn't appear:

1. Inspect `frontend/modules.json` — it should list the module's layer
   path.
2. Run `./bin/dentalpin modules sync-frontend` to regenerate the file.
3. Confirm the user has the permission listed in `navigation[].permission`.

---

## 8. Backups

Module-scoped backups live under `storage/backups/` inside the
backend's `storage_data` volume:

```bash
docker compose exec backend ls -l /app/storage/backups
```

Each uninstall produces one `.sql` file with INSERTs for every table
the module owned. Restore with:

```bash
docker compose exec -T db psql -U dental -d dental_clinic \
  < storage/backups/module_my_module_20260420T080000Z.sql
```

The schema must already exist (reinstall the module first, then
restore data).

### Full backup (database + files)

```bash
docker compose exec -T backend python -m app.cli db backup
```

Produces `full_<timestamp>.dump` (whole database) and
`storage_<timestamp>.tar.gz` (documents, X-rays, imports) under
`storage/backups/`. Schedule this nightly and copy the files off the
server: a backup on the same disk is not a backup. Full restore,
hardware-migration, and monthly-verification procedure:
`docs/workflows/backup-restore.md`.

---

## 9. Recovery

### A failed install

`dentalpin modules doctor` lists the module with its error. Options:

1. Fix the root cause (usually a migration or seed bug), then
   `dentalpin modules install <name>` + restart to retry.
2. Give up: `dentalpin modules orphan <name>` (marks uninstalled
   without running the uninstall flow). Only do this when the module
   wasn't actually present on disk.

### A stuck `to_install`

Happens when a crash takes down the backend mid-step. Restart — the
lifespan processor retries from the first incomplete step. Idempotent
design means migrate/seed/lifecycle are safe to re-run.

```bash
docker compose exec backend \
  psql -U dental -d dental_clinic \
  -c "SELECT * FROM core_module_operation_log ORDER BY id DESC LIMIT 20;"
```

### An orphan row

Module code was removed from disk without an uninstall (e.g. someone
uninstalled the Python package directly). Bootstrap will fail loud:

```
Orphan modules (in DB, missing from disk):
  - ghost
```

Options:

- Restore the package (`pip install dentalpin-ghost`).
- Mark uninstalled:

  ```bash
  ./bin/dentalpin modules orphan ghost
  ```

The orphan path **does not** run the uninstall steps (migrations are
not downgraded, external ids are not purged, no backup is taken). Use
with care.

### Permission denied after role change

Clear the user's auth cookies and re-login. Permissions are loaded
from `/me` at login time; stale sessions keep the old list.

---

## 10. SQL quick reference

Run inside `docker compose exec db psql -U dental -d dental_clinic`:

```sql
-- All modules + state + error
SELECT name, state, version, installed_at, error_message
FROM core_module
ORDER BY name;

-- Pending operations
SELECT name, state, last_state_change
FROM core_module
WHERE state LIKE 'to_%';

-- Recent operation log
SELECT module_name, operation, step, status, created_at
FROM core_module_operation_log
ORDER BY id DESC
LIMIT 25;

-- Seed records tracked for a module
SELECT xml_id, table_name, record_id, noupdate
FROM core_external_id
WHERE module_name = 'inventory';

-- Clear the Alembic pointer (dangerous — used by reset-db.sh)
DELETE FROM alembic_version;
```

---

## 11. Troubleshooting table

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `relation "core_module" does not exist` | Tests dropped all tables | `docker compose exec backend alembic upgrade head` |
| Module stuck in `to_install` | Crash mid-step | Inspect `core_module_operation_log`, restart backend |
| `403 Permission denied: billing.read` | Role lacks the permission | Check `ROLE_PERMISSIONS`, confirm cached `/me` |
| Frontend sidebar empty | `/api/v1/modules/-/active` failed (bad token?) | Check browser console, re-login |
| Community module page 404 | `modules.json` missing the layer path | `./bin/dentalpin modules sync-frontend` + frontend rebuild |
| Uninstall blocked: "no Alembic branch" | Fase A legacy module | Not supported; wait for Fase B |
| Uninstall blocked: "required by ..." | Reverse dependency exists | Uninstall dependents first, or `--force` |

---

## 12. Where to file bugs

GitHub: https://github.com/dentalpin/dentalpin/issues — include the
output of:

```bash
./bin/dentalpin modules doctor --json
./bin/dentalpin modules info <affected-module> --json
docker compose logs backend --tail 100
```

For security reports contact the maintainers privately rather than
opening a public issue.
