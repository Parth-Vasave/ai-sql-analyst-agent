import { DATA_URL, EVALUATION_URL, REPO_URL } from "../links";

export function ProjectHeader() {
  return (
    <header className="border-b border-rule bg-surface">
      <div className="mx-auto flex max-w-5xl flex-col gap-2 px-4 py-4 sm:gap-3 sm:px-6 sm:py-6 md:flex-row md:items-end md:justify-between">
        <div className="max-w-2xl">
          <h1 className="text-xl font-semibold tracking-[-0.01em]">AI SQL Analyst</h1>
          <p className="mt-1 text-sm text-ink-2">
            An open-source agent that answers questions about a database in SQL. A language model writes the query; a
            validator, a read-only database account and result checks decide what runs and what you see. Every step is
            shown below.
          </p>
        </div>
        <nav aria-label="Project" className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
          <a href={REPO_URL}>Source code</a>
          <a href={EVALUATION_URL}>Evaluation</a>
          <a href={DATA_URL}>Data source</a>
        </nav>
      </div>
    </header>
  );
}
