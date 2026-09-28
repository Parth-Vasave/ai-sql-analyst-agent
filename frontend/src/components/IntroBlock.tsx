const STEPS = [
  ['plan', 'the model drafts a query plan and SQL from your question'],
  ['validate', 'the SQL is checked against a syntax tree — only a single read-only SELECT against real, known tables and columns is accepted; nothing else reaches the database'],
  ['execute', 'it runs on a read-only account with a timeout and a row limit'],
  ['check', 'the result is screened for what an LLM gets wrong on its own — empty results from a misspelled filter, rankings led by NULL, and the like'],
  ['answer', 'every number in the written answer is checked against the rows actually returned; unverifiable ones are dropped for a plainer, grounded answer'],
] as const

export function IntroBlock() {
  return (
    <div className="px-1 py-6 font-mono text-[14px] leading-relaxed text-ink-dim sm:py-10">
      <p className="mb-4 max-w-[34rem] text-ink">
        Ask this database a question in plain language. The SQL that answers it is never trusted
        on its own — here is what happens between your question and the answer:
      </p>
      <ol className="max-w-[34rem] space-y-2">
        {STEPS.map(([label, description], index) => (
          <li key={label} className="flex gap-3">
            <span className="text-ink-faint">{index + 1}.</span>
            <span>
              <span className="text-accent">[{label}]</span> {description}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}
