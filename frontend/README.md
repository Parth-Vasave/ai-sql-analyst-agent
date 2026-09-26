# Frontend

The single-page web app for AI SQL Analyst: ask a question, read the answer, and inspect the plan
that produced it (SQL, validation, execution, result checks, timings).

Vite, React, TypeScript (strict), Tailwind CSS and Recharts. The page reads the FastAPI backend
under `/api`; in development the Vite server forwards `/api` to `http://127.0.0.1:8000`
(override with `API_URL`), and a production build can point elsewhere with `VITE_API_BASE`.

```bash
npm install
npm run dev        # http://localhost:5173 (start the backend on :8000 first)
npm test           # vitest: plan model, formatting, units, and the page's states with a mocked API
npm run typecheck
npm run build      # dist/
```

Design context lives outside the code: product facts in `../PRODUCT.md`, the page's design contract
in `../.impeccable/surfaces/`, and the visual system in `../DESIGN.md`.
