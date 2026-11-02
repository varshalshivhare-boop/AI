#!/usr/bin/env bash
# Phase 0 acceptance checks. Run from the repository root.
#   ./scripts/verify.sh              # schemas + fixtures + migration (if a database is reachable)
#   SKIP_DB=1 ./scripts/verify.sh    # schemas + fixtures only
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

step() { printf '\n== %s ==\n' "$1"; }

step "1. JSON Schema meta-validation, examples, negative cases"
python3 scripts/validate_schemas.py

step "2. Fixture integrity"
(cd fixtures && sha256sum -c SHA256SUMS)

step "3. Fixture regeneration is byte-identical"
python3 scripts/generate_fixtures.py >/dev/null
(cd fixtures && sha256sum -c SHA256SUMS)

if [[ "${SKIP_DB:-0}" == "1" ]]; then
  step "4. Migration: SKIPPED (SKIP_DB=1)"
else
  step "4. Migration applies and re-run is a no-op"
  ./scripts/migrate.sh
  ./scripts/migrate.sh
fi

printf '\nPhase 0 checks passed.\n'
