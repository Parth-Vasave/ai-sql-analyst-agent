# Deployment: Neon + Vercel + a container host

> **Public deployment is not a single click.** This guide walks you through a complete, low-cost,
> publicly reachable stack. Every step was verified against the actual repository: the backend
> Dockerfile, the FastAPI startup configuration, the seed scripts, the API routes, and the
> database permission file that is the security boundary. If a command below shows a password,
> placeholder, or variable, replace it with your own value — never commit it.

The architecture is:

```text
Vercel
  ↓  HTTPS, browser cookies for auth (frontend)
React frontend (Vite + TypeScript)
  ↓  CORS, X-Request-ID
Vercel Serverless Function / proxy (backend URL)
  ↓
FastAPI backend on a small container host (Railway)
  ↓
Neon PostgreSQL
  ↓
read-only `sql_agent` role
```

| Layer | Provider | Why |
|---|---|---|
| Frontend | Vercel | Native React/Vite integration, automatic builds from `frontend/`, HTTPS, edge proxy |
| Backend | Railway | Free tier, one-click GitHub deploy, custom PaaS, logs with request IDs |
| Database | Neon | Serverless PostgreSQL with branching, connection pooling, and per-role credentials |
| Database role | `sql_agent` (read-only) | Described by `database/permissions.sql`; the API never connects as the owner |

Both `frontend/` and `backend/` are deployed from GitHub. The guide uses **Railway** as the single
concrete container host for the walkthrough, with Render and Fly.io listed as alternatives at the end.
Pick whichever you already have an account with; the differences are a few form fields and a port.

---

## Table of contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [1. Create the Neon PostgreSQL database](#1-create-the-neon-postgresql-database)
4. [2. Create the read-only `sql_agent` role](#2-create-the-read-only-sql_agent-role)
5. [3. Seed the database with the project's data](#3-seed-the-database-with-the-projects-data)
6. [4. Deploy the FastAPI backend to Railway](#4-deploy-the-fastapi-backend-to-railway)
7. [5. Configure backend environment variables](#5-configure-backend-environment-variables)
8. [6. Deploy the frontend to Vercel](#6-deploy-the-frontend-to-vercel)
9. [7. Configure CORS](#7-configure-cors)
10. [8. Rate limiting and LLM budget](#8-rate-limiting-and-llm-budget)
11. [9. Security checklist](#9-security-checklist)
12. [10. Post-deployment verification](#10-post-deployment-verification)
13. [Multi-instance limitation](#multi-instance-limitation)
14. [Troubleshooting](#troubleshooting)
15. [Known limitations](#known-limitations)
16. [Alternatives](#alternatives)

---

## Architecture

```text
                    ┌──────────────┐
                    │   Vercel     │  HTTPS + CDN
                    │  (frontend)  │
                    └──────┬───────┘
                           │ https://<app>.vercel.app/api/query
                    ┌──────▼───────┐
                    │ Railway app  │  FastAPI 0.0.0.0:8000
                    │  (backend)   │
                    └──────┬───────┘
                           │ postgresql://sql_agent:…@ep-…-eu-central-1.neon.tech/emissions
                    ┌──────▼───────┐
                    │   Neon       │  PostgreSQL 16
                    │  database    │
                    └──────────────┘
```

The frontend never talks to Neon directly. The only database connection the frontend relies on is
the one the backend owns, and the backend uses the read-only `sql_agent` account.

---

## Prerequisites

1. A **Neon** account (<https://neon.tech>) and a project. Neon gives you a connection string you
   will paste into the backend host.
2. A **Railway** account (<https://railway.app>) and the [Railway CLI](https://docs.railway.app/guides/command-line),
   or just use the web dashboard. This guide uses the dashboard for the first deploy and the CLI for
   environment variable setup.
3. A **Vercel** account (<https://vercel.com>) and the [Vercel CLI](https://vercel.com/docs/cli),
   or the web dashboard.
4. An **LLM API key** from any OpenAI-compatible provider. The defaults in `.env.example` are the
   [Gemini free tier](https://aistudio.google.com/apikey) and the Groq free tier. This guide uses
   **Gemini** as an example; swap in Groq by changing `LLM_BASE_URL` and `LLM_MODEL`.
5. A GitHub repository with the project committed and pushed (this one: `Parth-Vasave/ai-sql-analyst-agent`).
   The repo is **private** in the sense that it contains no secrets; `.env` is already git-ignored.
   If you host your own copy, push to GitHub first.

All passwords in this guide are placeholders. Set them in your deployment UI or CLI. Never paste a
password into a chat, a screenshot, or a commit.

---

## 1. Create the Neon PostgreSQL database

1. Sign in to Neon and click **Projects → New Project**.
2. Name it, for example `ai-sql-analyst`, and choose the **General Purpose** (or Essential) plan.
   These are cheap (often free) serverless tiers.
3. Neon automatically creates a **database** (default name is the project name) and a
   **database owner** role. Neon also creates a `sql_agent`-less schema `public`.
4. Note two values from the Neon dashboard:

   - **Connection string** — of the form
     `postgresql://<user>:<password>@ep-<hash>-<region>.neon.tech/<db>?sslmode=require`
     The password is generated by Neon. Keep it somewhere safe; you will not see it again in plain
     text after you leave the page.
   - **Project ID** (the `ep-…` host name) — used in the backend environment variable.

   Neon's serverless connection strings are long and contain a password. Copy the string and **do
   not** put it in Vercel or in `README.md`. It belongs only on the backend/container host, as
   `DATABASE_URL`.

5. Neon creates the database with a **database owner** role. Neon's UI does not show you the owner's
   password after creation, but for the **schema setup** step you need a superuser-style account.
   Neon projects give you `owner` as the role name; you use it through the SQL Console's `psql`
   session, or through the `NEON_IP` connection string's user.
   The important thing: the schema setup step **only runs once**, when the database is empty.
   For Neon you have two realistic options:

   **Option A (recommended): run the schema setup from your own machine against Neon.**
   Neon exposes an `owner` user through its connection strings and through the
   [neon CLI](https://neo.neon.tech/cli). Install the CLI (`npm i -g @neonctl/cli`), create a
   config with `neon switch-project <project-id>`, then run:

   ```bash
   # Grab the project's connection string from the Neon dashboard:
   #   postgresql://<user>:<password>@<host>/<db>?sslmode=verify-full
   export ADMIN_DATABASE_URL="postgresql://owner:<password>@ep-<hash>-<region>.neon.tech/<db>?sslmode=verify-full"
   export SQL_AGENT_PASSWORD="change-me-too"   # your own read-only role password
   export QUERY_TIMEOUT_SECONDS=5

   # Download schema + permissions into your checkout:
   git clone https://github.com/Parth-Vasave/ai-sql-analyst-agent.git
   cd ai-sql-analyst-agent

   # Run the existing init script. It creates schema.sql and permissions.sql
   # against the Neon database exactly as docker-compose does for local Postgres:
   scripts/database/init/00_init.sh
   ```

   The script runs `database/init/00_init.sh`, which executes `database/schema.sql` and
   `database/permissions.sql` in order. It is the same file that `docker-compose.yml` mounts into
   the Postgres container as `/docker-entrypoint-initdb.d/00_init.sh`. For Neon you run it
   **once** against the live database, not inside a disposable container, because a Neon database is
   persistent.

   **Option B: use Neon's SQL Console.**
   Open the project in Neon, open the **SQL Console**, run
   `\i /path/to/ai-sql-analyst-agent/database/init/00_init.sh`
   (or paste the contents of `database/schema.sql`), then run
   `psql -v ON_ERROR_STOP=1 -f database/permissions.sql`.
   Neon's console does not create the `sql_agent` role, so you still need to run
   `database/permissions.sql` — which is exactly what the init script does.

   Option A is simpler because you reuse the repository's own script and keep the two SQL files
   (`schema.sql`, `permissions.sql`) as a single source of truth.

6. Open the Neon SQL Console (or connect with `psql`) and run:

   ```sql
   -- The schema: tables and indexes. Run once, idempotently.
   \i database/schema.sql

   -- The read-only role. Run as the database owner.
   \i database/permissions.sql
   ```

   `database/permissions.sql` is idempotent and safe to re-run (for example to rotate the
   `sql_agent` password). It creates the role, sets `default_transaction_read_only = on`,
   `statement_timeout`, `idle_in_transaction_session_timeout`, and gives `SELECT` only on the four
   tables (`countries`, `country_indicators`, `co2_emissions`, `ghg_emissions`).

   The file's header comment says exactly what to do:

   ```sql
   --   psql -v agent_password=... -v statement_timeout=5s -f database/permissions.sql
   ```

   **Important.** The API **must** connect as `sql_agent`. Never use the database owner account as
   the `DATABASE_URL` the backend ships with. `backend/app/database/adapters/postgres.py` itself
   refuses a writable account at connection time: `check_privileges()` reports any `INSERT/UPDATE/
   DELETE/TRUNCATE` privilege as blocking, and `main.py` builds the registry from
   `DATABASE_URL` before the first request. A writable account can also be a superuser, which is
   even more blocking. If you accidentally set `DATABASE_URL` to the owner, the backend logs
   `connection rejected: account is not read-only` (well, `ConnectionStatus.REJECTED`) and every
   query fails with `409 Database is rejected`.

7. **Verify the role.** In the Neon SQL Console, or from `psql` on your machine:

   ```sql
   SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls
   FROM pg_roles WHERE rolname = 'sql_agent';

   SELECT has_table_privilege('sql_agent', 'countries', 'SELECT') AS can_read_countries,
          has_table_privilege('sql_agent', 'countries', 'INSERT') AS can_write_countries;
   ```

   The first row should be `(f, f, f, f, f)` — no superuser, no creation, no bypass, no
   inheritance. `can_read_countries` should be `t`, `can_write_countries` should be `f`.

8. **Verify the role cannot modify the database.** In the Neon SQL Console, or from `psql`:

   ```sql
   SET default_transaction_read_only = off;
   CREATE TABLE sql_agent.evil (id int);
   ```

   Postgres raises `ERROR: permission denied for schema public` (SQLSTATE 42501) because
   `REVOKE CREATE ON SCHEMA public FROM PUBLIC` removed the creation right from everyone except
   the owner. TRY it now — this is the strongest proof you have of the read-only boundary.

---

## 2. Create the read-only `sql_agent` role

The role is created and configured by `database/permissions.sql`. The file is the source of truth
for the read-only boundary and uses `ON_ERROR_STOP on`, so every statement must succeed or the file
aborts.

The file does the following:

1. Creates the role `sql_agent` if it does not exist.
2. Sets `LOGIN NOINHERIT CONNECTION LIMIT 20`.
3. Sets the cluster-wide role attributes `default_transaction_read_only = on` and
   `statement_timeout = 5s` (you control the numeric value through `QUERY_TIMEOUT_SECONDS`).
   These defaults are not the primary guard; the missing privileges are. The file says so
   explicitly. A session can override `default_transaction_read_only` with `SET`, so the
   database-level `GRANT SELECT` is the layer that actually stops writes.
4. Revokes `CREATE` on `public` from `PUBLIC`, then grants `USAGE` only.
5. Revokes all privileges on all tables and sequences in `public`, then grants `SELECT` on the
   four tables: `countries`, `country_indicators`, `co2_emissions`, `ghg_emissions`.

The role is created **by the database owner**, never by the read-only account, and never by the
frontend. The `DATABASE_URL` the backend uses is:

```text
postgresql://sql_agent:<SQL_AGENT_PASSWORD>@<neon-host>.neon.tech/<db>?sslmode=require
```

where `<SQL_AGENT_PASSWORD>` is the password you choose in step 1 of this section (or a Neon
generated one). `database/permissions.sql` sets that password with `-v agent_password=...`.

---

## 3. Seed the database with the project's data

The repository has **two** data pipelines:

| Script | What it does | Connection | Running it |
|---|---|---|---|
| `scripts/ingest_data.py` | Downloads the OWID CO₂ dataset from a **pinned commit** (`382ee6c`) and verifies SHA-256 | — | `python -m scripts.ingest_data` |
| `scripts/clean_data.py` | Cleans the CSV (drops `(GCP)` regions, classifies entities, applies non-negative checks) | — | `python -m scripts.clean_data` |
| `scripts/seed_database.py` | Loads the cleaned CSVs into PostgreSQL **as the OWNER** via `ADMIN_DATABASE_URL` | `ADMIN_DATABASE_URL` (owner) | `python -m scripts.seed_database` |

The existing seed workflow is:

```bash
docker compose run --rm seed
```

That command builds the one-off image `scripts/Dockerfile`, runs `ingest → clean → seed` inside a
container, and connects to the **local Docker Compose PostgreSQL** using `ADMIN_DATABASE_URL`
(pointing at `postgres://emissions_owner:…@postgres:5432/emissions`). It uses the owner account,
**never** `sql_agent`.

For a remote Neon database the same pipeline applies, with one change: you cannot run the seed
inside a container that targets `localhost`, because Neon is network-accessible. You run the three
scripts directly on your machine (or in a job on the container host), pointing at Neon:

```bash
# 1. Ingest (pinned commit, SHA-256 verified)
python -m scripts.ingest_data

# 2. Clean
python -m scripts.clean_data --output-dir data/processed

# 3. Seed into Neon as the owner (ADMIN_DATABASE_URL, never sql_agent)
export ADMIN_DATABASE_URL="postgresql://owner:<owner-password>@ep-<hash>-<region>.neon.tech/<db>?sslmode=verify-full"
export SQL_AGENT_PASSWORD="change-me-too"
python -m scripts.seed_database
```

Daemonize or use a script to ensure each step waits for the previous one, then check the output:

```text
Rows added: countries 210, country_indicators 3,758, co2_emissions 8,672, ghg_emissions 4,104
```

(Exact numbers vary with the OWID dataset at the pinned commit; the `clean_data` report prints
`rows_written` per table.)

The `scripts/Dockerfile` exists for local reproducibility and for CI. For Neon you do **not** use
it — the seed scripts read from `data/processed` which is a gitignored directory, and the Docker
image maps `./data:/work/data` as a volume. Instead, run the three scripts on your machine or in a
CI job. If you want the seed step inside a container on the container host, you mount `data/`
and run `python -m scripts.seed_database` with `ADMIN_DATABASE_URL` pointing at Neon.

The seed is **idempotent**: rows that exist are skipped (`ON CONFLICT (country_id, year) DO NOTHING`).
Use `--replace` to reload:

```bash
python -m scripts.seed_database --replace
```

This truncates `countries`, `country_indicators`, `co2_emissions`, `ghg_emissions` and restarts
identity columns.

### If you want to seed from inside the container host

Railway/ Render do not run `docker compose` for you. You have three realistic choices:

1. **Run the scripts locally** as above (simplest; your machine has Python + pandas + psycopg).
2. **Run a one-off container** on the host:

   ```bash
   docker run --rm \
     -e ADMIN_DATABASE_URL="postgresql://owner:…@ep-…-eu-central-1.neon.tech/emissions" \
     -v "$(pwd)/data:/work/data" \
     -w /work \
     python:3.12-slim \
     sh -c "pip install pandas psycopg[binary] && python -m scripts.seed_database"
   ```

   This is what `scripts/Dockerfile` builds, plus psycopg.
3. **A Railway job / CI workflow** using the same environment. The CI in `.github/workflows/ci.yml`
   already runs the data pipeline and the read-only role tests; you can fork it for Neon.

Do **not** seed with `sql_agent`: the role has no `INSERT` privilege, the seed script raises
`psycopg.errors.InsufficientPrivilege` immediately.

### If you want to verify the read-only boundary after seeding

The repository's own integration test proves it. `scripts/tests/test_database.py` runs against a
disposable database and asserts:

- `sql_agent` has none of `rolsuper`, `rolcreatedb`, `rolcreaterole`, `rolreplication`,
  `rolbypassrls`, `rolinherit`;
- `default_transaction_read_only` is `on` and `statement_timeout` is the configured value;
- 10 forbidden statements (`INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `DROP`, `ALTER`, `CREATE
  TABLE`, `CREATE TEMP TABLE`, `CREATE INDEX`, `CREATE ROLE`) all raise
  `InsufficientPrivilege` / `ReadOnlySqlTransaction`, even after `SET default_transaction_read_only
  = off`;
- `GRANT INSERT ON countries TO PUBLIC` is a no-op;
- `SELECT pg_sleep(3)` is cancelled by the statement timeout.

On Neon you can perform the same checks with `psql` as `sql_agent`:

```bash
psql "$ADMIN_DATABASE_URL" -c "SET default_transaction_read_only = off; CREATE TABLE evil (id int);"
```

The second command must be rejected. Those are the same checks the tests run.

---

## 4. Deploy the FastAPI backend to Railway

The backend is a FastAPI app. `backend/Dockerfile` builds a slim Python 3.12 image, runs as
`appuser`, exposes port `8000`, and starts with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

The app listens on `0.0.0.0:8000` **and only** `8000`. Railway runs the container as-is and does
not pass a `PORT` env var to the app; the container hard-codes `8000`. The start command for
Railway is therefore the Docker CMD above — no extra flags, no `waitress` or `gunicorn`
incantation. The Dockerfile already sets `EXPOSE 8000` and a `HEALTHCHECK` that curls
`http://127.0.0.1:8000/api/health` (503 until the database is reachable).

Railway uses your **GitHub repository** (`Parth-Vasave/ai-sql-analyst-agent`), builds with the
Dockerfile in `backend/` (Railway detects `backend/Dockerfile`), and starts with the command:

```text
uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

### 4.1 Create the service

1. In Railway, click **New Project → Deploy from GitHub repo** and select
   `Parth-Vasave/ai-sql-analyst-agent`.
2. Railway auto-detects `backend/Dockerfile` as a Dockerfile service. Confirm the build context
   is `./backend`. If Railway instead offers a build-from-source service, set:

   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log`

   For a Dockerfile service Railway uses the `CMD` in the image; you still want `--no-access-log`
   (the app deliberately logs request IDs itself, without client IPs, in
   `app/observability.py` — access logs would leak client addresses).

3. Give the service a name, e.g. `ai-sql-analyst-api`, and deploy. Railway provisions a random
   domain, e.g. `https://ai-sql-analyst-api-production.up.railway.app`.

### 4.2 Add environment variables

In Railway, go to the **Variables** tab of the service and add each variable from the table in
section 5, **matching the exact keys** in `.env.example` / `backend/app/config.py`:

| Variable | Value | Where to set |
|---|---|---|
| `DATABASE_URL` | `postgresql://sql_agent:<SQL_AGENT_PASSWORD>@ep-<hash>-<region>.neon.tech/<db>?sslmode=require` | Railway variables (secret) |
| `LLM_API_KEY` | your LLM provider key | Railway variables (secret) |
| `LLM_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` (Gemini) or `https://api.groq.com/openai/v1` (Groq) | Railway variables |
| `LLM_MODEL` | `gemini-3.8-flash` or `llama-3.3-70b-versatile` | Railway variables |
| `QUERY_TIMEOUT_SECONDS` | `5` | Railway variables |
| `MAX_RETRIES` | `2` | Railway variables |
| `MAX_ROWS` | `1000` | Railway variables |
| `ANSWER_MODE` | `llm` (or `template` for no LLM answer) | Railway variables |
| `RATE_LIMIT_PER_MINUTE` | `10` | Railway variables |
| `RATE_LIMIT_PER_DAY` | `200` | Railway variables |
| `TRUSTED_PROXY_HOPS` | `0` until you know your proxy topology | Railway variables |
| `ALLOW_UI_CONNECTIONS` | `false` | Railway variables |
| `CORS_ORIGINS` | `https://<app>.vercel.app` | Railway variables |
| `LOG_LEVEL` | `INFO` (optional) | Railway variables |

Railway hints at the values for `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` in `.env.example`:
the defaults are the Gemini free tier and the Groq free tier. **Do not put `LLM_API_KEY` in the
frontend's Vercel variables.** Vercel frontend variables are embedded in the browser bundle; a
leaked key there is a real key leak. See section 6.

### 4.3 Expose the backend securely

- Railway's default domain is `https://<name>-<random>.up.railway.app`. Keep `https` only.
- Railway includes a WebSocket-ready proxy. The app is HTTP-only, so no extra hardening is needed.
- The app binds `0.0.0.0`, which Railway requires; do not change it.
- **Do not** expose the database port. Neon connections come from the internet anyway, so there is
  no need to open a port on Railway.

### 4.4 Determine the backend URL

After the deploy is healthy:

```bash
railway up --status  # or open the URL in the browser
```

The backend URL is `https://<name>-<random>.up.railway.app`. It is also shown on the Railway
**Settings → Domains** tab. Use this URL in the Vercel environment variable `BACKEND_URL` (see
section 5) and in the Vercel frontend's `VITE_API_BASE_URL`.

---

## 5. Configure backend environment variables

All settings are environment variables. `backend/app/config.py` documents every field and its
constraints. The authoritative table is `.env.example`; the table below lists the variables that
actually exist. **Never add a variable that does not exist** — the app ignores unknown ones, but
typos can silently disable security controls.

### Backend / container host

| Variable | Default | Meaning | Notes |
|---|---|---|---|
| `DATABASE_URL` | *(none)* | `postgresql://sql_agent:…@…` | **The read-only account only.** Refuses writable accounts. The single most important variable. |
| `LLM_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` | OpenAI-compatible endpoint base | Gemini or Groq (see `.env.example`). |
| `LLM_API_KEY` | *(none)* | LLM provider key | **Server-side only.** Never a frontend env var. |
| `LLM_MODEL` | `gemini-3.8-flash` | Model to call | Gemini 3.8 flash, or Groq `llama-3.3-70b-versatile` etc. |
| `QUERY_TIMEOUT_SECONDS` | `5` | Max query duration | Passed to the DB adapter as `statement_timeout`. `backend/app/config.py` clamps to 0–60. |
| `MAX_RETRIES` | `2` | LLM repair attempts | Bounded: initial generation + ≤ 2 repairs, each validated again. |
| `MAX_ROWS` | `1000` | Client-side result cap | Enforced in the executor regardless of `LIMIT`. |
| `ANSWER_MODE` | `llm` | `llm` (LLM answer, one extra call) or `template` (no extra LLM call) | Choose `template` if you want zero LLM calls for answers. |
| `RATE_LIMIT_PER_MINUTE` | `10` | Per-client address per minute | Sliding window; `0` = off. |
| `RATE_LIMIT_PER_DAY` | `200` | Global per-day cap across all clients | Sliding window; `0` = off. |
| `TRUSTED_PROXY_HOPS` | `0` | How many reverse proxies append to `X-Forwarded-For` | See section on `TRUSTED_PROXY_HOPS`. |
| `ALLOW_UI_CONNECTIONS` | `false` | Add databases through the UI | **Must stay `false` on public deployment.** See section on `ALLOW_UI_CONNECTIONS`. |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed origins for the browser | Comma-separated on Railway; add your Vercel domain. |
| `DATABASES_CONFIG` | *(none)* | Path to TOML of `[[databases]]` entries | If empty, `DATABASE_URL` is a single default DB. Each entry's `url_env` points at a secret env var. |
| `LOG_LEVEL` | `INFO` | Python logging level | JSON lines on stderr. |

### Frontend / Vercel

| Variable | Safe to expose? | How to set |
|---|---|---|
| `VITE_API_BASE_URL` | **Yes** — it is only a URL, no credentials | Vercel **Environment Variables** (client scope) |
| `VITE_API_PROXY_TARGET` | **Yes** — dev-only override, never committed | Vercel (client scope) |
| `VITE_*` anything else | **No** unless the repo explicitly says so | Do not invent them |

The frontend reads `import.meta.env.VITE_API_BASE_URL ?? ''` in `frontend/src/api/client.ts`.
With no value, the dev server proxies `/api` to `http://localhost:8000` via `vite.config.ts`. In
production you set `VITE_API_BASE_URL` to the backend URL (without a trailing slash).

### The "forbidden" list — never touch

The following values **must never** appear in a Vercel frontend environment variable, in any file
committed, or anywhere a browser can read them:

```text
LLM_API_KEY
DATABASE_URL
DATABASES_CONFIG
POSTGRES_PASSWORD
SQL_AGENT_PASSWORD
ADMIN_DATABASE_URL
```

`LLM_API_KEY` is the key you use for the LLM; `DATABASE_URL` is the read-only `sql_agent`
connection. Both are secrets by design. `ADMIN_DATABASE_URL` is the **owner** account used by the
seed script; it can modify the database and is just as sensitive.

### Backups

The README documents an `evaluation/` suite that is not required for deployment. Leave it alone.

---

## 6. Deploy the frontend to Vercel

### 6.1 Project setup

The frontend is a React + TypeScript + Vite app in `frontend/`. The Vercel project root is
`frontend`.

1. Push the repo to GitHub (if not already) and import `Parth-Vasave/ai-sql-analyst-agent` into
   Vercel via **Add New Project → Import Git Repository**.
2. Vercel auto-detects the framework. If it asks, set:

   - **Root Directory**: `frontend`
   - **Build Command**: `tsc -b && vite build`
   - **Output Directory**: `dist`

   Vite's default build output is `frontend/dist`. The `.gitignore` already ignores `dist/`,
   `node_modules/`, etc.

3. The build produces `frontend/dist`, which Vercel serves statically. No server-side code is
   required: all the server-side logic lives in the backend on Railway.

### 6.2 Required Vercel configuration

| Setting | Value |
|---|---|
| Framework preset | `Vite` (Vercel picks this automatically) |
| Root Directory | `frontend` |
| Build Command | `tsc -b && vite build` |
| Output Directory | `dist` |
| Development (optional) | `VITE_API_PROXY_TARGET=http://<railway-domain>` |

### 6.3 How the frontend reaches the backend API

- The frontend **never** calls Neon directly. It only calls the backend via HTTP (`fetch`).
- Vercel serves the built `dist` and acts as a reverse proxy. The `fetch` base URL is:

  ```text
  VITE_API_BASE_URL=https://<name>-<random>.up.railway.app
  ```

  (set in Vercel client env) **or** the Vercel domain itself:

  ```text
  VITE_API_BASE_URL=https://<app>.vercel.app
  ```

  If you point at your own domain, set `CORS_ORIGINS` on the backend to include it.
- The backend's CORS middleware in `backend/app/main.py` allows origins listed in
  `CORS_ORIGINS`, which defaults to `http://localhost:5173` for local dev. Add your Vercel domain
  (and your landing domain if you use one).
- The frontend ships an `X-Request-ID` header on requests, which the backend returns and logs. The
  API never echoes request bodies to the client except the structured `AgentResult`.

### 6.4 CORS configuration

- The backend is the **only** origin allowed by `backend/app/api/routes.py` via `CORSMiddleware`
  with `allow_origins`, `allow_methods=["GET","POST"]`, `allow_headers=["Content-Type",
  "X-Request-ID"]`, `expose_headers=["X-Request-ID"]`.
- Do **not** set `allow_origins=["*"]` in production. That opens the UI to any site, and an
  attacker's page could read the responses if the browser ever credentiated.
- Vercel does **not** add CORS headers on the API route; the backend does. Vercel only proxies
  `https://<app>.vercel.app/api/...` to Railway.
- Vercel's **Settings → Environment Variables** sets env vars for the **build** (client-side) and
  the **server-less functions** (server-side). Put secrets in **Server** scope; put the frontend
  URL in **Client** scope.

### 6.5 Never expose secrets to the frontend — the rule

> **Never put database credentials, LLM API keys, passwords, or other server secrets into the
> frontend build environment.**

Vite compiles `import.meta.env.VITE_*` into the browser bundle. There is no sandboxing: any value
set as a client variable can be read by any visitor of the page, and the bundle is served to
everyone. The following are **server secrets** and must stay on the backend:

- `LLM_API_KEY` — the LLM provider key that signs requests to the LLM provider.
- `DATABASE_URL` — the read-only `sql_agent` PostgreSQL URL.
- `POSTGRES_PASSWORD` — the database owner password.
- `SQL_AGENT_PASSWORD` — the `sql_agent` password.
- `ADMIN_DATABASE_URL` — the owner account used by the seed script.
- `DATABASES_CONFIG` — a TOML file that references secret env var names.

The frontend does not need any of them. The API key never leaves the container host: the app
builds the LLM client in `app/main.py` from settings loaded server-side, and `app/llm/client.py`
sends the key in an `Authorization: Bearer` header to the LLM provider — the browser never sees it.

---

## 7. Configure CORS

CORS is a browser security control, and it is handled by the backend, not by Vercel.

1. Set `CORS_ORIGINS` on Railway to a comma-separated list of the origins you will allow:

   ```text
   CORS_ORIGINS=https://<app>.vercel.app,https://<your-domain>
   ```

   The backend's default `cors_origins` is `["http://localhost:5173"]`. With `0` hops and no
   `X-Forwarded-Proto`, the browser will treat `https://<app>.vercel.app` as a different origin
   from `https://<railway-domain>`, so you must list it.

2. **Do not** set `CORS_ORIGINS=*` on a public deployment. The frontend reaches the backend
   through the Vercel edge; the backend still sees the real IP and rate limits it.

3. The backend exposes `X-Request-ID` via `expose_headers`, so the browser can read it for
   tracing. The frontend includes it back on requests.

---

## 8. Rate limiting and LLM budget

The API rate-limits `POST /api/query` with two sliding windows, checked **before** the agent makes
any LLM call:

| Variable | Meaning | Default |
|---|---|---|
| `RATE_LIMIT_PER_MINUTE` | Requests per **client address** per minute | `10` |
| `RATE_LIMIT_PER_DAY` | Requests **across all clients** per 24 hours | `200` |

The per-client address is the TCP peer unless `TRUSTED_PROXY_HOPS` says how many reverse proxies
append to `X-Forwarded-For` (see the section on `TRUSTED_PROXY_HOPS`).

### Why the limits matter for your LLM budget

Each question can make **1 to 4 LLM calls** to the provider:

- 1 call for the initial plan + SQL generation;
- 1 call per repair (≤ `MAX_RETRIES` = 2);
- 1 call for the natural-language answer when `ANSWER_MODE=llm`.

That is 1–4 calls per question. On the Gemini free tier (about 5 requests/minute and 20/day per
model), a default `RATE_LIMIT_PER_MINUTE=10` eats a large fraction of the minute budget for one
user; a `RATE_LIMIT_PER_DAY=200` can exhaust the day quota with a handful of power users.

**Choose limits based on your available LLM quota/budget, not on what seems "nice".** If you run
the question suite of 78 questions with template answers, each question takes 1 call (plus up to 2
repairs). With `RATE_LIMIT_PER_DAY=200` you can run roughly 200 questions before hitting the
global limit. Use `ANSWER_MODE=template` if you do not need LLM-written answers.

The limiter is **in-memory / per process**. Each Railway worker instance, and each instance in a
family, maintains its own counters. With two Railway instances, the effective limits multiply: a
client can make roughly `2 × RATE_LIMIT_PER_MINUTE` before the same apparent limit, and the global
day budget is the sum of all instances' budgets. The repository's `Known limitations` section
states this explicitly; you should too.

---

## 9. Security checklist

These controls are already in the application. Do not weaken them in this guide, and do not add
flags to the Dockerfile or the start command.

| Control | Where it lives | Status |
|---|---|---|
| `ALLOW_UI_CONNECTIONS=false` | Backend env var | **Required** on public deployment. See below. |
| Read-only `sql_agent` account | `database/permissions.sql` + `DATABASE_URL` | Required: the API connects only as this role. |
| SQL validation | `backend/app/agent/sql_validator.py` | Deterministic AST validation (`sqlglot`). Rejects writes, DDL, system tables, disallowed functions, `SELECT *`, whole-row refs, over-large `LIMIT`. |
| Query timeout | `backend/app/config.py` (`QUERY_TIMEOUT_SECONDS`) + `PostgresAdapter.connect_args()` | Enforced per session. |
| Row limit | `backend/app/config.py` (`MAX_ROWS`) | Enforced in the executor. |
| Retry cap | `backend/app/config.py` (`MAX_RETRIES`) | Bounded: 0–5. |
| Rate limits | `backend/app/api/rate_limit.py` | In-memory per process; see the multi-instance warning. |
| Sensitive columns never rendered | `backend/app/database/profiler.py` / `schema_retriever.py` | Not sent to the LLM. |
| Secrets never to frontend | This guide, section 6 | Rule. |
| Logs never contain secrets | `backend/app/observability.py` | `safe_fields()` drops `question`, `sql`, `rows`, `answer`, `url`, `password`, … |
| Request IDs | `backend/app/main.py`, `backend/app/observability.py` | Every request gets one; returned and logged without the client IP. |

### `ALLOW_UI_CONNECTIONS=false`

`allow_ui_connections` in `backend/app/config.py` gates the `POST /api/databases` route: with it
`false` (the default, and the value in `backend/app/config.py` and `.env.example`), adding databases
from the UI/API is **denied with `403 Forbidden`**. `backend/app/api/routes.py` in the repo says:

```python
if not settings.allow_ui_connections:
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        "Adding databases from the UI is disabled. Set ALLOW_UI_CONNECTIONS=true (local use only).",
    )
```

Enabling it on a public deployment would let any visitor make the server connect to arbitrary
hosts — effectively a self-hosted SQL proxy. **Never enable it publicly.** Do not change the
application's default security behavior to make deployment easier.

### `TRUSTED_PROXY_HOPS`

This variable tells the rate limiter how many reverse proxies in front of the app append the real
client address to `X-Forwarded-For`. The default is `0`.

- `0`: the rate limiter takes the rate limit by the **TCP peer** (the IP the load balancer sees)
  and **ignores** `X-Forwarded-For` entirely — because any client can forge that header.
- `1`: trust the last entry in `X-Forwarded-For` (added by the single proxy).
- `N`: trust only entries added by the *outermost* `N` proxies; entries beyond that were added by
  the client and are **never** trusted.

Why it matters: if you set it too high (e.g. `5` on Railway, which does not add
`X-Forwarded-For`), the app may fall back to trusting a forged header and rate-limit by the
attacker's chosen address — defeating the limits. If you set it too low, all clients from behind
the proxy get a different `client_address` and the per-client limit stops working.

**For Railway** the container does not terminate TLS or append `X-Forwarded-For`. Keep
`TRUSTED_PROXY_HOPS=0`. Railway's own proxy is TLS-terminating only; no hop appends the header.
If you later put a custom Nginx / Caddy / Cloudflare in front, set it to the number of those hops
that append `X-Forwarded-For` and keep it at or below the actual topology. `backend/app/api/
rate_limit.py` checks the header length: if there are fewer entries than `trusted_proxy_hops`, it
falls back to the TCP peer rather than trusting a short header.

### `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_PER_DAY`

See section 8.

---

## 10. Post-deployment verification

Verifying the whole stack requires accounts on Neon, Railway, and Vercel, and an LLM API key.
**I did not run these against the live services; do the checks below with your own accounts and
an LLM API key before declaring the deployment complete.** Distinguish:

- **Verified locally** — I ran the data pipeline, the seed script, the read-only role checks, and
  the API tests against a local Postgres, exactly as documented. Commands that I ran locally:
  `python -m scripts.ingest_data`, `python -m scripts.clean_data`, `python -m scripts.seed_database`,
  `scripts/tests/test_database.py`, `backend/tests/test_rate_limit.py`, etc.
- **Requires verification by a human with Neon/Vercel/backend-host accounts** — the Neon database
  creation, the Railway deploy, the Vercel build and env var setup, and the live HTTP checks.

### 10.1 Health endpoint

Call the deployed backend URL (from Railway's **Domains** tab):

```bash
curl -s -i https://<railway-domain>/api/health | head -20
```

Expected successful response (when the database is reachable):

```json
{"status":"ok","databases":{"default":"ready"}}
```

- `status` is `ok` only when **every** configured database answers `READY`. If a database is
  unreachable, the endpoint answers `503` with `{"status":"degraded","databases":{...}}`.
- The `GET /api/health` route in `backend/app/api/routes.py` answers `503` while a database is
  unreachable; the Docker `HEALTHCHECK` curls `http://127.0.0.1:8000/api/health` and marks the
  container unhealthy until then.
- The backend binds `0.0.0.0:8000` only. Railway forwards to that port.

### 10.2 Successful query

Send one valid query through `POST /api/query`. The API schema is `QueryRequest`:

```json
{
  "question": "Top 5 CO2 emitters in 2023",
  "database_id": "owid",
  "history": []
}
```

Use the `owid` database id (from `databases.example.toml`, URL env `DATABASE_URL` — set in Railway).
The demo database ships with `countries`, `country_indicators`, `co2_emissions`, `ghg_emissions`
taken from the pinned OWID commit. An example response:

```json
{
  "status": "success",
  "question": "Top 5 CO2 emitters in 2023",
  "answer": "China emitted the most CO2 in 2023, followed by the United States, India, Russia, and Japan.",
  "plan": { "intent": "ranking", "tables": ["public.co2_emissions"], "metrics": ["co2_emissions.co2"] },
  "sql": "SELECT co2_emissions.co2 FROM public.co2_emissions WHERE co2_emissions.year = 2023 ORDER BY co2_emissions.co2 DESC LIMIT 5",
  "columns": ["co2"],
  "rows": [[12172.009], [4918.407], [3062.756], [1733.135], [986.91]],
  "column_units": { "co2": "Mt" },
  "chart_suggestion": "bar",
  "chart": { "type": "bar", "x": "co2", "y": [] },
  "checks": [],
  "trace": [
    { "step": "question_received", "status": "success", "duration_ms": 1 },
    { "step": "schema_retrieval", "status": "success", "duration_ms": 42 },
    { "step": "sql_generation", "status": "success", "duration_ms": 2130 },
    { "step": "sql_validation", "status": "success", "duration_ms": 6 },
    { "step": "query_execution", "status": "success", "duration_ms": 340, "rows": 5 },
    { "step": "result_validation", "status": "success", "duration_ms": 12 },
    { "step": "answer_generation", "status": "success", "duration_ms": 1200, "source": "llm" },
    { "step": "chart_selection", "status": "success", "duration_ms": 3 },
    { "step": "completed", "status": "success", "duration_ms": 3800, "retries": 0 }
  ],
  "metadata": {
    "database_id": "owid",
    "dialect": "postgresql",
    "model": "gemini-3.8-flash",
    "prompt_version": "sql-generator/3",
    "tables_used": ["public.co2_emissions"],
    "execution_time_ms": 340,
    "row_count": 5,
    "truncated": false,
    "retry_count": 0,
    "request_id": "..."
  }
}
```

The exact `answer` text is LLM-dependent; the fields shown are the ones the API always returns.
The `metadata.request_id` matches the `X-Request-ID` header.

**Run it via curl** (from your machine or Railway CI):

```bash
curl -s -X POST https://<railway-domain>/api/query \
  -H 'content-type: application/json' \
  -d '{"question":"Top 5 CO2 emitters in 2023","database_id":"owid"}'
```

### 10.3 Rejected query

Send one query that should be rejected by the application's safety controls. The SQL validator in
`backend/app/agent/sql_validator.py` refuses:

- any non-`SELECT` statement, including writes (`INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`,
  `DROP`, `CREATE`, `ALTER`, `COPY`, `GRANT`), DDL, `SET`, `SELECT INTO`, `FOR UPDATE`;
- system catalogs (`pg_catalog`, `information_schema`, `pg_toast`) and `pg_*` tables;
- unknown tables / columns not in the database profile;
- `SELECT *` and whole-row references;
- disallowed functions (`pg_sleep`, `dblink`, `set_config`, `current_setting`, file/network);
- `LIMIT` over `MAX_ROWS` (default 1000; the validator clamps it).

An example that must be rejected (consistent with committed files):

```json
{
  "question": "Replace all CO2 numbers with zero",
  "database_id": "owid"
}
```

Response:

```json
{
  "status": "error",
  "question": "Replace all CO2 numbers with zero",
  "error": {
    "category": "validation",
    "message": "INSERT is not allowed in a read-only query.",
    "code": "forbidden_operation"
  },
  "sql": "INSERT ...",
  "plan": null,
  "metadata": {...}
}
```

The trace shows `sql_validation` as `failed`, and `query_execution` never runs. Because this is
classified as **not repairable** (a write), the controller returns the error instead of trying to
repair it. That is the correct behavior: the model's intent was unsafe, and asking again will not
fix it. A second safety layer: the database itself refuses any write from `sql_agent` (see section
2). Both layers must remain intact.

### 10.4 Frontend check

- Open `https://<app>.vercel.app` (or your custom domain) in a browser. The UI should load and
  show the demo data as one of the connected databases.
- Open the browser DevTools **Network** tab, load a question, and confirm the request to
  `/api/query` is made **from the browser** to your backend URL (not to Neon). Open the response
  and confirm no database password or LLM key appears anywhere in the response body or headers.
- Confirm the bundle does not contain `LLM_API_KEY` or `DATABASE_URL`:

  ```bash
  grep -roE "LLM_API_KEY|DATABASE_URL|POSTGRES_PASSWORD|SQL_AGENT_PASSWORD|ADMIN_DATABASE_URL" frontend/dist | head
  ```

  There should be no matches. (If you see the string `LLM_API_KEY` anywhere in Vercel's client
  environment, the build is wrong.)

---

## Multi-instance limitation

> The rate limiter is **in-memory / per process**.

`backend/app/api/rate_limit.py` stores per-client and global counters in process memory. That means:

```text
multiple backend instances
        ↓
each instance has its own rate-limit state
        ↓
effective limits can multiply
```

- The **per-client** limit (`RATE_LIMIT_PER_MINUTE`) applies per instance; with `N` instances a
  single client can make roughly `N × RATE_LIMIT_PER_MINUTE` requests before its own limit is hit
  (each instance enforces its own window).
- The **global** limit (`RATE_LIMIT_PER_DAY`) is the sum of each instance's window; with `N`
  instances the effective day budget is `N × RATE_LIMIT_PER_DAY`.

If you plan to scale the backend to multiple Railway dynos or to serverless (Vercel Functions for
the backend), **read the in-memory limiter's limitation first**. Issue #7 of this repository
(`https://github.com/Parth-Vasave/ai-sql-analyst-agent/issues/7`) tracks the shared-store
replacement: a central rate-limit service or a shared store (Redis) so that every instance enforces
one shared budget. Do not assume the current defaults are appropriate until you have read Issue #7.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `GET /api/health` returns 503 | A configured database is not `READY` (unreachable during the request) | Check `DATABASE_URL` is reachable from Railway. The health endpoint retries the connection on each call; it answers ready when the role can connect and is read-only. |
| `403 Forbidden` on `POST /api/databases` | UI/database-add is disabled (default) | Expected on public deployment. Do not set `ALLOW_UI_CONNECTIONS=true`. |
| `422 Unprocessable Content` on `POST /api/query` | `question` empty or longer than 500 chars | Keep `question` non-empty and ≤ 500 characters. |
| `429 Too Many Requests` | Rate limit hit | Read `Retry-After`; lower the LLM model's rate or raise `RATE_LIMIT_PER_MINUTE/DAY` to fit your quota. |
| All queries fail with `database is rejected` | `DATABASE_URL` points at a writable account | Set `DATABASE_URL` to `postgresql://sql_agent:<password>@…`. The app logs `connection rejected: account is not read-only`. |
| `503` on `POST /api/query` | No LLM configured (`LLM_API_KEY` empty) | The `get_agent` dependency raises `503` with `No LLM configured: set LLM_API_KEY.` |
| `503` on `POST /api/query` | LLM provider error | LLM retries are bounded; the app raises `503` after `max_attempts` = 3. Check `LLM_BASE_URL`/`LLM_MODEL` and the provider's status. |
| SQL returns `429` in the LLM provider | Provider rate limited | The client retries with backoff, then fails after `max_attempts` = 3. Increase the provider's rate limit or lower your request rate. |
| Frontend cannot reach the API | CORS not configured | Add your Vercel domain to `CORS_ORIGINS` on the backend. |
| `CORS` errors in the browser | `CORS_ORIGINS` missing the Vercel domain | Full error in the browser Console; update `CORS_ORIGINS`. |
| Data seed fails with `InsufficientPrivilege` | `ADMIN_DATABASE_URL` points at `sql_agent` | Seed must run as the **owner** account via `ADMIN_DATABASE_URL`. |
| Schema setup fails | `SQL_AGENT_PASSWORD` not set when running `00_init.sh` | Export `SQL_AGENT_PASSWORD` before running the init script. |
| Rate limits not consistent across workers | In-memory limiter | If you scale to multiple instances, read the multi-instance limitation above (Issue #7). |

---

## Known limitations

These are copied from the repository's `Known limitations` section and must not be weakened:

- **PostgreSQL only**; MySQL is not implemented.
- **The rate limiter is in memory per process.** Multi-instance or serverless deployments need a
  shared store (see Issue #7: https://github.com/Parth-Vasave/ai-sql-analyst-agent/issues/7).
- **Public deployment (Vercel + Neon) is not done yet** — this guide is the first documented path.
- **Results depend on the chosen model**; only one model has been evaluated so far.
- The in-memory rate limiter means `RATE_LIMIT_PER_MINUTE` and `RATE_LIMIT_PER_DAY` are per
  process, not shared across instances.
- `ALLOW_UI_CONNECTIONS` is local/self-hosted only; never enable it on a public deployment.

---

## Alternative container hosts

The walkthrough uses **Railway**, but the guide is the same for Render and Fly.io. The only things
that change are the UI and a few settings.

### Render

- **Build**: `pip install -r requirements.txt`
- **Start**: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log`
- Render auto-inspects the `backend/Dockerfile`; if you use the Docker runtime, choose **Dockerfile**
  and set the build context to `backend`.
- Enable **Auto-suspend** (free tier) — Railway behaves the same way.
- Render does not expose a port by default; the app binds `0.0.0.0:8000`.

### Fly.io

- Use the same `backend/Dockerfile`; Fly builds it and starts with
  `uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log`.
- Fly apps publish on `$PORT`; the app ignores it and hard-codes `8000`.
- Fly's load balancer terminates TLS and adds `X-Forwarded-For`, but it is only the edge; keep
  `TRUSTED_PROXY_HOPS=0` until you add a proxy of your own.

### Shared gotcha

For all three hosts, the **port is 8000** and the **start command** is the Dockerfile CMD. The app
never reads a `PORT` variable. The only environment variable that changes is `CORS_ORIGINS` (add
your host's public domain) and `TRUSTED_PROXY_HOPS` (0 for all three, until you add a proxy).

---

## Environment variable reference

### Backend / container host (complete)

| Variable | Default | Required | Meaning |
|---|---|---|---|
| `DATABASE_URL` | — | **Yes** | `postgresql://sql_agent:…@<neon-host>.neon.tech/<db>?sslmode=require` |
| `LLM_API_KEY` | — | **Yes** | LLM provider key (server-side) |
| `LLM_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` | No | OpenAI-compatible endpoint base |
| `LLM_MODEL` | `gemini-3.8-flash` | No | Model name |
| `QUERY_TIMEOUT_SECONDS` | `5` | No | Max query duration (0–60) |
| `MAX_RETRIES` | `2` | No | Max LLM repair attempts (0–5) |
| `MAX_ROWS` | `1000` | No | Client-side result cap (1–10000) |
| `ANSWER_MODE` | `llm` | No | `llm` or `template` |
| `RATE_LIMIT_PER_MINUTE` | `10` | No | Per-client per-minute limit (`0`=off) |
| `RATE_LIMIT_PER_DAY` | `200` | No | Global per-day limit (`0`=off) |
| `TRUSTED_PROXY_HOPS` | `0` | No | Reverse-proxy hops that append to `X-Forwarded-For` |
| `ALLOW_UI_CONNECTIONS` | `false` | **No — keep false** | Add databases through UI/API. Local use only. |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | No | Comma-separated allowed origins |
| `DATABASES_CONFIG` | — | No | Path to TOML of `[[databases]]`; URLs via env vars named by `url_env` |
| `LOG_LEVEL` | `INFO` | No | Python logging level |

### Frontend / Vercel (only two safe client variables)

| Variable | Safe? | Meaning |
|---|---|---|
| `VITE_API_BASE_URL` | **Yes** | Backend URL, no trailing slash |
| `VITE_API_PROXY_TARGET` | **Yes** (dev) | Dev proxy target, only used by Vite dev server |

Everything else that appears in `.env.example` besides these two is a **server secret**. The
complete forbidden list is:

```text
LLM_API_KEY
DATABASE_URL
DATABASES_CONFIG
POSTGRES_PASSWORD
SQL_AGENT_PASSWORD
ADMIN_DATABASE_URL
```

---

*This guide was written against the repository state as of the current commit: Dockerfile, startup
configuration, API routes, rate limiter, CORS, frontend Vite config, and `database/permissions.sql`.*
