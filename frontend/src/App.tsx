import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, ask, getProfile, listDatabases } from "./api/client";
import type { AgentResult, DatabaseInfo, DatabaseProfile } from "./api/types";
import { AnswerOutput } from "./components/AnswerOutput";
import { AskForm } from "./components/AskForm";
import { nodeDetails } from "./components/NodeDetails";
import { PlanTree } from "./components/PlanTree";
import { ProjectFooter } from "./components/ProjectFooter";
import { ProjectHeader } from "./components/ProjectHeader";
import { buildPlan, idlePlan } from "./planTree";
import { unitsFromProfile } from "./units";

function apiErrorText(error: ApiError): { title: string; body: string } {
  if (error.status === 503 && /LLM/.test(error.message)) {
    return {
      title: "No language model is configured",
      body: "This deployment has no LLM_API_KEY, so it cannot write SQL. The database list and schema still work.",
    };
  }
  if (error.status === 0) return { title: "The API is unreachable", body: error.message };
  return { title: `The API returned an error (HTTP ${error.status})`, body: error.message };
}

export default function App() {
  const [databases, setDatabases] = useState<DatabaseInfo[]>([]);
  const [databaseId, setDatabaseId] = useState<string | null>(null);
  const [profile, setProfile] = useState<DatabaseProfile | null>(null);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AgentResult | null>(null);
  const [apiError, setApiError] = useState<ApiError | null>(null);
  const [running, setRunning] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    listDatabases()
      .then((list) => {
        setDatabases(list);
        setDatabaseId(list.find((db) => db.status === "ready")?.id ?? list[0]?.id ?? null);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError) setApiError(error);
      });
  }, []);

  useEffect(() => {
    if (!databaseId) return;
    setProfile(null);
    getProfile(databaseId)
      .then(setProfile)
      .catch(() => setProfile(null)); // the schema list is optional; asking still works
  }, [databaseId]);

  useEffect(() => {
    if (!running) return;
    const started = performance.now();
    const timer = window.setInterval(() => setElapsedMs(Math.round(performance.now() - started)), 100);
    return () => window.clearInterval(timer);
  }, [running]);

  const submit = useCallback(
    (text: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setRunning(true);
      setElapsedMs(0);
      setApiError(null);
      setResult(null);
      ask(text, databaseId, controller.signal)
        .then(setResult)
        .catch((error: unknown) => {
          if (controller.signal.aborted) return;
          setApiError(error instanceof ApiError ? error : new ApiError(0, String(error), null));
        })
        .finally(() => {
          if (abortRef.current === controller) setRunning(false);
        });
    },
    [databaseId],
  );

  const refine = useCallback(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const nodes = useMemo(() => (result ? buildPlan(result) : idlePlan()), [result]);
  const details = useMemo(() => (result ? nodeDetails(result, nodes) : {}), [result, nodes]);
  const caption = result ? `Plan for: ${result.question}` : running ? "Running the plan" : "How a question is answered";
  const failure = apiError ? apiErrorText(apiError) : null;
  const units = useMemo(() => unitsFromProfile(profile), [profile]);

  return (
    <div className="flex min-h-screen flex-col">
      <ProjectHeader />
      <main className="mx-auto w-full max-w-5xl flex-1 space-y-4 px-4 py-4 sm:space-y-6 sm:px-6 sm:py-6">
        <AskForm
          databases={databases}
          databaseId={databaseId}
          onDatabaseChange={setDatabaseId}
          profile={profile}
          question={question}
          onQuestionChange={setQuestion}
          onSubmit={submit}
          running={running}
          inputRef={inputRef}
        />
        {failure && (
          <div role="alert" className="rounded-sm border border-bad/25 bg-bad-soft px-3.5 py-2.5">
            <p className="font-semibold text-bad">{failure.title}</p>
            <p className="mt-0.5 text-sm text-ink-2">{failure.body}</p>
          </div>
        )}
        <PlanTree
          key={result?.metadata.request_id ?? (running ? "running" : "idle")}
          nodes={nodes}
          details={details}
          running={running}
          elapsedMs={elapsedMs}
          caption={caption}
          rootOutput={result ? <AnswerOutput result={result} onRefine={refine} units={units} /> : undefined}
        />
      </main>
      <ProjectFooter />
    </div>
  );
}
