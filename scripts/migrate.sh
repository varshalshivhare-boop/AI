#!/usr/bin/env bash
# Applies SQL migrations in lexical order. Idempotent: each file is recorded in
# schema_migrations and skipped on re-run.
#
# Usage (from repo root, with the stack running):
#   ./scripts/migrate.sh                 # uses the timescaledb container
#   DB_CONTAINER=quantmind-timescaledb ./scripts/migrate.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MIGRATIONS_DIR="${ROOT}/migrations"
DB_CONTAINER="${DB_CONTAINER:-quantmind-timescaledb}"
DB_USER="${POSTGRES_USER:-quantmind}"
DB_NAME="${POSTGRES_DB:-quantmind}"

psql_cmd() {
  docker exec -i "${DB_CONTAINER}" psql -v ON_ERROR_STOP=1 -X -q -U "${DB_USER}" -d "${DB_NAME}" "$@"
}

psql_cmd <<'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    checksum    TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
SQL

applied=0
skipped=0
for file in "${MIGRATIONS_DIR}"/*.sql; do
  version="$(basename "${file}" .sql)"
  checksum="$(sha256sum "${file}" | cut -d' ' -f1)"

  existing="$(psql_cmd -tA -c "SELECT checksum FROM schema_migrations WHERE version = '${version}';")"

  if [[ -n "${existing}" ]]; then
    if [[ "${existing}" != "${checksum}" ]]; then
      echo "ERROR: ${version} was modified after being applied (checksum mismatch). Write a new migration instead." >&2
      exit 1
    fi
    echo "skip   ${version} (already applied)"
    skipped=$((skipped + 1))
    continue
  fi

  echo "apply  ${version}"
  psql_cmd -f - < "${file}"
  psql_cmd -c "INSERT INTO schema_migrations (version, checksum) VALUES ('${version}', '${checksum}');"
  applied=$((applied + 1))
done

echo "done: ${applied} applied, ${skipped} skipped"
