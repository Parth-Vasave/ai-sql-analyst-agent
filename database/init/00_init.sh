#!/usr/bin/env bash
# Creates the schema and the read-only sql_agent role.
#
# In Docker this runs automatically on first start of the postgres container
# (docker-entrypoint-initdb.d), connecting over the local socket as POSTGRES_USER.
# Outside Docker, point it at any database with ADMIN_DATABASE_URL:
#
#   ADMIN_DATABASE_URL=postgresql://owner:pw@localhost:5432/mandi \
#   SQL_AGENT_PASSWORD=... ./database/init/00_init.sh
set -euo pipefail

: "${SQL_AGENT_PASSWORD:?SQL_AGENT_PASSWORD must be set}"
SQL_DIR="${SQL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TIMEOUT="${QUERY_TIMEOUT_SECONDS:-5}s"

if [[ -n "${ADMIN_DATABASE_URL:-}" ]]; then
  target=("$ADMIN_DATABASE_URL")
else
  target=(--username "${POSTGRES_USER:-postgres}" --dbname "${POSTGRES_DB:-postgres}")
fi

psql -v ON_ERROR_STOP=1 "${target[@]}" -f "$SQL_DIR/schema.sql"
psql -v ON_ERROR_STOP=1 "${target[@]}" \
  -v agent_password="$SQL_AGENT_PASSWORD" \
  -v statement_timeout="$TIMEOUT" \
  -f "$SQL_DIR/permissions.sql"

echo "Schema and sql_agent role are ready (statement_timeout=$TIMEOUT)."
