---
version: 1
slug: "frontend"
primary_target: "frontend"
related_targets: []
---

## Scope & mode

New surface: the whole frontend (single page app, Vite + React + TS + Tailwind + Recharts),
consuming the existing FastAPI backend. Mode: Operate (a task tool: ask a question, read the
answer and its safety trail), with a brief moment of Persuade at first load for the visitor
evaluating the engineering rather than asking a question.

## Audience, job, task, proof, constraints

- Audience A: someone asking a real question against a connected database (starts with the
  bundled OWID CO2/GHG demo) and reading the answer, chart, and grounding.
- Audience B: someone evaluating the engineering (GitHub visitor, recruiter, collaborator) who
  will read the same page as evidence the safety claims are real, not marketing.
- Job/task: type a question in plain language; see the resolved plan and assumptions; see the
  generated SQL; see execution + validation + result-check trace steps with real timings; see the
  chart and grounded answer; ask a follow-up.
- Proof/content: the backend already returns everything needed (plan, SQL, trace steps with
  durations/retry counts, checks, column_units, chart spec, answer_source, request_id). No content
  needs to be invented; the OWID dataset citation is real and citable.
- Constraints: never fabricate evaluation numbers (none exist yet beyond the offline safety suite);
  no invented GitHub stars/license/testimonials; must present every real backend error state
  (rate limited, provider error, validation rejection, timeout, unreachable API, no LLM configured,
  clarification needed, unanswerable) with its own recovery; read-only messaging must stay accurate.

## Chosen direction & memorable moment

**The Console.** The page is one long-lived database session, not a chat app and not a form-then-
card layout. A fixed session header (connection string style: `database · role · status`) sits above
a scrolling transcript. Each question becomes a prompt line (`>`), and the answer that follows is a
real console rendering of the backend's own steps: `[plan]`, `[sql]`, `[check]`, then a result grid
with column types and a row-count/timing footer (psql's own convention), then the grounded prose
answer, then the chart (rendered inline, still inside the transcript rhythm, not a separate
dashboard widget). Follow-up questions append further down the same transcript, exactly like a
real session's scrollback.

Raised from the direction round (each is a real device in the build, not decoration):
- **Measured trace strip** (from an oscilloscope's graticule): the execution trace renders as a
  fixed-division timing strip under each answer — a literal ruled scale the step durations are
  plotted against, not a soft progress bar. Retries and timeouts show as a second overlaid trace
  in a dimmer tone on the same graticule.
- **Held alert state** (from a live gate/status board): a step that fails, retries, or triggers a
  repair holds a single reserved alert color until the person has seen it (never auto-dismisses on
  its own timer); a step that is merely running pulses only the cursor, not the whole row.
- **Two-tone data density** (from strict black/white data-art restraint): the base palette is
  near-black text on near-white ground (or the reverse in dark mode), one signal accent reserved
  for the alert state above and nothing else — no soft grey SaaS-card shadows, no gradients.
  Hairline rules only; monospace for anything that is data (SQL, results, timings, request IDs),
  a plain humanist sans for prose (the answer sentence, labels, empty states).
  This must not slide into a neon hacker-terminal cliché: no glow, no scanlines, no green-on-black
  default — the accent is used once, deliberately, and the resting page reads closer to a clean
  `psql`/`less` pager than a cyberpunk terminal.
- **Density-led hierarchy** (from pure type-scale hierarchy): in the dense transcript zones,
  hierarchy comes from type size/weight and monospace vs. sans alone, never from boxes, colored
  chips-as-decoration, or drop shadows. A validation-check chip is a real state indicator (pass/
  fail/warning), not a decorative label.
- **Traceable state** (from a tension/counterforce structure): clicking a failed or retried check
  expands in place to show what caused it (the prior SQL attempt, the reason code, the repair
  hint) — the trace is inspectable, not just displayed.

## First viewport

On load: the session header (idle, no live database connected yet is impossible here — a default
demo database is selected) directly above an empty transcript holding just the prompt line and a
short, real explanation of what will happen when a question is asked (not a hero image, not a
tagline) — e.g. the previous steps a question goes through, written plainly, so a first-time
visitor understands the mechanism before they've typed anything. No gradient hero, no illustration,
no marketing headline; the "hero" is the mechanism, stated in the console's own voice, at the
console's own type scale. Below the fold on first load: nothing manufactured — the transcript grows
only as real answers arrive.

## Form

Direction 6 of 7 in my own ranked list (psql/pgAdmin console), assigned by the direction round;
seed key `c7118e12`. No pick-card override taken — the assignment was also genuinely the strongest
fit, so it leads without a separate pick card.

## Unresolved decisions

- Exact type pairing (a monospace + a humanist sans, both chosen deliberately, not system defaults)
  and the single accent hue are decided while building, guided by the palette/type sections of
  new-work.md, not pinned here.
- Dark mode is required (prefers-color-scheme) but which mode is "default" vs "alternate" is
  decided during build based on which reads more like a real console.
- Whether the chart renders inside the monospace transcript rhythm or breaks briefly into a plain
  sans/measured layout for legibility is a build-time call, resolved against the craft-floor
  reference.

## Finish

unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict,
DESIGN.md, and every shipping raster carrying its provenance.
