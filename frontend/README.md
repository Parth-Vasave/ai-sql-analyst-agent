# AI SQL Analyst — frontend

The console UI for the AI SQL Analyst backend: ask a question, watch it become a validated,
read-only SQL query, and read the result as a live database session — plan, SQL, an execution
trace, deterministic checks, a chart, and a grounded answer, in that order, exactly as the
backend returns them.

See `../DESIGN.md` for the design system and `../PRODUCT.md` for product context.

## Develop

```bash
npm install
npm run dev        # http://localhost:5173, proxies /api to http://localhost:8000
```

The dev server expects the backend (see the repository root's `docker-compose.yml`) running at
`http://localhost:8000`. Override the proxy target with `VITE_API_PROXY_TARGET`, or point a built
app at a different origin with `VITE_API_BASE_URL` (see `.env.example`).

## Check

```bash
npm run typecheck
npm test
npm run build
```
