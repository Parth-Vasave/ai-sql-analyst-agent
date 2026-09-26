import { ChevronDown, ChevronRight } from "lucide-react";
import { type FormEvent, type KeyboardEvent, useId, useState } from "react";

import type { DatabaseInfo, DatabaseProfile } from "../api/types";

// Questions from the evaluation set (evaluation/questions.json), each with verified ground truth.
export const EXAMPLES = [
  "Which 5 countries emitted the most CO2 in 2023?",
  "How did India's CO2 emissions change year by year from 2015 to 2020?",
  "What was China's share of global CO2 emissions in 2023?",
  "Among countries with more than 100 million people in 2022, which 5 had the lowest CO2 per capita?",
  "Which World Bank income group had the highest total CO2 emissions in 2022?",
  "Show me the trend.",
];

interface Props {
  databases: DatabaseInfo[];
  databaseId: string | null;
  onDatabaseChange: (id: string) => void;
  profile: DatabaseProfile | null;
  question: string;
  onQuestionChange: (question: string) => void;
  onSubmit: (question: string) => void;
  running: boolean;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
}

export function AskForm({
  databases,
  databaseId,
  onDatabaseChange,
  profile,
  question,
  onQuestionChange,
  onSubmit,
  running,
  inputRef,
}: Props) {
  const questionId = useId();
  const databaseSelectId = useId();
  const hintId = useId();
  const trimmed = question.trim();
  const [allExamples, setAllExamples] = useState(false);
  const SHOWN_ON_SMALL_SCREENS = 2;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (trimmed && !running) onSubmit(trimmed);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) submit(event);
  }

  return (
    <section aria-label="Ask a question" className="space-y-3 sm:space-y-4">
      <form onSubmit={submit} className="space-y-2.5 sm:space-y-3">
        <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3">
          <label htmlFor={databaseSelectId} className="text-sm font-medium">
            Database
          </label>
          <div className="relative inline-block">
          <select
            id={databaseSelectId}
            value={databaseId ?? ""}
            onChange={(e) => onDatabaseChange(e.target.value)}
            disabled={databases.length === 0 || running}
            className="w-full appearance-none rounded-sm border border-rule-strong bg-surface py-1.5 pr-8 pl-2.5 text-sm hover:border-ink-3 disabled:bg-well disabled:text-ink-3 sm:w-auto"
          >
            {databases.length === 0 && <option value="">No database available</option>}
            {databases.map((db) => (
              // a rejected account (not read-only) can never be used; an unavailable one is retried on use
              <option key={db.id} value={db.id} disabled={db.status === "rejected"}>
                {db.name}
                {db.status !== "ready" ? ` (${db.status})` : ""}
              </option>
            ))}
          </select>
            <ChevronDown aria-hidden className="pointer-events-none absolute top-1/2 right-2 size-4 -translate-y-1/2 text-ink-3" />
          </div>
        </div>

        <div>
          <label htmlFor={questionId} className="text-sm font-medium">
            Question
          </label>
          <div className="mt-1.5 flex flex-col gap-2 sm:flex-row sm:items-start">
            <textarea
              id={questionId}
              ref={inputRef}
              value={question}
              onChange={(e) => onQuestionChange(e.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              maxLength={500}
              aria-describedby={hintId}
              placeholder="For example: which 5 countries emitted the most CO2 in 2023?"
              className="min-h-[3.25rem] w-full resize-y rounded-sm border border-rule-strong bg-surface px-3 py-2 text-base placeholder:text-ink-3 hover:border-ink-3"
            />
            <button
              type="submit"
              disabled={!trimmed || running}
              className="shrink-0 rounded-sm bg-accent px-5 py-2.5 text-sm font-semibold text-white hover:bg-accent-hover active:translate-y-px disabled:cursor-not-allowed disabled:bg-rule-strong disabled:text-white"
            >
              {running ? "Running" : "Ask"}
            </button>
          </div>
          <p id={hintId} className="mt-1.5 hidden text-xs text-ink-3 sm:block">
            Ctrl+Enter or ⌘+Enter to ask. Questions are answered from the data only; up to 500 characters.
          </p>
        </div>
      </form>

      <div>
        <h2 className="text-sm font-medium">Examples from the evaluation set</h2>
        <ul className="mt-1.5 flex flex-wrap gap-2">
          {EXAMPLES.map((example, index) => (
            <li key={example} className={index >= SHOWN_ON_SMALL_SCREENS && !allExamples ? "hidden sm:block" : ""}>
              <button
                type="button"
                disabled={running}
                onClick={() => {
                  onQuestionChange(example);
                  onSubmit(example);
                }}
                className="rounded-sm border border-rule bg-surface px-2.5 py-1 text-left text-sm text-ink-2 hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
              >
                {example}
              </button>
            </li>
          ))}
          {!allExamples && (
            <li className="sm:hidden">
              <button
                type="button"
                onClick={() => setAllExamples(true)}
                className="px-1 py-1 text-sm font-medium text-accent hover:underline"
              >
                More examples ({EXAMPLES.length - SHOWN_ON_SMALL_SCREENS})
              </button>
            </li>
          )}
        </ul>
      </div>

      {profile && profile.tables.length > 0 && (
        <details className="group rounded-sm border border-rule bg-surface">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-sm font-medium text-ink-2 select-none hover:text-ink [&::-webkit-details-marker]:hidden">
            <ChevronRight aria-hidden className="size-4 text-ink-3 transition-transform duration-150 group-open:rotate-90" />
            What this database contains ({profile.tables.length} tables)
          </summary>
          <div className="grid gap-4 border-t border-rule px-3 py-3 sm:grid-cols-2">
            {profile.tables.map((table) => (
              <div key={`${table.schema_name}.${table.name}`}>
                <h3 className="text-sm">
                  <code className="font-semibold">{table.name}</code>
                  {table.estimated_rows !== null && (
                    <span className="tabular ml-2 text-xs text-ink-3">
                      about {table.estimated_rows.toLocaleString("en")} rows
                    </span>
                  )}
                </h3>
                {table.comment && <p className="mt-0.5 text-xs text-ink-2">{table.comment}</p>}
                <p className="mt-1 text-xs leading-relaxed text-ink-2">
                  {table.columns
                    .filter((c) => !c.sensitive)
                    .map((c, i) => (
                      <span key={c.name}>
                        {i > 0 && ", "}
                        <code title={c.comment ?? undefined}>{c.name}</code>
                      </span>
                    ))}
                </p>
              </div>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}
