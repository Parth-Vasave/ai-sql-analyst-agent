import type { ReactNode } from "react";

import type { AgentResult, QueryPlan } from "../api/types";
import type { PlanNode } from "../planTree";
import { SqlBlock } from "./SqlBlock";

function Facts({ items }: { items: [string, ReactNode][] }) {
  const shown = items.filter(([, value]) => value !== null && value !== undefined && value !== "");
  if (shown.length === 0) return null;
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
      {shown.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-ink-3">{label}</dt>
          <dd className="min-w-0 break-words">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function codeList(values: unknown): ReactNode {
  if (!Array.isArray(values) || values.length === 0) return null;
  return values.map((v, i) => (
    <span key={String(v)}>
      {i > 0 && ", "}
      <code>{String(v)}</code>
    </span>
  ));
}

function planFacts(plan: QueryPlan | null): [string, ReactNode][] {
  if (!plan) return [];
  const list = (values: string[]) => (values.length ? values.join("; ") : null);
  return [
    ["Intent", plan.intent],
    ["Tables", codeList(plan.tables)],
    ["Measures", list(plan.metrics)],
    ["Filters", list(plan.filters)],
    ["Grouped by", list(plan.group_by)],
    ["Ordered by", plan.order_by],
    ["Row limit", plan.limit === null ? null : String(plan.limit)],
    ["Assumptions", list(plan.assumptions)],
  ];
}

/** Expandable content for each executed plan node; only nodes with something to show get an entry. */
export function nodeDetails(result: AgentResult, nodes: PlanNode[]): Record<string, ReactNode> {
  const details: Record<string, ReactNode> = {};
  const lastOf = (step: PlanNode["step"]) => nodes.find((n) => n.step === step)?.key; // nodes are newest first
  const lastExecution = lastOf("execution");
  const lastGeneration = nodes.find((n) => n.step === "generation" || n.step === "repair")?.key;

  details.answer = (
    <Facts
      items={[
        ["Model", <code key="m">{result.metadata.model}</code>],
        ["Prompt", <code key="p">{result.metadata.prompt_version}</code>],
        ["Repairs", String(result.metadata.retry_count)],
        ["Request ID", result.metadata.request_id ? <code key="r">{result.metadata.request_id}</code> : null],
      ]}
    />
  );

  for (const node of nodes) {
    const d = node.detail;
    switch (node.step) {
      case "execution":
        if (node.key === lastExecution && result.sql && node.status === "success") {
          details[node.key] = (
            <>
              <p className="text-sm text-ink-2">The SQL that ran, as rewritten by the validator:</p>
              <SqlBlock sql={result.sql} />
            </>
          );
        }
        break;
      case "validation":
        details[node.key] = (
          <Facts
            items={[
              ["Tables read", codeList(d.tables)],
              ["Row limit", d.limit === undefined ? null : `${String(d.limit)} (${String(d.limit_action)})`],
              ["Rejected as", d.code ? String(d.code).replaceAll("_", " ") : null],
              [
                "Plan vs SQL",
                Array.isArray(d.plan_warnings) && d.plan_warnings.length ? d.plan_warnings.join("; ") : null,
              ],
            ]}
          />
        );
        break;
      case "generation":
      case "repair":
        details[node.key] = (
          <Facts
            items={[
              ...planFacts(node.key === lastGeneration ? result.plan : null),
              ["Model", d.model ? <code key="m">{String(d.model)}</code> : null],
                ["Prompt", d.prompt_version ? <code key="p">{String(d.prompt_version)}</code> : null],
                ["Tokens in / out", d.prompt_tokens ? `${String(d.prompt_tokens)} / ${String(d.completion_tokens)}` : null],
              ["Provider attempts", d.provider_attempts ? String(d.provider_attempts) : null],
            ]}
          />
        );
        break;
      case "checks":
        if (result.checks.length) {
          details[node.key] = (
            <ul className="space-y-1 text-sm">
              {result.checks.map((check) => (
                <li key={`${check.code}-${check.message}`}>
                  <span className={check.severity === "warning" ? "font-semibold text-warn" : "font-semibold"}>
                    {check.code.replaceAll("_", " ")}
                  </span>
                  <span className="text-ink-2">: {check.message}</span>
                </li>
              ))}
            </ul>
          );
        }
        break;
      case "chart":
        if (result.chart) details[node.key] = <p className="text-sm text-ink-2">{result.chart.reason}</p>;
        break;
      case "schema":
        details[node.key] = <Facts items={[["Tables sent to the model", codeList(d.tables)]]} />;
        break;
      default:
        break;
    }
  }
  return details;
}
