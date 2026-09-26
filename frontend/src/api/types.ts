// Mirrors the FastAPI response models (backend/app/agent/*.py, backend/app/api/schemas.py).

export type AgentStatus = "success" | "needs_clarification" | "unanswerable" | "error";
export type TraceStatus = "success" | "failed" | "skipped";

export interface TraceEvent {
  step: string;
  status: TraceStatus;
  duration_ms: number;
  detail: Record<string, unknown>;
}

export interface QueryPlan {
  intent: "lookup" | "aggregate" | "ranking" | "trend" | "comparison" | "other";
  tables: string[];
  metrics: string[];
  filters: string[];
  group_by: string[];
  order_by: string | null;
  limit: number | null;
  assumptions: string[];
}

export interface ResultCheck {
  code: string;
  severity: "info" | "warning";
  message: string;
  column: string | null;
  repairable: boolean;
}

export interface ChartSpec {
  type: "stat" | "bar" | "line" | "scatter" | "none";
  x: string | null;
  y: string[];
  series: string | null;
  label: string | null;
  orientation: "vertical" | "horizontal" | null;
  reason: string;
}

export interface QueryError {
  category: string;
  message: string;
  code: string | null;
}

export interface QueryMetadata {
  database_id: string;
  dialect: string;
  model: string;
  prompt_version: string;
  tables_used: string[];
  execution_time_ms: number | null;
  row_count: number | null;
  truncated: boolean;
  retry_count: number;
  request_id: string | null;
}

export type Cell = string | number | boolean | null;

export interface AgentResult {
  status: AgentStatus;
  question: string;
  answer: string | null;
  answer_source: "llm" | "template" | null;
  clarification_question: string | null;
  explanation: string | null;
  plan: QueryPlan | null;
  sql: string | null;
  columns: string[];
  rows: Cell[][];
  chart_suggestion: string | null;
  chart: ChartSpec | null;
  checks: ResultCheck[];
  error: QueryError | null;
  trace: TraceEvent[];
  metadata: QueryMetadata;
}

export interface DatabaseInfo {
  id: string;
  name: string;
  dialect: string;
  source: "config" | "ui";
  sampling: "off" | "safe" | "full";
  status: "ready" | "rejected" | "unavailable";
  issues: string[];
}

export interface ColumnProfile {
  name: string;
  type: string;
  nullable: boolean;
  comment: string | null;
  primary_key: boolean;
  sensitive: boolean;
}

export interface TableProfile {
  schema_name: string;
  name: string;
  kind: string;
  comment: string | null;
  estimated_rows: number | null;
  columns: ColumnProfile[];
}

export interface DatabaseProfile {
  database_id: string;
  dialect: string;
  tables: TableProfile[];
}
