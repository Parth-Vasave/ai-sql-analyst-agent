---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: []
---

Scope: the single public page of the web app (frontend/src/App.tsx). Mode: Operate.
Audience and job: developers evaluating the open-source project (inferred; owner skipped the interview). Ask a question of the demo database, read the answer, and inspect how it was produced and why it is safe.
Proof and content: live API responses only; no invented metrics. Evaluation record shown as recorded (offline SQL safety suite 28/28; question suite not run yet).
Constraints: open-source project, not a product: README-like framing, no marketing. Data attribution for OWID (CC BY 4.0) is required. No license claim (the repository has no LICENSE file).

## Direction contract

THESIS: The page is the EXPLAIN ANALYZE output of a question: the answer is the root node, and the steps that produced it hang beneath it with real timings. It refuses the AI-chat page (centered prompt, bubbles, sparkles).
OWN-WORLD: A query-plan visualizer: indented node rows joined by elbow connectors, actual-time columns in tabular numerals, horizontal time bars on a single blue ramp, nodes that expand in place. Cool light ground, white panels, hairline rules, plan-blue accent for actions and selection only, status as icon plus label.
STORY: The visitor reads the answer, sees at a glance where the time went and that the SQL was validated and run read-only, opens the node that interests them (SQL, plan, checks), and trusts the result because the work is shown.
FIRST VIEWPORT: README-style project header (name, one sentence, links) at small scale; below it the database picker, question field and Run button with example questions; then the plan tree filling the rest of the viewport: idle, it is the plan without timings, each node with its one-line job.
FORM: Database EXPLAIN plan tree, candidate 7 of 7 on the ordered list; seed key f8b3cdf9 (degraded roll, no challengers).
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
