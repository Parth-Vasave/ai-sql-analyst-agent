# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Inferred from the brief (the owner skipped the interview; confirm or correct): developers and
technical reviewers evaluating an open-source project — arriving from the GitHub repository, a
portfolio or a code review. Their job is to try a question on the demo data and see exactly how the
answer was produced and why it is safe, then decide whether the code is worth reading or reusing.
Analysts querying their own databases are a secondary audience (local/self-hosted use).

## Product Purpose

AI SQL Analyst answers natural-language questions about a relational database by generating SQL
with an LLM, validating it deterministically, running it on a read-only account, checking the
result, and returning a grounded answer with a table and a chart. Success for the site: a visitor
asks a question, gets a correct answer, and can inspect every step (plan, SQL, validation, result
checks, trace) without leaving the page.

## Positioning

An open-source project, presented as one — not a product with a sales pitch (owner's instruction).
Its distinguishing mechanism is that the LLM is never trusted: generated SQL passes an AST
validator and runs on a read-only database account; failures go through a bounded repair loop;
numbers in answers are checked against the returned rows; everything is observable in a structured
trace, and accuracy is measured by a result-based evaluation suite.

## Operating Context

- Built-in demo database: Our World in Data CO2 and greenhouse-gas emissions, yearly, 1750–2024,
  countries, regions and income groups (CC BY 4.0, pinned commit; see data/README.md).
- Backend: FastAPI (`POST /api/query`, `GET /api/databases`, `GET /api/databases/{id}/profile`,
  `GET /api/health`). Each query response carries status, answer and its source (llm | template),
  plan, SQL, columns and rows, result checks, chart spec, error, trace and metadata (model, prompt
  version, retry count, request id).
- Answers take several seconds (LLM latency; free-tier providers also rate-limit), so waiting and
  provider errors are normal states, not edge cases.
- Deployment target: Vercel (frontend) with the API as a serverless function and managed Postgres.

## Stack

Vite + React + TypeScript (strict) + Tailwind CSS + Recharts, as planned in TODO.md (Milestone 12);
frontend in `frontend/`, calling the FastAPI backend.

## Capabilities and Constraints

- Statuses to present: success, needs_clarification, unanswerable, error (with category and code).
- Chart spec types: stat, bar (vertical/horizontal), line (optional series), scatter, none.
- Adding databases from the UI exists only when ALLOW_UI_CONNECTIONS=true (local use); the public
  site shows the configured databases only.
- Never show secrets or connection URLs (the API never returns them).
- No accuracy figures may be shown until the evaluation suite has actually been run
  (EVALUATION_PLAN.md). As of 2026-09-26 only the offline SQL safety suite has run (28/28 blocked).

## Brand Commitments

- Name: AI SQL Analyst. Open-source project; the repository is the source of truth.
- Voice: plain, technical, factual, like a good README. No marketing claims.

## Evidence on Hand

- Real demo data and example questions (evaluation/questions.json).
- Recorded evaluation: offline SQL safety suite, 28/28 adversarial statements blocked (commit 250c86e).
- Absent: question-suite accuracy, users, testimonials, benchmarks, logos. Do not fabricate them.

## Product Principles

1. Show the work: every answer comes with the SQL, plan, checks and trace that produced it.
2. Honest by construction: only numbers the database returned; only metrics a run produced.
3. Safety is visible: the read-only account and the validator are explained where they act.
4. Documentation over persuasion: explain what it is and how it works; let the demo convince.

## Accessibility & Inclusion

No product-specific standard was set; the web quality floor applies (keyboard use, visible focus,
contrast, reduced motion, table view for every chart).
