#!/bin/sh
# Keep the anonymous /app/node_modules volume in sync with the lockfile.
# The volume is seeded once from the image; without this check, an image
# rebuild that adds dependencies (e.g. a font package) leaves the running
# container on the stale set, and Vite SSR dies tracelessly (IPC closed,
# HTTP 500 on every route) on the first unresolvable import. Comparing
# the lockfile hash is cheap; `npm ci` runs only on real drift.
set -e
STAMP=/app/node_modules/.package-lock.sha256
CURRENT=$(sha256sum /app/package-lock.json | cut -d' ' -f1)
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$CURRENT" ]; then
  echo "node-modules-sync: lockfile moved, re-syncing node_modules..."
  npm ci --no-audit --no-fund
  echo "$CURRENT" > "$STAMP"
fi
exec "$@"
