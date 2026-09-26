import { lazy, type ReactNode, Suspense } from "react";

import type { AgentResult } from "../api/types";
import { ResultTable } from "./ResultTable";
import { SqlBlock } from "./SqlBlock";

// Recharts is most of the bundle; load it only once there is a result to draw.
const ResultChart = lazy(() => import("./ResultChart").then((m) => ({ default: m.ResultChart })));

/** What went wrong, and what to do about it, for an agent error. */
export function errorExplanation(result: AgentResult): { title: string; body: string } {
  const error = result.error;
  if (!error) return { title: "The question could not be answered", body: "No error details were returned." };
  const message = error.message;
  if (error.category === "llm_error") {
    if (/HTTP 429/.test(message)) {
      return {
        title: "The language model is rate-limiting requests",
        body: "The model provider refused the request (HTTP 429), usually a free-tier quota. Wait a minute and ask again.",
      };
    }
    if (/HTTP 5\d\d|request failed/.test(message)) {
      return {
        title: "The language model could not be reached",
        body: `${message}. This is on the provider's side; asking again usually works.`,
      };
    }
    return { title: "The language model returned an unusable reply", body: message };
  }
  if (error.category === "validation") {
    return {
      title: "The generated SQL was rejected",
      body: `${message} Nothing was run on the database.`,
    };
  }
  if (error.category === "timeout") {
    return {
      title: "The query took too long",
      body: "The database cancelled it at the statement time limit. Try a narrower question, such as fewer years or one country.",
    };
  }
  return { title: "The database returned an error", body: `${message} (${error.category.replaceAll("_", " ")})` };
}

function Callout({ tone, title, children }: { tone: "info" | "warn" | "bad"; title: string; children: ReactNode }) {
  const tones = {
    info: "border-rule bg-well",
    warn: "border-warn/30 bg-warn-soft",
    bad: "border-bad/25 bg-bad-soft",
  };
  return (
    <div role={tone === "bad" ? "alert" : undefined} className={`rounded-sm border px-3.5 py-2.5 ${tones[tone]}`}>
      <p className={`font-semibold ${tone === "bad" ? "text-bad" : ""}`}>{title}</p>
      <div className="mt-0.5 text-sm text-ink-2">{children}</div>
    </div>
  );
}

interface Props {
  result: AgentResult;
  onRefine: () => void;
  units?: Record<string, string>;
}

export function AnswerOutput({ result, onRefine, units = {} }: Props) {
  if (result.status === "needs_clarification") {
    return (
      <Callout tone="info" title="The question needs to be more specific">
        <p>{result.clarification_question}</p>
        <button type="button" onClick={onRefine} className="mt-2 text-sm font-semibold text-accent hover:underline">
          Edit the question
        </button>
      </Callout>
    );
  }

  if (result.status === "unanswerable") {
    return (
      <Callout tone="info" title="This database cannot answer that">
        <p>{result.answer ?? result.explanation}</p>
        <p className="mt-1">The list of tables above the plan shows what the data covers.</p>
      </Callout>
    );
  }

  if (result.status === "error") {
    const { title, body } = errorExplanation(result);
    return (
      <div className="space-y-3">
        <Callout tone="bad" title={title}>
          <p>{body}</p>
        </Callout>
        {result.sql && (
          <div>
            <p className="mb-1 text-sm text-ink-2">The last SQL the model wrote:</p>
            <SqlBlock sql={result.sql} />
          </div>
        )}
      </div>
    );
  }

  const assumptions = result.plan?.assumptions ?? [];
  const shown = result.chart && result.chart.type !== "none";
  return (
    <div className="space-y-4">
      <div className="max-w-[70ch]">
        <p className="text-lg leading-relaxed">{result.answer}</p>
        {assumptions.length > 0 && (
          <div className="mt-2 text-sm text-ink-2">
            <p>Read as:</p>
            <ul className="mt-0.5 list-disc space-y-0.5 pl-5">
              {assumptions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <div
        className={
          shown && result.columns.length <= 3
            ? "grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_auto]" // a narrow table sits beside its chart
            : "space-y-4"
        }
      >
        {shown && result.chart && (
          <Suspense fallback={<div aria-hidden className="h-[280px] animate-pulse rounded-sm bg-well" />}>
            <ResultChart spec={result.chart} columns={result.columns} rows={result.rows} units={units} />
          </Suspense>
        )}
        <ResultTable columns={result.columns} rows={result.rows} caption={`Result of: ${result.question}`} units={units} />
      </div>
    </div>
  );
}
