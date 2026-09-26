---
name: AI SQL Analyst
description: A question answered as a query plan; the answer is the root node and the steps that produced it hang beneath it with real timings.
colors:
  plan-blue: "#1c5cab"
  plan-blue-deep: "#184f95"
  plan-blue-wash: "#e3edfb"
  cool-ground: "#f3f5f7"
  panel-white: "#ffffff"
  well-grey: "#edf1f5"
  ink: "#1a1e24"
  ink-2: "#505a66"
  ink-3: "#626b76"
  hairline: "#d5dbe2"
  hairline-strong: "#b8c1cc"
  status-good: "#0f7a2e"
  status-warn: "#8a5a00"
  status-bad: "#b3261e"
  bad-wash: "#fbeceb"
  warn-wash: "#fbf2df"
  series-1: "#2a78d6"
  series-2: "#eb6834"
  series-3: "#1baf7a"
  series-4: "#eda100"
  series-5: "#e87ba4"
  series-6: "#008300"
  series-7: "#4a3aa7"
  series-8: "#e34948"
  ramp-250: "#86b6ef"
  ramp-400: "#3987e5"
  ramp-550: "#1c5cab"
typography:
  display:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: "2.25rem"
    letterSpacing: "-0.01em"
    fontFeature: "tnum"
  headline:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.4375rem"
    fontWeight: 600
    lineHeight: "2rem"
    letterSpacing: "-0.01em"
  answer:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.1875rem"
    fontWeight: 400
    lineHeight: 1.625
  title:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: "1.625rem"
  body:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: "1.625rem"
  body-sm:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: "1.375rem"
  label:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: "1.25rem"
  code:
    fontFamily: "Source Code Pro, ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.625
rounded:
  sm: "3px"
  md: "5px"
  full: "9999px"
spacing:
  indent-sm: "1rem"
  indent: "1.25rem"
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.plan-blue}"
    textColor: "{colors.panel-white}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "10px 20px"
  button-primary-hover:
    backgroundColor: "{colors.plan-blue-deep}"
    textColor: "{colors.panel-white}"
  button-primary-disabled:
    backgroundColor: "{colors.hairline-strong}"
    textColor: "{colors.panel-white}"
  chip-example:
    backgroundColor: "{colors.panel-white}"
    textColor: "{colors.ink-2}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "4px 10px"
  chip-example-hover:
    backgroundColor: "{colors.panel-white}"
    textColor: "{colors.plan-blue}"
  input-question:
    backgroundColor: "{colors.panel-white}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
  select-database:
    backgroundColor: "{colors.panel-white}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "6px 32px 6px 10px"
  panel-plan:
    backgroundColor: "{colors.panel-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
  callout-info:
    backgroundColor: "{colors.well-grey}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "10px 14px"
  callout-warn:
    backgroundColor: "{colors.warn-wash}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "10px 14px"
  callout-bad:
    backgroundColor: "{colors.bad-wash}"
    textColor: "{colors.status-bad}"
    rounded: "{rounded.sm}"
    padding: "10px 14px"
  sql-block:
    backgroundColor: "{colors.well-grey}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
  table-header:
    backgroundColor: "{colors.well-grey}"
    textColor: "{colors.ink-2}"
    typography: "{typography.code}"
    padding: "6px 12px"
  time-bar:
    backgroundColor: "{colors.well-grey}"
    rounded: "{rounded.full}"
    height: "6px"
---

# Design System: AI SQL Analyst

## Overview

**Creative North Star: "The Annotated Query Plan"**

The interface reads like `EXPLAIN ANALYZE` output rendered with care: a question becomes a plan tree whose root node is the answer, and every step that produced it hangs beneath, indented one column deeper, joined by elbow connectors, with its actual time in tabular numerals and a thin horizontal bar showing its share of the total. Nodes expand in place to reveal the SQL, the query plan, the validator's verdict and the checks. It is a technical document you can open up, not a chat.

The world is light only, chosen for its use scene: read in daylight, next to a code editor, by developers checking how an answer was made. A cool grey ground carries white panels outlined by hairline rules; a second, slightly bluer grey (the well) marks machine material such as SQL, table headers and loading placeholders. Colour is restrained to one plan-blue accent for actions and selection, a status triad for outcomes, and a validated data-viz palette that appears only inside charts and time bars. Density is that of a good README: compact rows, generous line height, one column no wider than 64rem.

Motion exists only to report state: a chevron turns when a node opens, time bars grow once when a result lands, placeholders pulse while the plan runs. Reduced-motion preferences collapse all of it.

**Key Characteristics:**
- Plan-tree structure: indented rows, elbow connectors, a vertical spine, status icon column, time column, share-of-total bar column.
- Light theme only; cool grey ground, white panels, hairline borders, no shadows.
- Public Sans for all interface text; Source Code Pro only for SQL, identifiers and ids.
- One accent (plan-blue) for actions and selection; status is always an icon plus text, never colour alone.
- Fixed rem type scale (ratio about 1.2), tabular numerals for every measured value.
- Charts follow the data-viz method: fixed palette order, one value axis, a table twin, units from the database's column comments.

## Colors

A cool, near-monochrome slate world with a single saturated blue doing all the pointing; everything else colourful is data.

### Primary
- **Plan Blue** (`plan-blue`): the only interactive colour. The Ask button, links, focus rings, the text caret, hovered node names and example chips, the selected-text wash. It is also the deepest step of the time-bar ramp, so "where the time went" and "what you can act on" share one hue family.
- **Plan Blue Deep** (`plan-blue-deep`): hover state of the primary button only.
- **Plan Blue Wash** (`plan-blue-wash`): text selection background.

### Neutral
- **Cool Ground** (`cool-ground`): page background behind all panels.
- **Panel White** (`panel-white`): header, footer, plan panel, form fields, example chips, table body.
- **Well Grey** (`well-grey`): the second neutral layer for machine material: SQL blocks, table header row, time-bar tracks, info callouts, loading placeholders, chart hover cursor.
- **Ink** (`ink`): primary text, answers, SQL.
- **Ink 2** (`ink-2`): secondary text: node summaries, captions, body copy in callouts and footer, table header labels.
- **Ink 3** (`ink-3`): tertiary text that still passes 4.5:1 on ground, well and white: hints, fact labels, axis ticks, units, null cells, "attempt n" tags, inactive chevrons.
- **Hairline** (`hairline`): panel borders, section dividers, table row rules, chart grid and axis lines.
- **Hairline Strong** (`hairline-strong`): field borders, tree connectors and spine, the pending-status ring, disabled button fill.

### Status
- **Good** (`status-good`): success check icon.
- **Warn** (`status-warn`) on **Warn Wash** (`warn-wash`): result-check warnings and warning callouts.
- **Bad** (`status-bad`) on **Bad Wash** (`bad-wash`): failed node icon, name and summary; failed time-bar segments; error callouts and inline error text.

### Data (charts and time bars only)
- **Series 1 to 8** (`series-1` … `series-8`): the validated categorical palette, assigned to series strictly in slot order (blue, orange, green, amber, pink, deep green, violet, red). A single-series chart is always Series 1.
- **Time Ramp** (`ramp-250`, `ramp-400`, `ramp-550`): a three-step sequential blue ramp for time bars: under 10% of total is the lightest, 10 to 50% the middle, over 50% the deepest.

### Named Rules
**The One Pointer Rule.** Plan Blue marks what you can act on or what is selected, nothing else. Headings, icons and decoration never borrow it.

**The Data Owns Its Colours Rule.** The series palette and the time ramp appear only in charts and time bars. Interface chrome never uses a series colour.

**The Icon Plus Words Rule.** Status is carried by a distinct icon shape (check, alert, minus, empty ring) plus the node's text; colour reinforces, never carries alone.

## Typography

**Body Font:** Public Sans (with ui-sans-serif, system-ui)
**Mono Font:** Source Code Pro (with ui-monospace, SFMono-Regular, Menlo)

**Character:** A plain, civic grotesque for everything a person reads, paired with a quiet monospace reserved for what a machine reads. The pairing mirrors the product: prose explains, code is shown as it ran.

### Hierarchy
- **Display** (600, 1.75rem, tabular, -0.01em): the single-number stat answer only; its unit follows at the Answer size in 500 weight, Ink 2.
- **Headline** (600, 1.4375rem, -0.01em): the project name in the header. There is one per page.
- **Answer** (400, 1.1875rem, relaxed 1.625): the written answer under the root node, capped at 70ch.
- **Title** (600, 1rem): plan node names, callout titles, footer section headings.
- **Body** (400, 1rem): the question field.
- **Body Small** (400 or 500 for field labels, 0.875rem): node summaries, captions, form labels, chips, table cells, footer copy, panel caption (600).
- **Label** (400, 0.8125rem): hints, column headers of the plan (Time, Share of total), "attempt n", row estimates.
- **Code** (Source Code Pro 400, keywords 600, 0.8125rem or 0.9em of context): SQL blocks, table column headers, table and column names, model, prompt version and request ids.

### Named Rules
**The Mono Means Machine Rule.** Source Code Pro appears only for SQL, database identifiers and ids. Never for headings, numbers in prose or decoration.

**The Tabular Numbers Rule.** Every measured value (durations, table numbers, stat answers, row counts) uses tabular numerals so columns align like plan output.

**The Fixed Scale Rule.** Sizes come from the six rem steps; no fluid clamp() type. The page is a tool, not a poster.

## Layout

A single centred column (max 64rem) with 16px side gutters on mobile and 24px from 640px up. Order is fixed: README-style header (name, one paragraph, links), the ask form, the plan panel, then a three-column footer that stacks on small screens. Vertical rhythm between blocks is 16px on mobile and 24px on desktop.

The plan panel is a grid per row: node content, a 5rem right-aligned time column and a 9rem share-of-total bar column (from 640px). Under 640px the time sits beside the name and the bar drops to a full-width line beneath. Each level of the tree indents by 1rem on mobile and 1.25rem on desktop, capped at eight levels. Expanded detail and the root's answer indent 24px under the node text, so the spine runs past them.

In the answer, a narrow result table (three columns or fewer) sits beside its chart from 1024px; wider tables stack beneath. Tables scroll inside their own border (max 24rem tall, sticky header); the page never scrolls sideways. On mobile, only two example chips show, with a "More examples" link, and the keyboard hint is hidden.

## Elevation & Depth

Flat. There are no shadows anywhere. Depth is tonal and linear: grey ground, white panels, a well-grey layer for machine material, and 1px hairline borders to separate. Hover never lifts; it shifts a border or text to Plan Blue, or tints a table row with the well.

### Named Rules
**The Borders Not Shadows Rule.** Separation is a 1px rule or a tonal step. A box-shadow on any surface is out of system.

## Shapes

Nearly square. Controls, callouts, chips, SQL blocks and tables use a 3px corner (`rounded.sm`); the plan panel uses 5px (`rounded.md`). Time bars and their tracks are fully rounded pills 6px tall. Chart bars carry a 4px radius on their value end only, square at the baseline. The tree connectors are 1px strokes in Hairline Strong: a vertical spine from each node's icon, and an elbow (left and bottom border with a 3px inner corner) turning into each child row, as in EXPLAIN output. Icons are 16px line icons with a 2px stroke.

## Components

### Buttons
Direct and quiet; one filled button on the page.
- **Shape:** gently squared (`rounded.sm`).
- **Primary (Ask):** Plan Blue fill, white 600 text at Body Small, 10px by 20px padding. Label reads "Running" while a plan runs.
- **Hover / Focus / Active:** fill deepens to Plan Blue Deep; focus is a 2px Plan Blue outline offset 2px; pressed nudges down 1px.
- **Disabled:** Hairline Strong fill, white text, not-allowed cursor.
- **Text actions** ("Edit the question", "More examples"): Plan Blue 600/500 text with underline on hover; no fill.

### Chips (example questions)
- **Style:** white fill, Hairline border, Ink 2 text at Body Small, 4px by 10px padding, 3px corners, wrapping in a flex row with 8px gaps.
- **State:** hover turns border and text Plan Blue; disabled while running at 60% opacity. Clicking fills the question and runs it.

### Inputs / Fields
- **Style:** white fill, Hairline Strong border, 3px corners. The question textarea is Body size, two rows, vertically resizable, 500-character limit; the database select is Body Small with a custom 16px chevron in Ink 3.
- **Hover / Focus:** border darkens to Ink 3 on hover; focus shows the global Plan Blue outline; the caret is Plan Blue.
- **Disabled:** well-grey fill and Ink 3 text.

### Plan Tree (signature)
The page's defining component: an ordered list inside a white panel with a Hairline border and 5px corners, headed by a caption bar (Body Small 600, bottom rule) with the "Time" and "Share of total" column labels.
- **Rows:** status icon, node name (Title) with an optional "attempt n" label, summary (Body Small, Ink 2) below; time right-aligned in tabular Body Small; share bar on the right.
- **Connectors:** spine and elbows in Hairline Strong, as described in Shapes. Pending nodes keep an empty ring icon so the connectors never touch text.
- **Status icons:** check (Good), alert (Bad, with name and summary also in Bad), minus (skipped, Ink 3), empty ring (pending, Hairline Strong).
- **Expansion:** expandable node names are buttons followed by an inline chevron that rotates 90° in 150 ms; hover turns name and chevron Plan Blue. The detail region opens in place beneath, holding a facts list (Ink 3 labels, values beside), SQL blocks or check lists.
- **Time bars:** 6px pill on a well-grey track, filled by the time ramp (Bad when failed), growing from zero to their share once, over 250 ms ease-out, when a result arrives. A non-zero share shows at least a sliver.
- **Root segment bar:** the root node's bar is segmented: one piece per step in the order they ran, width proportional to duration, separated by 2px gaps, each coloured by the same ramp thresholds.
- **Running:** the root summary counts elapsed time; time cells and bars become pulsing well-grey placeholders.
- **Idle:** before any question the tree shows the plan with each node's one-line job and no timings.

### Callouts
- **Style:** 3px corners, 1px border, 10px by 14px padding; Title-weight heading, Body Small Ink 2 body.
- **Tones:** info (Hairline border, well fill) for clarification and unanswerable; warn (Warn at 30% border, Warn Wash fill); bad (Bad at 25% border, Bad Wash fill, Bad heading, announced as an alert).

### SQL Block
Well-grey fill, Hairline border, 3px corners, Source Code Pro at 0.8125rem with relaxed leading, wrapping. Keywords are uppercased and set in 600 weight; string literals in Ink 2. No colour syntax highlighting: the query is read, not decorated.

### Result Table
Bordered (Hairline, 3px corners), Body Small. Header row sticks, well-grey, column names in Source Code Pro 600 Ink 2 with units in Public Sans Ink 3 beside them. Numeric columns right-aligned and tabular (years stay left); nulls in Ink 3; row rules in Hairline; hover tints the row with the well.

### Result Chart
- **Forms:** stat (Display number with unit and a caption naming the column), bar (vertical or horizontal), line (optional series), scatter.
- **Marks:** series colours in fixed slot order; bars max 28px thick with 4px value-end radius; lines 2px, linear, dots only up to 24 points; no entry animation.
- **Axes and grid:** one value axis; Hairline grid on the value direction only; tick labels 12px Ink 3, no tick marks; legend only when there are multiple series.
- **Caption:** above the plot, naming each measured column in mono and its unit from the column comment ("co2 in Mt").
- **Tooltip:** white, Hairline border, 3px corners, 13px, title in Ink 600.
- **Twin:** every chart is accompanied by the result table with the same rows.

### Navigation (header and footer)
Header: white band with a bottom rule; project name (Headline), one explanatory paragraph in Ink 2, and three plain links (Plan Blue, 1px underline at 45% opacity that becomes solid on hover) aligned right from 768px. Footer: white band with a top rule, three sections (How it stays safe, Evaluation, Data) with Title headings in Ink and Ink 2 copy.

## Do's and Don'ts

### Do:
- **Do** keep Plan Blue for actions, links, focus and selection only.
- **Do** pair every status with its icon shape and text; colour is the third signal, not the first.
- **Do** set SQL, table and column names, model names and ids in Source Code Pro, and everything else in Public Sans.
- **Do** use tabular numerals for every duration, count and result value, and right-align numeric columns.
- **Do** separate with 1px hairlines and the well-grey layer.
- **Do** assign chart series from the palette in slot order, keep one value axis, caption the measure with its unit from the column comment, and show the table beside or below the chart.
- **Do** limit motion to state changes (chevron 150 ms, time bars 250 ms once, pulse while running) and let reduced-motion collapse it.

### Don't:
- **Don't** add a dark theme or tinted panels; the world is light only.
- **Don't** use box-shadows, gradients or blurred glass for depth.
- **Don't** colour-highlight SQL; weight and case carry the keywords.
- **Don't** use series or ramp colours in interface chrome.
- **Don't** introduce fluid display type or sizes outside the six-step rem scale.
- **Don't** present the page as a chat: no message bubbles, centred prompt boxes or sparkle icons.
- **Don't** animate charts on entry or decorate with motion that reports no state.
