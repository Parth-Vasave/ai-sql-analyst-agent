---
name: AI SQL Analyst
description: A live database console — the transcript of a read-only session, not a chat app or a dashboard.
colors:
  paper: "#faf9f7"
  paper-raised: "#f1efec"
  ink: "#16181c"
  ink-dim: "#5b6169"
  ink-faint: "#666c74"
  line: "#dbdcdc"
  accent: "#9a5a1f"
  accent-soft: "#f1e3d1"
  chart-steel-blue: "#3b6e8c"
  chart-violet: "#6e5a9c"
  chart-teal-green: "#3b8c6e"
  chart-wine: "#8c3b6e"
  chart-olive: "#6e8c3b"
  chart-indigo: "#3b4f8c"
  chart-purple: "#7a3b8c"
  chart-cyan-teal: "#3b8c9e"
typography:
  display:
    fontFamily: "'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace"
    fontSize: "1.875rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "normal"
  body-console:
    fontFamily: "'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.6
  body-prose:
    fontFamily: "'IBM Plex Sans', 'Segoe UI', ui-sans-serif, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace"
    fontSize: "11px"
    fontWeight: 400
    letterSpacing: "normal"
rounded:
  none: "0px"
  full: "9999px"
spacing:
  xs: "0.375rem"
  sm: "0.5rem"
  md: "1rem"
  lg: "1.5rem"
components:
  prompt-caret:
    textColor: "{colors.accent}"
    typography: "{typography.body-console}"
  step-label:
    textColor: "{colors.accent}"
    typography: "{typography.body-console}"
  check-chip-pass:
    textColor: "{colors.ink-dim}"
    rounded: "{rounded.none}"
    padding: "0.125rem 0.375rem"
  check-chip-warning:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent}"
    rounded: "{rounded.none}"
    padding: "0.125rem 0.375rem"
  ghost-button:
    textColor: "{colors.ink-dim}"
    rounded: "{rounded.none}"
    padding: "0.25rem 0.5rem"
  code-block:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0.375rem 0.5rem"
---

# Design System: AI SQL Analyst

## Overview

**Creative North Star: "The Console."**

This is one long-lived database session rendered as a scrolling transcript, not a chat app skinned as a product and not a form-then-card dashboard. The session header reads like a connection string (`database · role · status`); every question becomes a prompt line; every answer is the backend's own steps rendered in order — plan, SQL, execution trace, checks, result grid, chart, grounded prose — in the same rhythm a real `psql`/`less` session would print them. Nothing is invented to look friendlier than the backend actually is: what you see is what the API returned, in the order it returned it.

The palette is two-tone and near-monochrome on purpose (near-black ink on near-white paper, inverted in dark mode) with exactly one reserved color. Hierarchy inside the dense transcript zones comes from type size, weight, and monospace-vs-sans alone — never from colored chips-as-decoration, card boxes, or drop shadows. The build stays a hair's-width from a hacker-terminal cliché and deliberately steps back from it: no glow, no scanlines, no green-on-black default; the resting page is closer to a clean pager than a cyberpunk shell.

Confirmed visual rejections, carried from the build itself: no soft SaaS-card shadows, no gradients, no rounded "friendly" corners (the one exception is the circular status dot), no filled/colored primary button anywhere in the shipped surface — every actionable control is a hairline-bordered ghost button, a native input, or a plain link.

**Key Characteristics:**
- Monospace-first transcript, humanist sans reserved for the one piece of prose (the grounded answer sentence) and empty-state copy.
- One reserved accent, confined to the console's own operator markup and the held/alert state — never to routine data or routine status.
- Flat, bordered, hairline-ruled; no shadows, no card elevation.
- Square corners everywhere except the circular status dot.
- Density-led hierarchy: size and weight carry meaning, not boxes or color.

## Colors

Near-monochrome ink-on-paper in both themes, with a single reserved warm accent that never colors anything routine.

### Primary
- **Reserved Amber** (`#9a5a1f` light / `#d99a4e` dark): the system's only chromatic color. It appears in exactly two families of place, and nowhere else: (1) the console's own fixed operator markup — the prompt caret (`>`, `>_`), the bracketed step labels (`[plan]`, `[sql]`, `[validate]`, `[check]`, `[clarify]`, `[unanswerable]`, `[error]`), and the blinking "running" cursor — the console's native syntax-highlighting device, present on every screen whether or not anything is wrong; and (2) the held/alert state — a failed trace segment, a warning-severity check chip, the `retries` counter, the error banner, and a `rejected` (non-read-only) database connection. It is darkened from the "true" amber so it clears 4.5:1 as body text on paper.
- **Reserved Amber Soft** (`#f1e3d1` light / `#3a2c1a` dark): the accent's low-chroma background wash — selection highlight, the warning check-chip fill, the error banner's tint, the failed-segment fill on the trace graticule. Always paired with the accent, never used alone.

### Neutral
- **Paper** (`#faf9f7` light / `#111215` dark): the page ground.
- **Paper Raised** (`#f1efec` light / `#191a1e` dark): the one tonal step up from paper — table headers, the SQL code block, the row-count footer bar, the resting fill of trace-strip segments. This is the system's only elevation device; it is never paired with a shadow.
- **Ink** (`#16181c` light / `#e7e8ea` dark): primary text.
- **Ink Dim** (`#5b6169` light / `#9a9fa6` dark): secondary text — assumptions, meta labels, passing check chips, the "ready" status dot. Tuned to clear 4.5:1 on paper.
- **Ink Faint** (`#666c74` light / `#7d838b` dark): tertiary text and decorative marks — separator dots, row/timing footers, the "unavailable" status dot, placeholder text. Goes lighter than the 4.5:1 floor by design; reserved for the least load-bearing marks.
- **Line** (`#dbdcdc` light / `#2b2d31` dark): the only border color. Every rule, table divider, block outline, and header/footer boundary is this hairline, 1px.

### Named Rules
**The Reserved Accent Rule.** The accent means one of two things, always: this is the console's own markup, or this is the thing you need to notice. It is never used to differentiate routine data or routine status — a healthy connection, a passing check, and a chart series are never accent-colored. This is a corrected rule, not just a stated one: an early build leaked the accent into the chart palette and into the "ready" state of the connection-status dot, and both were pulled back out during finish review (see Do's and Don'ts).

## Typography

**Body Font (console):** JetBrains Mono, with `ui-monospace, Menlo, Consolas, monospace` fallback
**Body Font (prose):** IBM Plex Sans, with `Segoe UI, ui-sans-serif, sans-serif` fallback

**Character:** A dense, information-forward monospace carries almost the entire interface — plans, SQL, traces, checks, tables, labels, the prompt itself; the humanist sans appears only where the backend hands back a written sentence (the grounded answer, the intro's explanatory prose, empty states). The pairing itself is the "the machine talks in one voice, the answer talks in another" device.

### Hierarchy
(Bumped one step site-wide 2026-09-28 for readability, from the shipped build's 11–14px scale;
relative proportions between tiers are unchanged.)
- **Display** (400, 32px, mono, tabular-nums): the single number in a "stat" chart response — the only oversized type on the page, reserved for exactly one component.
- **Body — console** (400, 14px, monospace, 1.6 line-height): the dominant register — prompt lines, plan/SQL/check text, trace labels, table cells, session header. This is the type the whole app is written in.
- **Body — prose** (400, 15px, sans, 1.6 line-height, max 36rem measure): the grounded natural-language answer and the intro block's explanatory paragraph. The only sans-serif text in the system.
- **Label** (400, 12–13.5px, monospace): request IDs, timings, row counts, axis ticks, the character counter, the footer disclaimer. The smallest, least load-bearing tier.

### Named Rules
**The Density-Led Hierarchy Rule.** Inside the transcript, hierarchy is carried by type size, weight, and monospace-vs-sans alone — never by colored chips-as-decoration, card boxes, or drop shadows. A validation-check chip is a real state indicator (pass/warning), not a decorative label.

## Layout

A single centered column (`max-w-4xl`, 56rem) holds the whole session at every width tested (390px mobile through 1600px desktop); the build does not introduce a second column or a dashboard grid at wide viewports; it just widens the margins. The page is a fixed three-part vertical stack, not a scrolling document: a bordered session header at the top, a scrolling transcript in the middle (`flex-1 overflow-y-auto`), and a fixed prompt form plus a one-line footer at the bottom — the same shape as a terminal with a status bar. Each answer block is bordered on its bottom edge only (`border-b border-line`) rather than boxed, so the transcript reads as continuous scrollback, not a stack of cards. Responsive change is disclosure, not rearrangement: at the `sm` breakpoint (640px) the database's dialect/mode string and the "ready"/"rejected" status word hide, and the theme toggle's label shortens (`:theme dark` → `:set theme dark`) — the structure itself does not change. Prose blocks (the answer sentence, assumptions, check detail) cap at a 34–36rem measure inside the wider column, so line length stays readable even though the transcript column itself is much wider.

## Elevation & Depth

Flat. There are no shadows anywhere in the shipped build — not on hover, not on the header, not on the chart panel, not even the one interactive dropdown or the results table. Depth is conveyed by a single tonal step (`paper` → `paper-raised`) for surfaces that need to read as slightly recessed or grouped — table headers, the SQL code block, the row-count footer bar, the resting fill of a trace segment — plus hairline borders (`line`, 1px) to separate every other region. A tooltip explicitly sets `shadow-none` rather than omitting a shadow by accident.

### Named Rules
**The Flat-By-Default Rule.** Nothing lifts. There is no hover-elevate, no focus-elevate, no card-shadow anywhere in the system. The one state change that isn't color or a hairline is the trace strip's redo overlay — a second, dimmer lane appearing under a repaired step — and even that is tonal, not a shadow.

## Shapes

Square corners everywhere: buttons, the database `<select>`, code blocks, table borders, chart panels, and check chips are all explicitly `rounded-none`. The single exception is the connection-status dot, a small (7px) filled circle — the one deliberately soft shape in the system, reserved for that one indicator. Borders are uniformly 1px hairlines in `line`; the trace strip and the results table are the only places a border doubles as a measuring device (the graticule's divisions, the table's row/column rules) rather than a container edge.

## Components

### Buttons
- **Shape:** square corners (0px radius), always.
- **Primary:** there is no filled/colored primary button anywhere in the shipped surface. The closest equivalent — the theme toggle and the error banner's retry button — are hairline-bordered ghost buttons: transparent background, `border-line`, `ink-dim` text, padding roughly `0.25rem 0.5rem`.
- **Hover / Focus:** hover darkens the border to `ink-faint` and the text to `ink`; there is no background change. Focus is a uniform 2px solid accent outline with 2px offset (`:focus-visible`), applied globally, not per-component.
- **Disabled:** reduced opacity plus `cursor-not-allowed` (seen on the retry button during its cooldown).

### Chips
- **Style:** check-result chips are the only chip in the system. Passing/skipped checks: hairline `border-line`, `ink-dim` text, a hollow-circle glyph (`○`). Warning-severity checks: `border-accent`, `text-accent`, a filled-circle glyph (`●`), and the accent-soft background on hover.
- **State:** each chip is a real toggle — clicking one expands an inline detail line (the failure message, the affected column, whether it was fed back for repair) directly beneath the chip row; it is not decorative.

### Cards / Containers
- **Corner Style:** square (0px radius) on every container — the SQL block, the results table, the chart panel.
- **Background:** `paper` at rest; `paper-raised` for the SQL block, table header, and footer bar.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Border:** 1px hairline in `line` around every block; the trace strip additionally borders in `accent` around any failed segment.
- **Internal Padding:** tight and consistent — roughly `0.375rem–0.5rem` for code/table cells, `1rem` for the chart panel.

### Inputs / Fields
- **Style:** the question input and the database `<select>` are both borderless and backgroundless, sitting directly in the console's flow (`border-none bg-transparent`), distinguished only by the monospace prompt caret beside them and, for the select, an underline decoration.
- **Focus:** the select gets a 1px accent ring; the text input relies on the same global `:focus-visible` outline treatment as everything else. No glow, no border-color shift beyond that.
- **Error / Disabled:** disabled state sets a contextual placeholder (e.g. "this database account is not read-only; queries are disabled" or "waiting on the previous question…") rather than a separate error style on the field itself.

### Navigation
- There is no persistent nav bar beyond the session header, which behaves like a connection string: `>_ ai-sql-analyst · <database> (<dialect>, read-only, sampling: <mode>) ● <status>`, plain-ink at rest, with the theme-toggle ghost button as its only other control. There is no active/hover navigation state to speak of — the header does not link anywhere; it only reports and lets you switch the connected database.

### Signature Component: The Trace Strip
The execution trace renders as a fixed-division timing strip — a literal ruled scale (bordered graticule, `flex` segments sized by proportional `flex-grow`) that each backend step's duration is plotted against, in `paper-raised` at rest and accent-outlined where a step failed. A second, dimmer overlay lane beneath it marks exactly the spans that were redone after a repair, so a retry shows up in the measurement itself, not only in a text label. Text labels beneath the strip name each step and its duration in mono 11px, going accent-colored only for a failed step's label and for the `retries` count.

## Do's and Don'ts

### Do:
- **Do** keep the accent to its two reserved families: the console's own operator markup (prompt caret, bracketed step labels, the running cursor) and the held/alert state (failed steps, warnings, errors, retries, a rejected connection). Nothing else earns the color.
- **Do** use `paper-raised` plus a hairline border for anything that needs to read as grouped or recessed; never reach for a shadow.
- **Do** keep chart series and any future data-classification color out of the amber/orange/red hue range — the qualitative palette (steel blue, violet, teal green, wine, olive, indigo, purple, cyan-teal) exists specifically so data never reads as an alert.
- **Do** report a healthy/normal state in plain ink (`ink-dim`), not a second hue — "ready" is the unremarkable case.
- **Do** keep corners square; the status dot's circle is the one named exception, not a precedent for rounding other UI.

### Don't:
- **Don't** color a chart series, a passing check, or a "ready"/healthy status with the accent — both a chart-palette leak and a status-dot leak into the accent were found and corrected during finish review; treat that correction as settled, not as a precedent to loosen.
- **Don't** add a shadow anywhere, including on hover or focus — this system's only elevation device is the one tonal step from `paper` to `paper-raised`.
- **Don't** introduce a filled/colored primary button. The shipped system has none; every control is a ghost button, a native form control, or a plain underlined link.
- **Don't** let the resting page slide toward a hacker-terminal cliché (no glow, no scanlines, no green-on-black default) even though the console metaphor and the monospace-first type would otherwise invite it.
