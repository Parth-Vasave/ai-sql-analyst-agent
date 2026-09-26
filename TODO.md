AI SQL Analyst — Development Progress

Current Phase

Milestone 1 — Dataset ingestion + PostgreSQL (complete)

Current Objective

Start Milestone 2: question → SQL → PostgreSQL → result.

⸻

Milestone 1 — Dataset ingestion + PostgreSQL

* [x] Rename claude.md → CLAUDE.md
* [x] Dataset: Our World in Data CO2 & GHG emissions, pinned commit + SHA-256 (see data/README.md)
* [x] Document dataset source, columns, cleaning rules, assumptions and caveats (data/README.md)
* [x] Ingestion script: download pinned OWID commit, verify hashes, write manifest (scripts/ingest_data.py)
* [x] Cleaning: entity classification, (GCP) duplicate removal, split into tables, report (scripts/clean_data.py)
* [x] Normalized schema: countries, country_indicators, co2_emissions, ghg_emissions; unit comments,
      CHECK constraints, indexes (database/schema.sql)
* [x] Read-only sql_agent role: SELECT only, read-only default, statement_timeout (database/permissions.sql)
* [x] Seed script: one transaction, idempotent, header validation (scripts/seed_database.py)
* [x] Backend skeleton: FastAPI + settings + GET /api/health
* [x] docker-compose (postgres, backend, seed pipeline) + .env.example + .gitignore
* [x] Tests: cleaning rules, seeding, role privileges, timeout, health endpoint
* [x] Manual analytical queries verified on the full real dataset (database/queries/sanity_checks.sql)

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

* Milestone 1 (first on AGMARKNET mandi prices, then reworked for OWID CO2 data).
  35 pipeline/database tests + 3 API tests pass. Full dataset loads in ~2 s.
* docker compose stack verified: postgres init creates schema + role, backend /api/health returns ok,
  seed service downloads, cleans and loads the data, sql_agent write attempts are denied.

⸻

Current Blockers

None.

⸻

Important Decisions

* Dataset: Our World in Data CO2 & GHG emissions (CC BY 4.0) instead of AGMARKNET mandi prices.
  The official mandi sources (data.gov.in, AGMARKNET) were not reachable/downloadable in a reproducible way;
  OWID is real, citable and downloadable by script from a pinned commit with verified hashes.
* Aggregates (World, continents, income groups) are kept but classified via countries.entity_type so
  "countries" questions can exclude them; "(GCP)" duplicate regions are excluded.
* Security boundary is the database: sql_agent has SELECT on four tables only; read-only default and
  statement_timeout are set on the role and again per session. The SQL validator is a second layer.
* Seeding/ingestion use a separate owner account (ADMIN_DATABASE_URL); the API never gets it.
* psycopg 3 with plain SQL, no ORM: the schema is small and read-only for the app.
* Schema via idempotent SQL scripts instead of a migration tool (Alembic not needed yet).
* LLM: free-tier, OpenAI-compatible provider (default Groq, llama-3.3-70b-versatile); swappable via
  LLM_BASE_URL / LLM_MODEL (Gemini, OpenRouter, local Ollama). To confirm before Milestone 2.
* Deployment target: Vercel (frontend + FastAPI serverless function) with a managed Postgres (e.g. Neon).
  Short-lived DB connections chosen with serverless in mind.
* Test fixture is an unmodified real extract of the OWID file; malformed cases are built in memory.

⸻

Notes for Next Session

Read this file and inspect the repository before continuing.
Local dev DB: see .env.example. Rebuild data: ingest_data → clean_data → seed_database (or `docker compose run --rm seed`). Integration tests need TEST_ADMIN_DATABASE_URL and TEST_SQL_AGENT_PASSWORD
(an empty, disposable database; the tests reset the cluster-wide sql_agent password).
Run tests: `python -m pytest scripts/tests` and `cd backend && python -m pytest`.
