import type { AgentResult, TraceEvent } from "./api/types";

/** One row of the plan: a step of the agent, EXPLAIN-style (the final output first). */
export interface PlanNode {
  key: string;
  step: StepKind;
  name: string;
  status: "success" | "failed" | "skipped" | "pending";
  durationMs: number | null;
  share: number; // of the total time, 0..1
  summary: string;
  error: string | null;
  attempt: number | null; // shown when the agent needed more than one attempt
  detail: Record<string, unknown>;
}

export type StepKind =
  | "answer"
  | "chart"
  | "answer_text"
  | "checks"
  | "execution"
  | "validation"
  | "generation"
  | "repair"
  | "schema"
  | "question";

interface StepInfo {
  name: string;
  job: string; // what the step does, shown before a question is asked
}

export const STEPS: Record<StepKind, StepInfo> = {
  answer: {
    name: "Answer",
    job: "The result of the whole plan: the answer, a chart when the data has a shape worth drawing, and the rows.",
  },
  chart: {
    name: "Chart choice",
    job: "Chosen from the shape of the result, not by the model: one value becomes a figure, years a line, categories bars.",
  },
  answer_text: {
    name: "Answer text",
    job: "Written from the returned rows. Every number in it must appear in the result; otherwise a plain answer built from the rows is shown.",
  },
  checks: {
    name: "Result checks",
    job: "An empty result is probed for filter values that do not exist; a ranking led by missing values is sent back for repair.",
  },
  execution: {
    name: "Execution",
    job: "Runs on a read-only database account with a statement timeout; only a limited number of rows can come back.",
  },
  validation: {
    name: "Validation",
    job: "The SQL is parsed, never trusted: one SELECT only, known tables and columns, no system catalogs or dangerous functions, a LIMIT enforced.",
  },
  generation: {
    name: "SQL generation",
    job: "The language model writes a short query plan and one SELECT statement for the question.",
  },
  repair: {
    name: "SQL repair",
    job: "When validation, the database or a result check rejects the SQL, the model gets the reason back and tries again, at most twice.",
  },
  schema: {
    name: "Schema retrieval",
    job: "Finds the tables that matter for the question. Columns that look sensitive are never shown to the model.",
  },
  question: {
    name: "Question",
    job: "What you asked, in your own words.",
  },
};

/** The plan before anything runs: EXPLAIN without ANALYZE. */
export const IDLE_ORDER: StepKind[] = [
  "answer",
  "chart",
  "answer_text",
  "checks",
  "execution",
  "validation",
  "generation",
  "schema",
  "question",
];

const TRACE_TO_STEP: Record<string, StepKind> = {
  chart_selection: "chart",
  answer_generation: "answer_text",
  result_validation: "checks",
  query_execution: "execution",
  sql_validation: "validation",
  sql_generation: "generation",
  sql_repair: "repair",
  schema_retrieval: "schema",
  question_received: "question",
};

const CHART_NAMES: Record<string, string> = {
  stat: "Single figure",
  bar: "Bar chart",
  line: "Line chart",
  scatter: "Scatter plot",
  none: "No chart; the table shows the result",
};

function plural(n: number, word: string): string {
  return `${n.toLocaleString("en")} ${word}${n === 1 ? "" : "s"}`;
}

function asList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function summarize(kind: StepKind, event: TraceEvent, result: AgentResult): string {
  const d = event.detail;
  switch (kind) {
    case "chart":
      return CHART_NAMES[String(d.type ?? "none")] ?? "No chart";
    case "answer_text": {
      if (d.source === "llm") return "Written by the model; every number checked against the rows";
      const ungrounded = asList(d.ungrounded_numbers);
      if (ungrounded.length) return `Model answer rejected (${ungrounded.join(", ")} not in the rows); built from the rows`;
      if (event.status === "failed") return "Model unavailable; built from the rows";
      return `Built from the rows${d.reason ? `: ${String(d.reason)}` : ""}`;
    }
    case "checks": {
      const checks = asList(d.checks);
      return checks.length ? checks.map((c) => c.replaceAll("_", " ")).join(", ") : "Nothing flagged";
    }
    case "execution":
      if (event.status === "failed") return `Database error: ${String(d.category ?? "other").replaceAll("_", " ")}`;
      return `${plural(Number(d.rows ?? 0), "row")}${d.truncated ? ", more exist" : ""}`;
    case "validation": {
      if (event.status === "failed") return `Rejected: ${String(d.code ?? "invalid").replaceAll("_", " ")}`;
      const tables = asList(d.tables);
      const limit = d.limit_action === "added" ? `LIMIT ${String(d.limit)} added` : d.limit_action === "clamped" ? `LIMIT lowered to ${String(d.limit)}` : `LIMIT ${String(d.limit)}`;
      return `${plural(tables.length, "table")}, ${limit}`;
    }
    case "generation":
    case "repair": {
      if (event.status === "failed") {
        const error = String(d.error ?? "");
        if (/HTTP 429/.test(error)) return "Rate-limited by the model provider (HTTP 429)";
        const outage = /HTTP (5\d\d)/.exec(error);
        if (outage) return `Model provider unavailable (HTTP ${outage[1]})`;
        if (/request failed/.test(error)) return "The model provider could not be reached";
        return "The model's reply could not be used";
      }
      const parts = [String(d.model ?? result.metadata.model)];
      if (typeof d.intent === "string") parts.push(`${d.intent} plan`);
      const tokens = Number(d.prompt_tokens ?? 0) + Number(d.completion_tokens ?? 0);
      if (tokens > 0) parts.push(plural(tokens, "token"));
      return parts.join(", ");
    }
    case "schema":
      return plural(asList(d.tables).length, "table");
    case "question":
      return result.question;
    default:
      return "";
  }
}

function errorOf(event: TraceEvent): string | null {
  if (event.status !== "failed") return null;
  const e = event.detail.error;
  return typeof e === "string" ? e : null;
}

const FAILURE_WORDS: Record<string, string> = {
  llm_error: "the language model did not answer",
  validation: "the SQL was rejected",
  timeout: "the query timed out",
};

function answerSummary(result: AgentResult): string {
  switch (result.status) {
    case "success":
      return plural(result.rows.length, "row");
    case "needs_clarification":
      return "Needs a clearer question";
    case "unanswerable":
      return "Not answerable from this database";
    case "error":
      if (!result.error) return "Failed";
      return `Failed: ${FAILURE_WORDS[result.error.category] ?? `database error (${result.error.category.replaceAll("_", " ")})`}`;
  }
}

/** The executed plan, root first, then the steps from the most recent to the first. */
export function buildPlan(result: AgentResult): PlanNode[] {
  const steps = result.trace.filter((e) => e.step in TRACE_TO_STEP);
  const total = steps.reduce((sum, e) => sum + Math.max(e.duration_ms, 0), 0);
  const attempts = Math.max(1, ...steps.map((e) => Number(e.detail.attempt ?? 1)));

  const nodes: PlanNode[] = [...steps].reverse().map((event, index) => {
    const kind = TRACE_TO_STEP[event.step] as StepKind;
    const attempt = typeof event.detail.attempt === "number" ? event.detail.attempt : null;
    return {
      key: `${event.step}-${index}`,
      step: kind,
      name: STEPS[kind].name,
      status: event.status,
      durationMs: event.duration_ms,
      share: total > 0 ? event.duration_ms / total : 0,
      summary: summarize(kind, event, result),
      error: errorOf(event),
      attempt: attempts > 1 ? attempt : null,
      detail: event.detail,
    };
  });

  const root: PlanNode = {
    key: "answer",
    step: "answer",
    name: STEPS.answer.name,
    status: result.status === "error" ? "failed" : "success",
    durationMs: total,
    share: 1,
    summary: answerSummary(result),
    error: result.status === "error" ? (result.error?.message ?? null) : null,
    attempt: null,
    detail: {},
  };
  return [root, ...nodes];
}

/** Nodes for the plan before a question has been asked (or while it runs). */
export function idlePlan(): PlanNode[] {
  return IDLE_ORDER.map((kind) => ({
    key: kind,
    step: kind,
    name: STEPS[kind].name,
    status: "pending",
    durationMs: null,
    share: 0,
    summary: STEPS[kind].job,
    error: null,
    attempt: null,
    detail: {},
  }));
}

export function formatDuration(ms: number | null): string {
  if (ms === null) return "";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;
}
