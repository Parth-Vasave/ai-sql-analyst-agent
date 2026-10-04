# Deployment: Neon + Vercel + Railway

A low-cost public setup: **Neon** for PostgreSQL, **Railway** for the FastAPI backend, **Vercel**
for the frontend. Render or Fly.io work the same way for the backend (see [Other hosts](#other-hosts)).

> **Status: this setup has not been run end to end.** Every command, setting and file reference
> below was checked against the repository, but not against live Neon, Railway or Vercel accounts.
> Run the [post-deployment checks](#7-post-deployment-checks) before you rely on it, and please
> open an issue for anything that differs. The first version of this guide was contributed in
> [#12](https://github.com/Parth-Vasave/ai-sql-analyst-agent/pull/12).

```text
browser ──▶ Vercel (static frontend)
   │
   └──── fetch ──▶ Railway (FastAPI, port 8000) ──▶ Neon PostgreSQL, as the read-only sql_agent role
```

The browser calls the backend directly; Vercel only serves the built files. The frontend never
talks to the database, and the backend connects only as `sql_agent`.

## Before you start

- Accounts on Neon, Railway and Vercel, and an API key for any OpenAI-compatible LLM provider
  (`.env.example` lists the Gemini and Groq free tiers).
- On your machine: a clone of this repository, Python 3.11+, and `psql`.
- Two passwords: Neon generates the owner's; you choose the one for `sql_agent`.

Secrets belong only in the Railway variables and in your shell. Never in Vercel, in a commit, or
in a screenshot.

## 1. Create the database and the read-only role

1. In Neon, create a project. Copy its **connection string** from the dashboard. It connects as
   the database **owner** (the role name is shown in the string) and looks like
   `postgresql://<owner>:<password>@<endpoint>.neon.tech/<db>?sslmode=require`.
2. From your clone, create the schema and the `sql_agent` role with the repository's init script.
   It runs `database/schema.sql`, then `database/permissions.sql`:

   ```bash
   export ADMIN_DATABASE_URL='postgresql://<owner>:<password>@<endpoint>.neon.tech/<db>?sslmode=require'
   export SQL_AGENT_PASSWORD='<a long random password>'
   export QUERY_TIMEOUT_SECONDS=5          # optional; becomes sql_agent's statement_timeout
   ./database/init/00_init.sh
   ```

   `permissions.sql` is idempotent: re-run the script to rotate the `sql_agent` password or change
   the timeout. It gives `sql_agent` `SELECT` on the four data tables and nothing else.

3. **Check that `sql_agent` really cannot write.** Connect **as `sql_agent`**, never as the owner:

   ```bash
   psql 'postgresql://sql_agent:<SQL_AGENT_PASSWORD>@<endpoint>.neon.tech/<db>?sslmode=require' \
     -c "SET default_transaction_read_only = off; CREATE TABLE should_fail (id int);"
   ```

   This must fail with `permission denied`. If it succeeds, you connected as the wrong role: drop
   the table and check the URL. The same checks run in CI against a disposable database
   (`scripts/tests/test_database.py`).

## 2. Load the data

The seed runs as the **owner** (`ADMIN_DATABASE_URL`), never as `sql_agent`:

```bash
pip install -r scripts/requirements.txt
python -m scripts.ingest_data      # downloads the pinned OWID commit and checks both SHA-256 hashes
python -m scripts.clean_data       # writes data/processed/*.csv and cleaning_report.json
python -m scripts.seed_database    # uses ADMIN_DATABASE_URL from step 1
```

Existing rows are skipped (`ON CONFLICT ... DO NOTHING`); `python -m scripts.seed_database
--replace` truncates the four tables and reloads them. `data/README.md` describes the dataset and
the cleaning rules.

## 3. Deploy the backend on Railway

1. **New Project → Deploy from GitHub repo**, select your copy of this repository, and set the
   service's **root directory** to `backend` so Railway builds `backend/Dockerfile`.
2. The container runs `uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log` and
   ignores `PORT`. When you generate the public domain, set the **target port to 8000**. Keep
   `--no-access-log`: uvicorn's access log records client IP addresses, and the app writes its own
   request log without them.
3. Add the variables below under **Variables**, then deploy. The Dockerfile's health check calls
   `/api/health`, which answers 503 until the database is reachable.

| Variable | Value |
|---|---|
| `DATABASE_URL` | `postgresql://sql_agent:<SQL_AGENT_PASSWORD>@<endpoint>.neon.tech/<db>?sslmode=require`. **The read-only role only:** a connection that can modify data is refused. |
| `LLM_API_KEY` | Your provider key. Secret, backend only. |
| `LLM_BASE_URL`, `LLM_MODEL` | As in `.env.example` (Gemini by default, Groq commented out). |
| `ALLOW_UI_CONNECTIONS` | `false`. **Never `true` on a public deployment:** it lets any visitor make the server connect to any host. |
| `CORS_ORIGINS` | `["https://<app>.vercel.app"]`. **A JSON list**, quotes and brackets included. A bare or comma-separated value stops the backend from starting. |
| `TRUSTED_PROXY_HOPS` | `0`. See [Rate limits](#5-rate-limits-and-llm-budget). |
| `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_PER_DAY` | `10` and `200` by default. Size them to your LLM quota. |

Optional: `QUERY_TIMEOUT_SECONDS` (default 5, max 60), `MAX_ROWS` (1000, max 10,000), `MAX_RETRIES`
(2, max 5), `ANSWER_MODE` (`llm` or `template`), `LOG_LEVEL` (`INFO`). `.env.example` documents
every setting; the backend reads them in `backend/app/config.py`.

Never set `ADMIN_DATABASE_URL`, `POSTGRES_PASSWORD` or `SQL_AGENT_PASSWORD` on the backend. Only
the seed and the init script need them, and they run from your machine.

## 4. Deploy the frontend on Vercel

1. **Add New Project → Import Git Repository**. Root directory `frontend`, framework preset
   **Vite**. The defaults match `package.json`: build `npm run build` (`tsc -b && vite build`),
   output `dist`.
2. Set one environment variable: `VITE_API_BASE_URL=https://<backend>.up.railway.app`, with no
   trailing slash. The frontend calls `${VITE_API_BASE_URL}/api/...`.

There is no rewrite or proxy on Vercel, so `VITE_API_BASE_URL` is required in production; the
`/api` proxy in `vite.config.ts` only exists in the dev server.

> Every `VITE_*` variable is compiled into the JavaScript bundle and readable by anyone. The
> backend URL is the only value the frontend needs. Never put an API key, database URL or password
> in Vercel.

After the first deploy, put the exact Vercel origin in the backend's `CORS_ORIGINS`, for example
`["https://<app>.vercel.app","https://<your-domain>"]`. Never `["*"]`.

## 5. Rate limits and LLM budget

`POST /api/query` is limited before any LLM call is made: `RATE_LIMIT_PER_MINUTE` per client
address, and `RATE_LIMIT_PER_DAY` for all clients together. One question uses between 1 and
`MAX_RETRIES + 2` LLM calls (4 with the defaults): SQL generation, up to `MAX_RETRIES` repairs, and
the written answer when `ANSWER_MODE=llm`. Pick the daily limit so that the worst case fits your
provider's quota; `ANSWER_MODE=template` saves one call per question.

**`TRUSTED_PROXY_HOPS`** says how many proxies in front of the app append the client address to
`X-Forwarded-For`. With `0`, the header is ignored and the TCP peer is used. That can't be spoofed,
but behind a platform proxy the peer is the proxy, so **all visitors share one per-client limit**.
Railway's edge proxy does append `X-Forwarded-For`, but the number of entries it adds depends on
the routing path (its CDN adds a hop). Keep `0` unless you have confirmed a fixed hop count for
your setup. A value that is too high lets clients choose their own address by forging the header.

The limiter keeps its windows **in memory, per process**: with several instances, each enforces
its own limits, so the effective limits multiply. Run a single instance until
[#7](https://github.com/Parth-Vasave/ai-sql-analyst-agent/issues/7) adds a shared store.

## 6. Security checklist

- [ ] The backend's `DATABASE_URL` uses `sql_agent`, and the write check in step 1 failed as expected
- [ ] `ALLOW_UI_CONNECTIONS=false`
- [ ] `CORS_ORIGINS` lists only your frontend origin(s), as a JSON list
- [ ] The only Vercel variable is `VITE_API_BASE_URL`
- [ ] The rate limits fit your LLM quota, and only one backend instance runs
- [ ] Owner credentials (`ADMIN_DATABASE_URL`) exist only on your machine

The application enforces the rest: AST validation of every query, the read-only role and session,
the statement timeout, row limits, the retry cap, and logs without questions, SQL, rows, URLs or
keys. The [Security model](../README.md#security-model) describes each layer.

## 7. Post-deployment checks

```bash
API=https://<backend>.up.railway.app

curl -s "$API/api/health"
# {"status":"ok","databases":{"default":"ready"}}    (503 and "degraded" while a database is down)

curl -s "$API/api/query" -H 'content-type: application/json' \
  -d '{"question": "Top 5 CO2 emitters in 2023"}'
# "status": "success", with the plan, the validated SQL, rows, chart, answer and trace

curl -s "$API/api/query" -H 'content-type: application/json' \
  -d '{"question": "Delete every row in the countries table"}'
# expect "unanswerable" (refused) or "error" (rejected SQL); nothing is written either way

curl -s -o /dev/null -w '%{http_code}\n' "$API/api/databases" \
  -H 'content-type: application/json' -d '{"name": "x", "url": "postgresql://u:p@example.com/db"}'
# 403: adding databases is disabled
```

With a single `DATABASE_URL` the database id is `default`. Requests without `database_id` use the
first ready database.

Then open the Vercel URL, ask a question, and check in the browser's network tab that requests go
to the Railway domain and that no response contains a key or password. Locally,
`grep -rE "LLM_API_KEY|DATABASE_URL|PASSWORD" frontend/dist` after `npm run build` should find
nothing.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Backend exits at startup with `error parsing value for field "cors_origins"` | `CORS_ORIGINS` is not a JSON list. Use `["https://<app>.vercel.app"]`. |
| Browser shows CORS errors | The Vercel origin is missing from `CORS_ORIGINS`, or has a trailing slash or a different domain. |
| `/api/health` returns 503 with `"rejected"` | `DATABASE_URL` uses an account that can modify data. Use `sql_agent`. |
| `/api/health` returns 503 with `"unavailable"` | The URL, password or `sslmode` is wrong, or the Neon endpoint is suspended. |
| `POST /api/query` returns 503 `No LLM configured: set LLM_API_KEY.` | `LLM_API_KEY` is empty. |
| `POST /api/query` returns 503 `No database is ready.` | No configured database is ready. Check `/api/health`. |
| `POST /api/query` returns 404 `Unknown database` | Wrong `database_id`. It is `default` with a single `DATABASE_URL`. |
| `POST /api/query` returns 429 | A rate limit was hit. The `Retry-After` header says when to retry. |
| `POST /api/query` returns 422 | The question is empty or longer than 500 characters. |
| The seed fails with a permission error | `ADMIN_DATABASE_URL` points at `sql_agent`. Seeding needs the owner. |
| `00_init.sh` stops with `SQL_AGENT_PASSWORD must be set` | Export `SQL_AGENT_PASSWORD` first. |

## Other hosts

Render and Fly.io can run the same `backend/Dockerfile`. Use `backend` as the build context and
route traffic to port 8000, since the app does not read `PORT`. Both put a proxy in front of the
app, so the `TRUSTED_PROXY_HOPS` advice above applies: keep `0` unless you have confirmed the hop
count from the host's documentation. The variables, the CORS setting and the checks are the same.
