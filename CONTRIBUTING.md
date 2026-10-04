# Contributing

Issues and pull requests are welcome. For a larger change, open an issue first so we can agree on
the approach.

## Setup

Follow the [Quick start](README.md#quick-start) in the README. Database-backed tests need a
disposable PostgreSQL database; see [Testing and quality](README.md#testing-and-quality).
Never point the tests at a real cluster: they reset the `sql_agent` password.

## Before opening a pull request

Run the same checks as CI:

```bash
python -m pytest scripts/tests
cd backend && python -m pytest
python -m pytest evaluation/tests
ruff check . && ruff format --check . && mypy
cd frontend && npm run lint && npm run typecheck && npm test
```

## Ground rules

- **SQL safety stays deterministic.** Generated SQL must pass the validator before it runs. Do not
  make a prompt the only protection against anything.
- **Do not weaken tests to make a change pass.** If a test is wrong, explain why in the PR.
- **Add tests with the change**, especially for the validator: a new rule needs both an accepted
  and a rejected case.
- **Evaluation numbers come from runs.** If a change affects prompts, the validator or the model,
  re-run the suite and record the result in `EVALUATION_PLAN.md`. Never edit numbers by hand.
- **No secrets** in code, logs, fixtures or commits. Configuration goes in `.env.example`.

## Security issues

Report them privately; see [SECURITY.md](SECURITY.md).
