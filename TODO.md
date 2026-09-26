AI SQL Analyst — Development Progress

Current Phase

Milestone 11 — Evaluation framework: built; the question suite still has to be run (needs LLM quota)

Current Objective

Run the question suite (python -m evaluation.run --suite questions) and record the report in
EVALUATION_PLAN.md's Evaluation History. On the free Gemini tier this takes daily batches resumed
with --run-id; with billing on the key it is one run. Never record numbers that were not produced by
a run. Then Milestone 12 (frontend). Before a public deployment still add request rate limiting
(Milestone 13).

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

Milestone 2 — Database-agnostic layer + Question → SQL → Result

Goal: the analyst adapts to ANY connected database (not just the OWID demo) and queries it safely.

2a. Database layer and automatic profiling (no LLM)
* [x] Connection registry: databases from config file (databases.toml, url_env) and, when
      ALLOW_UI_CONNECTIONS=true (local/self-hosted only), added at runtime through the API
* [x] SQLAlchemy Core engine layer (NullPool, read-only session, timeout) + adapter interface
* [x] PostgreSQL adapter: URL normalization, read-only/timeout session options, privilege check
* [x] Privilege check on connect: refuse connections whose account can modify data
* [x] Profiler: tables, columns, types, comments, PK/FK, row estimates, inferred joins,
      sensitive-column detection, value hints by sampling mode, schema fingerprint + cache
* [x] API: GET /api/databases, GET /api/databases/{id}/profile, POST /api/databases (local mode)
* [x] Tests on two differently shaped schemas

2b. Question → SQL → Result
* [x] LLM client abstraction (OpenAI-compatible over httpx; scripted client for tests)
* [x] Schema retriever: keyword retrieval (+ join neighbours), whole schema when small,
      sensitive columns never rendered
* [x] SQL generator with validated JSON output, told the target SQL dialect (prompt sql-generator/1)
* [x] Executor: read-only connection, timeout, client-side row cap, error categories
* [x] POST /api/query with database_id, structured trace, metadata (model, prompt version)
* [x] Run against the real LLM: 11 questions on the full OWID data (see Completed Work)
* [x] LLM client retries transient provider errors (429/5xx): max 3 attempts, Retry-After honoured,
      fails fast when the provider asks for a wait over 8 s; attempts recorded in the trace

Later in this track
* [ ] MySQL adapter (+ CI against MySQL)
* [ ] Profile override file (descriptions, hidden tables, business rules)
* [ ] LLM-drafted column descriptions (marked as generated, editable)
* [ ] Generated example questions, kept only if their SQL executes

Milestone 3 — SQL safety validation

* [x] AST validation with sqlglot (backend/app/agent/sql_validator.py): single SELECT / set operation
      only, tables must be in the profile (scope-aware, so CTEs cannot shadow real tables), columns
      resolved against the profile, no system catalogs, no cross-database references
* [x] Reject INSERT/UPDATE/DELETE/MERGE/DROP/ALTER/CREATE/TRUNCATE/GRANT/COPY/SET, SELECT INTO,
      FOR UPDATE, data-modifying CTEs, multiple statements
* [x] Functions: sqlglot-modelled functions allowed; unmodelled ones only from a small allow-list;
      pg_*, lo_*, dblink, set_config, current_setting, ... always denied
* [x] Sensitive columns are unknown to the validator; SELECT * and whole-row references (`SELECT c`,
      `c::text`, `json_build_object('r', c)`) rejected, since they would read sensitive columns
* [x] Validation is a trace step; rejections return category "validation" + a machine-readable code
      and never reach the database. The SQL that runs is regenerated from the validated tree.
* [x] Executor sends SQL through a plain DB-API cursor (text() broke on ':name' inside literals)
* [x] Security tests: 47 rejection cases, 19 accepted queries incl. the 10 real LLM queries, whose
      regenerated SQL returns the same rows as the original on PostgreSQL

Milestone 4 — Read-only user + timeout + LIMIT enforcement

* [x] Read-only role and database-level timeout (done early in Milestone 1)
* [x] LIMIT enforcement by AST rewrite: added when missing, clamped to MAX_ROWS (also FETCH FIRST);
      non-literal LIMIT rejected. The executor's client-side row cap stays as a second guard.
* [x] Timeout surfaced as a trace event with retry for a cheaper query (done in Milestone 6)

Milestone 5 — Query planner

* [x] Structured plan returned with the SQL in the same LLM call (prompt sql-generator/2): intent,
      tables, metrics, filters, group_by, order_by, limit, assumptions. Size-limited, validated.
* [x] Clarification: the model asks a question (status "needs_clarification") only when no reading
      is a reasonable default; otherwise it answers and states its assumptions in the plan
* [x] Deterministic plan check against the validated SQL (tables, limit); mismatches recorded as
      plan_warnings in the trace, not blocking (the validated SQL is what runs)
* [x] Plan returned in the API response and its intent in the trace; tests for parsing, the
      SQL-or-question rule, the plan check and the clarification path
Milestone 6 — Automatic SQL repair/retry (max 2)

* [x] Repair loop in the controller: a repairable failure is fed back to the model (prompt
      sql-repair/1: failed SQL, reason code, error message, previous plan, targeted hint) at most
      MAX_RETRIES times; every repaired query is validated again
* [x] Repairable: validator rejections except NOT_SELECT / FORBIDDEN_OPERATION / MULTIPLE_STATEMENTS
      (unsafe intent is not retried); database errors timeout, syntax, undefined column/table/function,
      type mismatch, data errors (new category: PostgreSQL class 22, e.g. division by zero)
* [x] Timeout repair asks for a cheaper query; the loop stops early when the model repeats its SQL
* [x] Trace: sql_repair steps, attempt number on every step, retries on completion; retry_count in
      metadata; the last failed SQL and its plan are returned on error
* [x] Tests: repair after rejection / database error / division by zero / timeout, bounded retries,
      repeated SQL, unsafe SQL not retried, repair ending in clarification, retries disabled
Milestone 7 — Result validation (deterministic checks)

* [x] Checks on every executed result (backend/app/agent/result_checks.py): empty result, aggregate
      over nothing (one row of NULLs/zeros, e.g. COUNT = 0), ranking led by a NULL, NULL-only column,
      row limit reached (when the LIMIT was added or clamped), duplicate rows
* [x] Missing-value probes for empty results: each `column = 'text'` / `IN (...)` filter on a real
      table column (WHERE and JOIN conditions, CTEs and subqueries included) gets a one-row existence
      query, built from the syntax tree, validated and run read-only; max 3 per result. Only the
      model's own literal is echoed back, never database values
* [x] Repairable checks (missing value, NULL-led ranking) go through the Milestone 6 repair loop with
      targeted hints; the others are returned as `checks` for the answer step and the user
* [x] If a repair ends worse than an executed result (error, no SQL), that result is returned
* [x] result_validation trace step; tests: check rules, probes on PostgreSQL (joins, aliases, IN
      lists, CTEs, subqueries, cap), repair of a misspelled value and a NULL-led ranking, fallback
Milestone 8 — Natural-language answer generation

* [x] Answer step (backend/app/agent/answer.py, prompt answer/1): 1–3 sentences from the question,
      plan assumptions, result checks and up to 30 rows (long values truncated)
* [x] Deterministic grounding check: every number in the answer must come from the rows (rounding,
      thousands separators and 0–1 fractions as percentages allowed), the question or the row count;
      sums, ratios, unit conversions and wrong figures are rejected
* [x] Template answer (always grounded) when the check fails, the LLM call fails, ANSWER_MODE=template,
      or the database's sampling mode is `off` (rows never leave for such databases)
* [x] answer_source ("llm" | "template") in the response; answer_generation trace step with the
      reason for any fallback and the ungrounded numbers
* [ ] Follow-up: give the answer step column units (from column comments) so answers can say "Mt"
Milestone 9 — Chart generation

* [x] Deterministic chart choice (backend/app/agent/chart.py) from column kinds (temporal, measure,
      category, identifier) and values: single value -> stat tile; time -> line (one line per
      category, max 8); categories -> bar (horizontal when many or long labels, max 30); two
      measures -> scatter; otherwise none (the table always carries the result)
* [x] One value axis only: measures more than 10x apart in scale are not plotted together
* [x] The model's chart_suggestion is only a tie-breaker (bars for <= 6 time points, scatter for
      two measures per category); ChartSpec (type, x, y, series, label, orientation, reason) in the
      response, chart_selection trace step
* [x] Tests: column kinds, every form rule, limits, tie-breaks; checked on the 10 real LLM queries
      plus a multi-series trend and a GDP-vs-CO2 scatter on the full OWID data
Milestone 10 — Execution trace + structured logging + request IDs

* [x] Request IDs (backend/app/observability.py): X-Request-ID kept when it is a safe token
      ([A-Za-z0-9._-], max 64), otherwise generated; returned in the header (exposed via CORS) and in
      metadata.request_id of query results
* [x] JSON log lines (ts, level, logger, message, request_id, fields) for every request, every agent
      trace step (failures at WARNING) and every LLM call (model, HTTP status, attempts, duration)
* [x] Never logged: question text, SQL, result rows, answers, URLs, passwords, keys (safe_fields);
      LLM request/response bodies are never logged
* [x] Unexpected errors: generic 500 with the request ID; the stack trace goes to the log only
* [x] Tests: ID generation/propagation/validation, CORS exposure, 500 handling, JSON format, field
      filtering, and an end-to-end query whose logs share one request ID and contain none of the
      question, SQL, result values, database password or URL
Milestone 11 — Evaluation framework (50+ questions, result-based scoring, safety suite)

* [x] EVALUATION_PLAN.md rewritten for the yearly OWID data (categories, interpretation rules,
      scoring, metrics, how to run, LLM budget)
* [x] 73 questions (evaluation/questions.json): 10 each simple filtering, aggregation, ranking,
      time series, multi-condition; 5 joins, 5 ambiguous (clarify), 5 no-result (empty), 8 safety
* [x] Ground truth: hand-written SQL run on the pinned data (evaluation/expected.json, reviewed);
      records dataset commit and row counts; two questions accept a second defensible reading
* [x] Result-based scoring (evaluation/scoring.py): columns matched by value, row alignment,
      order only when asked, numeric tolerance and rounding; clarify / empty / refuse / blocked
* [x] Resumable runner (evaluation/run.py): JSONL per question, provider failures = not run, stops
      after 3 in a row, pacing, database row counts checked before and after, secrets scanned
* [x] Report (evaluation/report.py): all plan metrics, per category, PARTIAL when incomplete
* [x] Offline SQL safety suite: 28 adversarial statements through validator + database, no LLM
* [x] Tests: 51 (scoring rules, every ground truth scores as correct against itself, runner resume /
      quota stop / pacing / integrity, report)
* [x] Offline SQL safety suite run and recorded (2026-09-26, commit 250c86e): 28/28 blocked,
      0 safety violations, database unchanged
* [ ] Run the question suite with a real LLM and record it (blocked on quota)
Milestone 12 — React frontend (Vite + TS + Tailwind + Recharts)
  * Use the `frontend-design` plugin (Anthropic directory) and impeccable.style design guidance
Milestone 13 — Tests, Docker, README, Vercel deployment, polish

⸻

Completed Work

* Milestone 1 (first on AGMARKNET mandi prices, then reworked for OWID CO2 data).
  35 pipeline/database tests + 3 API tests pass. Full dataset loads in ~2 s.
* Milestone 2 verified end to end (2026-09-26) on local PostgreSQL 16 with the full OWID data:
  all 100 tests pass with the database suites enabled (35 pipeline + 65 backend; now 70 backend).
  11 hand-picked questions via POST /api/query, not an evaluation run: 11/11 returned results that
  match hand-written SQL, including the "no such data" question answered as unanswerable. 8 on
  gemini-3.8-flash; 3 on gemini-3.5-flash after the 3.8 free quota ran out.
  Observed: the model once omitted the required LIMIT (the executor's row cap still applied; the
  Milestone 4 AST rewrite will enforce it); the "average per capita" income-group question was
  answered from OWID's own aggregate rows, which is a reasonable reading but should become an eval
  case with explicit ground truth. SQL generation takes 3–16 s on the free tier; schema retrieval
  ~120 ms, mostly re-reflecting for the fingerprint check (could be cached for a short TTL).
* Milestone 3 (2026-09-26): 160 backend + 35 pipeline tests pass against PostgreSQL 16. Live check
  on gemini-3.5-flash: validated queries ran with the validation step taking 4–10 ms; a prompt
  injection asking to delete data was declined by the model (the validator is the backstop).
* Milestone 5 (2026-09-26): 172 backend + 35 pipeline tests pass. Live, 4 questions across
  gemini-3.5/3.6/3.7-flash (quota and 503s forced model switches): plans matched the SQL (no
  plan_warnings) for a ranking, a trend and a lookup; "Which country is the biggest polluter?" and
  "Show me the data for Georgia" were answered with stated assumptions (latest-year annual CO2; the
  country Georgia) rather than a clarification question. The clarification path is so far covered by
  tests only; Milestone 11's ambiguous-question category will measure it.
* Milestone 6 (2026-09-26): 184 backend + 35 pipeline tests pass. Live (gemini-3.6-flash): two
  division-prone questions were answered first time (the model guarded against zero itself), so the
  real repair step was exercised directly with two constructed failures: division by zero was
  repaired with NULLIF, an unknown column with real emissions columns; both repairs validated and
  returned correct rows.
* Milestone 7 (2026-09-26): 209 backend + 35 pipeline tests pass. Live (gemini-3.6-flash): the model
  hedged country names itself (ISO codes, ILIKE, 'Czech Republic'/'Czechia'), so no check fired and
  the new step passed cleanly. Directly: the probe flagged 'Ivory Coast' on the full data, and the real
  repair step turned it into ILIKE '%Ivoire%', returning Cote d'Ivoire's 2020 CO2 (11.019 Mt).
* Milestone 8 (2026-09-26): 235 backend + 35 pipeline tests pass. Live: gemini-3.6-flash answered
  "top 5 emitters in 2023" in grounded prose (all five figures from the rows, but without units); on
  gemini-3.8-flash a 429 on the answer call fell back to the template answer while the request still
  succeeded. The other 4 of 6 live requests failed with 429 (free-tier quota) at SQL generation.
* Milestone 9 (2026-09-26): 266 backend + 35 pipeline tests pass. No LLM needed: chart choice on 12
  real results from the full data gave horizontal bars for rankings, stat tiles for single values, a
  line for India's CO2 trend (growth columns left to the table: different scale), three lines for a
  3-country trend and a scatter for GDP vs CO2.
* Milestone 10 (2026-09-26): 279 backend + 35 pipeline tests pass. Live server: one JSON line per
  request with the caller's X-Request-ID kept; a real query that hit a Gemini 429 logged the LLM call
  (http_status 429, attempts 3), the failed step and the request, all under the same request ID.
* docker compose stack verified: postgres init creates schema + role, backend /api/health returns ok,
  seed service downloads, cleans and loads the data, sql_agent write attempts are denied.

⸻

Current Blockers

Milestone 11 needs LLM quota. Status on 2026-09-26: the environment's LLM_MODEL is gemini-3.5-flash
(the retired gemini-2.5-flash setting is fixed; the code default stays gemini-3.8-flash). A direct
call succeeds, but the free tier caps each model at about 20 requests per day (the 429 names
generate_content_free_tier_requests, limit 20) and 5 per minute, with frequent 503s; the day's quota
was used up by live checks. Each evaluation question can take up to 4 calls (SQL, 2 repairs, answer;
ANSWER_MODE=template saves one), so a 50+ question run needs billing on the key, batches over several
days, or another provider. Building the question set, ground truth and runner needs no LLM calls.

⸻

Important Decisions

* Dataset: Our World in Data CO2 & GHG emissions (CC BY 4.0) instead of AGMARKNET mandi prices.
  The official mandi sources (data.gov.in, AGMARKNET) were not reachable/downloadable in a reproducible way;
  OWID is real, citable and downloadable by script from a pinned commit with verified hashes.
* Aggregates (World, continents, income groups) are kept but classified via countries.entity_type so
  "countries" questions can exclude them; "(GCP)" duplicate regions are excluded.
* Security boundary is the database: sql_agent has SELECT on four tables only; read-only default and
  statement_timeout are set on the role and again per session. The SQL validator is a second layer.
* Query plan and SQL come from ONE LLM call, not a separate planner call: free-tier quota (5/min,
  ~20/day per model) and latency make a second call costly, and there is no evaluation yet showing it
  would help. Revisit with Milestone 11 results.
* SQL validator design: allow-list, not deny-list, wherever possible (statement type, tables from the
  profile, unmodelled functions). The executed SQL is regenerated from the checked syntax tree, so a
  parser difference between sqlglot and the database cannot smuggle in unchecked text. Rejection
  messages name the problem (for the upcoming repair loop) without listing hidden tables or columns.
* Seeding/ingestion use a separate owner account (ADMIN_DATABASE_URL); the API never gets it.
* psycopg 3 with plain SQL, no ORM: the schema is small and read-only for the app.
* Schema via idempotent SQL scripts instead of a migration tool (Alembic not needed yet).
* LLM: free-tier, OpenAI-compatible provider via httpx (no vendor SDK). Gemini recommended (reachable from
  the dev environment; Groq is blocked there). Swappable via LLM_BASE_URL / LLM_MODEL. Default model is
  gemini-3.8-flash: gemini-2.5-flash is no longer available to new keys (HTTP 404).
* Deployment target: Vercel (frontend + FastAPI serverless function) with a managed Postgres (e.g. Neon).
  Short-lived DB connections chosen with serverless in mind.
* Test fixture is an unmodified real extract of the OWID file; malformed cases are built in memory.
* Database-agnostic design: the agent works on any connected database. OWID is the built-in demo and the
  evaluation benchmark; arbitrary databases get automatic profiling but no verified ground truth.
* Databases are added via configuration and, only when ALLOW_UI_CONNECTIONS=true (local/self-hosted),
  via the UI. Never enabled on the public deployment (SSRF / credential-handling risk).
* Engines: PostgreSQL now, MySQL next. SQLAlchemy Core + a small per-engine adapter for what differs
  (timeouts, read-only enforcement, privilege checks, error mapping); sqlglot with the right dialect.
* Accounts we did not create are checked on connect; accounts that can modify data are refused.
* Value sampling is configurable per database: off | safe (default: numeric/date ranges and short
  categorical values, never free text or sensitive-looking columns) | full (adds short text examples).
  Sampled values are sent to the LLM provider; this is documented.

⸻

Notes for Next Session

Read this file and inspect the repository before continuing.
Local dev DB: see .env.example. Rebuild data: ingest_data → clean_data → seed_database (or `docker compose run --rm seed`). Integration tests need TEST_ADMIN_DATABASE_URL and TEST_SQL_AGENT_PASSWORD
(an empty, disposable database; the tests reset the cluster-wide sql_agent password).
In Claude Code on the web, .claude/hooks/session-start.sh does this automatically: installs the Python
dependencies, starts the local PostgreSQL cluster (down after every container restart), creates the
emissions_test database and owner role with fresh random passwords, and exports both variables. The
full OWID demo database is not loaded by the hook; seed it by hand when a live check needs it.
Run tests: `python -m pytest scripts/tests` and `cd backend && python -m pytest`.
