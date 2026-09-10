#!/bin/bash
# Seed DentalPin with demo data
# Usage: ./scripts/seed-demo.sh [--lang en|es]
#
# Examples:
#   ./scripts/seed-demo.sh              # English (default)
#   ./scripts/seed-demo.sh --lang es    # Spanish
#   ./scripts/seed-demo.sh -l es        # Spanish (short form)

set -e

export MSYS_NO_PATHCONV=1
echo "Seeding demo data..."
docker compose exec -T -e PYTHONPATH=/app backend python scripts/seed_demo.py "$@"
