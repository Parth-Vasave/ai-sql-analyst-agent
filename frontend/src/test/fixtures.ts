import type { AgentResult, TraceEvent } from "../api/types";

export function event(step: string, duration_ms: number, detail: Record<string, unknown> = {}, status: TraceEvent["status"] = "success"): TraceEvent {
  return { step, status, duration_ms, detail };
}

export const SQL =
  "SELECT c.name AS country, e.co2 FROM public.co2_emissions AS e JOIN public.countries AS c ON e.country_id = c.id WHERE e.year = 2023 ORDER BY e.co2 DESC LIMIT 3";

export function success(overrides: Partial<AgentResult> = {}): AgentResult {
  return {
    status: "success",
    question: "Which 3 countries emitted the most CO2 in 2023?",
    answer: "China emitted 12,172.009 Mt, followed by the United States and India.",
    answer_source: "llm",
    clarification_question: null,
    explanation: "Top 3 by CO2.",
    plan: {
      intent: "ranking",
      tables: ["public.co2_emissions", "public.countries"],
      metrics: ["co2"],
      filters: ["year = 2023"],
      group_by: [],
      order_by: "co2 DESC",
      limit: 3,
      assumptions: ["'countries' excludes regions"],
    },
    sql: SQL,
    columns: ["country", "co2"],
    rows: [
      ["China", 12172.009],
      ["United States", 4918.407],
      ["India", 3062.756],
    ],
    chart_suggestion: "bar",
    chart: { type: "bar", x: "country", y: ["co2"], series: null, label: null, orientation: "horizontal", reason: "co2 compared across country" },
    checks: [],
    error: null,
    trace: [
      event("question_received", 0, { question_length: 46 }),
      event("schema_retrieval", 120, { tables: ["public.co2_emissions", "public.countries"] }),
      event("sql_generation", 2000, { attempt: 1, model: "gemini-test", intent: "ranking", prompt_tokens: 900, completion_tokens: 80 }),
      event("sql_validation", 5, { code: "unknown_column", error: "Column 'emissions' could not be resolved." }, "failed"),
      event("sql_repair", 1500, { attempt: 2, model: "gemini-test", intent: "ranking" }),
      event("sql_validation", 6, { attempt: 2, tables: ["public.co2_emissions", "public.countries"], limit: 3, limit_action: "kept", plan_warnings: [] }),
      event("query_execution", 20, { attempt: 2, rows: 3, truncated: false }),
      event("result_validation", 2, { attempt: 2, checks: [] }),
      event("answer_generation", 900, { source: "llm", model: "gemini-test" }),
      event("chart_selection", 1, { type: "bar", reason: "co2 compared across country" }),
      event("completed", 0, { retries: 1 }),
    ],
    metadata: {
      database_id: "default",
      dialect: "postgres",
      model: "gemini-test",
      prompt_version: "sql-generator/2",
      tables_used: ["public.co2_emissions", "public.countries"],
      execution_time_ms: 20,
      row_count: 3,
      truncated: false,
      retry_count: 1,
      request_id: "req-123",
    },
    ...overrides,
  };
}
