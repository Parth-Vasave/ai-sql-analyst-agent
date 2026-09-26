#!/bin/bash
# SessionStart hook for Claude Code on the web: makes the test suites and linter runnable.
#
# 1. Installs the Python dependencies of the backend and the data pipeline.
# 2. Starts the local PostgreSQL cluster (it is down after every container restart).
# 3. Creates a disposable test database and an owner role for the integration tests, with
#    fresh random passwords each session (no credentials are stored in the repository), and
#    exports TEST_ADMIN_DATABASE_URL / TEST_SQL_AGENT_PASSWORD for the session.
#
# Idempotent. Database problems only print a warning: the DB-backed tests are then skipped,
# as they are anywhere these variables are not set.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}"

python3 -m pip install --quiet --disable-pip-version-check --root-user-action=ignore \
  -r backend/requirements-dev.txt -r scripts/requirements.txt

setup_test_database() {
  command -v pg_lsclusters >/dev/null || { echo "PostgreSQL is not installed"; return 1; }
  local version cluster
  read -r version cluster < <(pg_lsclusters --no-header | awk 'NR == 1 {print $1, $2}')
  [ -n "${version:-}" ] || { echo "no PostgreSQL cluster found"; return 1; }
  if ! pg_lsclusters --no-header | awk 'NR == 1 {print $4}' | grep -q online; then
    pg_ctlcluster "$version" "$cluster" start || return 1
  fi

  local owner_password agent_password
  owner_password="$(python3 -c 'import secrets; print(secrets.token_hex(16))')" || return 1
  agent_password="$(python3 -c 'import secrets; print(secrets.token_hex(16))')" || return 1

  runuser -u postgres -- psql -q -v ON_ERROR_STOP=1 -v pw="$owner_password" <<'SQL' || return 1
SELECT 'CREATE ROLE emissions_owner LOGIN CREATEROLE'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'emissions_owner') \gexec
ALTER ROLE emissions_owner WITH LOGIN CREATEROLE PASSWORD :'pw';
SELECT 'CREATE DATABASE emissions_test OWNER emissions_owner'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'emissions_test') \gexec
SQL

  local admin_url="postgresql://emissions_owner:${owner_password}@localhost:5432/emissions_test"
  if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
    {
      echo "export TEST_ADMIN_DATABASE_URL='${admin_url}'"
      echo "export TEST_SQL_AGENT_PASSWORD='${agent_password}'"
    } >> "$CLAUDE_ENV_FILE"
  fi
  echo "PostgreSQL ${version}/${cluster} is running; test database emissions_test is ready."
}

if ! setup_test_database; then
  echo "WARNING: test database setup failed; database-backed tests will be skipped." >&2
fi
