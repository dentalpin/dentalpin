#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  # One-time heal for the Fase C schedules-branch rewire (issue #56):
  # DBs bootstrapped while schedules lived on the main linear chain have
  # the schedules tables but no row in alembic_version for the new
  # branch. Stamp sch_0001 so the boot upgrade is a no-op instead
  # of re-creating tables that already exist.
  PG_URL="$(python -c 'from app.config import settings; print(settings.DATABASE_URL.replace("postgresql+asyncpg://","postgresql://"))')"
  psql "$PG_URL" -v ON_ERROR_STOP=1 <<'SQL' || true
DO $$
BEGIN
  IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'clinic_weekly_schedules'
     )
     AND NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num = 'sch_0001')
  THEN
    INSERT INTO alembic_version(version_num) VALUES ('sch_0001');
    RAISE NOTICE 'Stamped sch_0001 for pre-branch schedules tables';
  END IF;
END
$$;
SQL

  # Core heads + the branches of installed modules only (ADR 0020): an
  # uninstalled module's tables must not come back on restart (#91).
  echo "[entrypoint] Running dentalpin db upgrade..."
  python -m app.cli db upgrade
fi

if [ "${SEED_ON_STARTUP:-0}" = "1" ]; then
  (
    SEED_LANG_ARG="${SEED_LANG:-es}"
    for i in $(seq 1 60); do
      if python -c "import urllib.request,sys
try:
    sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=1).status == 200 else 1)
except Exception:
    sys.exit(1)" 2>/dev/null; then
        echo "[entrypoint] Backend healthy — running seed (lang=$SEED_LANG_ARG)"
        PYTHONPATH=/app python /app/scripts/seed_demo.py --lang "$SEED_LANG_ARG" || echo "[entrypoint] Seed failed (non-fatal)"
        exit 0
      fi
      sleep 1
    done
    echo "[entrypoint] Backend never became healthy — seed skipped"
  ) &
fi

exec "$@"
