AI SQL Analyst — Development Progress

Current Phase

Milestone 1 — Dataset ingestion + PostgreSQL (code complete; blocked on real data)

Current Objective

Load the real AGMARKNET dataset and verify the manual analytical queries on it.

⸻

Milestone 1 — Dataset ingestion + PostgreSQL

* [x] Rename claude.md → CLAUDE.md
* [x] Identify official mandi dataset (data.gov.in / AGMARKNET; see data/README.md)
* [x] Document dataset source, columns, cleaning rules and assumptions (data/README.md)
* [x] Ingestion script: data.gov.in API → data/raw + provenance manifest (scripts/ingest_data.py)
* [x] Cleaning script with per-rule drop counts (scripts/clean_data.py)
* [x] Normalized PostgreSQL schema + indexes + CHECK constraints (database/schema.sql)
* [x] Read-only sql_agent role: SELECT only, read-only default, statement_timeout (database/permissions.sql)
* [x] Seed script: one transaction, idempotent (scripts/seed_database.py)
* [x] Backend skeleton: FastAPI + settings + GET /api/health
* [x] docker-compose (postgres, backend, seed) + .env.example + .gitignore
* [x] Tests: cleaning rules, seeding, role privileges, timeout, health endpoint
* [x] Manual analytical queries written (database/queries/sanity_checks.sql), verified on synthetic fixture
* [ ] Download real dataset and record download date
* [ ] Seed real data and run sanity_checks.sql on it
* [ ] Decide dataset scope (commodities / states / years) and size of committed sample

Milestone 2 — Basic Question → SQL → PostgreSQL → Result

* [ ] LLM client abstraction (OpenAI-compatible; scripted fake client for tests)
* [ ] Schema metadata from information_schema + column comments
* [ ] SQL generator with structured JSON output
* [ ] Executor (sql_agent connection, timeout, read-only transaction)
* [ ] POST /api/query (minimal)

Milestone 3 — SQL safety validation

* [ ] AST validation with sqlglot: single SELECT only, allow-listed tables/columns, no system catalogs
* [ ] Reject INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT/REVOKE, multiple statements
* [ ] Block dangerous functions (pg_sleep, pg_read_file, dblink, ...)
* [ ] Security tests

Milestone 4 — Read-only user + timeout + LIMIT enforcement

* [x] Read-only role and database-level timeout (done early in Milestone 1)
* [ ] LIMIT enforcement by AST rewrite (add or clamp to MAX_ROWS)
* [ ] Timeout surfaced as a trace event with retry for a cheaper query

Milestone 5 — Query planner
Milestone 6 — Automatic SQL repair/retry (max 2)
Milestone 7 — Result validation (deterministic checks)
Milestone 8 — Natural-language answer generation
Milestone 9 — Chart generation
Milestone 10 — Execution trace + structured logging + request IDs
Milestone 11 — Evaluation framework (50+ questions, result-based scoring, safety suite)
Milestone 12 — React frontend (Vite + TS + Tailwind + Recharts)
  * Use the `frontend-design` plugin (Anthropic directory) and impeccable.style design guidance
Milestone 13 — Tests, Docker, README, Vercel deployment, polish

⸻

Completed Work

* Milestone 1 code, schema, role, scripts and tests. 29 pipeline/database tests + 3 API tests pass.
* docker compose stack verified: postgres init creates schema + role, backend /api/health returns ok,
  seed service loads data, sql_agent write attempts are denied.

⸻

Current Blockers

* Real data: the development environment's network policy blocks data.gov.in and agmarknet.gov.in.
  Options: allow api.data.gov.in in the environment network settings and provide DATA_GOV_IN_API_KEY,
  or download a CSV manually and add it to data/raw/.

⸻

Important Decisions

* Dataset: data.gov.in "Variety-wise Daily Market Prices" (historical) instead of the "current daily"
  resource, which only covers the latest day and cannot answer multi-year questions.
* Security boundary is the database: sql_agent has SELECT on three tables only; read-only default and
  statement_timeout are set on the role and again per session. The SQL validator is a second layer.
* Seeding/ingestion use a separate owner account (ADMIN_DATABASE_URL); the API never gets it.
* psycopg 3 with plain SQL, no ORM: the schema is small and read-only for the app.
* Schema via idempotent SQL scripts instead of a migration tool (Alembic not needed yet).
* LLM: free-tier, OpenAI-compatible provider (default Groq, llama-3.3-70b-versatile); swappable via
  LLM_BASE_URL / LLM_MODEL (Gemini, OpenRouter, local Ollama). To confirm before Milestone 2.
* Deployment target: Vercel (frontend + FastAPI serverless function) with a managed Postgres (e.g. Neon).
  Short-lived DB connections chosen with serverless in mind.
* Synthetic test fixture uses obviously fake place names and is never loaded into the app database.

⸻

Notes for Next Session

Read this file and inspect the repository before continuing.
Local dev DB: see .env.example. Integration tests need TEST_ADMIN_DATABASE_URL and TEST_SQL_AGENT_PASSWORD
(an empty, disposable database; the tests reset the cluster-wide sql_agent password).
Run tests: `python -m pytest scripts/tests` and `cd backend && python -m pytest`.
