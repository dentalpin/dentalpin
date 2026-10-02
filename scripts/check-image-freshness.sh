#!/bin/bash
# Compare the Node major pinned in the frontend Dockerfiles against the
# node-version matrix in .github/workflows/CI, and (best-effort) against
# a locally built frontend image. Prevents a repeat of the 30-hour
# Node-20 incident: the Dockerfiles say 22 while a stale local image
# still reports 20.
# Usage: ./scripts/check-image-freshness.sh [--image <name>]
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=""
if [[ "${1:-}" == "--image" ]]; then
  IMAGE="${2:-}"
fi

fail() { echo "image-freshness: $1" >&2; exit 1; }

CI_MAJORS=$(grep -oE 'node-version: "[0-9]+"' .github/workflows/ci.yml | grep -oE '[0-9]+' | sort -u | tr '\n' ' ')
[[ -n "$CI_MAJORS" ]] || fail "no node-version found in CI"
echo "CI node majors: $CI_MAJORS"

DOCKER_MAJORS=""
for f in frontend/Dockerfile frontend/Dockerfile.prod; do
  [[ -f "$f" ]] || continue
  major=$(grep -oE 'FROM node:[0-9]+' "$f" | grep -oE '[0-9]+' | head -1)
  [[ -n "$major" ]] || fail "no node pin in $f"
  echo "$f pins node major: $major"
  DOCKER_MAJORS="$DOCKER_MAJORS $major"
  echo "$CI_MAJORS" | grep -qw "$major" || fail "$f pins node $major, not in CI matrix ($CI_MAJORS)"
done

if [[ -n "$IMAGE" ]]; then
  if ! reported=$(docker run --rm "$IMAGE" node --version 2>/dev/null); then
    echo "image $IMAGE not present locally, skipping runtime check"
  else
    runtime_major=$(echo "$reported" | grep -oE '^v[0-9]+' | grep -oE '[0-9]+')
    echo "$IMAGE reports $reported"
    echo "$CI_MAJORS" | grep -qw "$runtime_major" \
      || fail "$IMAGE runs node major $runtime_major, not in CI matrix ($CI_MAJORS)"
  fi
fi

echo "image-freshness: OK"
