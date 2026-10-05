import type { ReactNode } from 'react'
import { Dialog } from './Dialog'

interface HelpPanelProps {
  onClose: () => void
}

const PIPELINE_STEPS = [
  ['plan', 'the model drafts a query plan (intent, tables, metrics, filters) and SQL from your question. If no reading of the question is reasonable, it asks a clarifying question instead.'],
  ['validate', 'the SQL is parsed into a syntax tree and checked: a single read-only SELECT, only tables and columns the profiler actually found, no system catalogs, no functions off an allow-list. Nothing else reaches the database — the SQL that runs is regenerated from the checked tree, not the model\'s original text.'],
  ['execute', 'it runs on a read-only database account with a query timeout and a row limit, both enforced twice (in the SQL and again client-side).'],
  ['check', 'the result is screened for what an LLM gets wrong on its own — an empty result from a misspelled filter value, a ranking led by NULL, an aggregate over nothing. Some of these trigger an automatic repair with a targeted hint; the SQL is validated again after any repair.'],
  ['answer', 'every number in the written answer is checked against the rows actually returned, the question, or the row count. Anything unverifiable is dropped in favor of a plainer, template-built answer.'],
] as const

const ERRORS = [
  ['No database is ready', 'no connected database passed its read-only check. Connect one from the settings menu (bottom left), or ask the person running this instance to check DATABASE_URL / databases.toml.'],
  ['Not read-only', 'the account you connected can write data (insert/update/create/etc). Only strictly read-only accounts are accepted — create one and reconnect.'],
  ['No LLM configured', 'the server has no LLM_API_KEY set. Questions cannot be answered until the operator sets one.'],
  ['Rate limited', 'you (or the whole server) hit the configured question budget. The banner shows a countdown; retry after it reaches zero.'],
  ['Could not reach the API', 'the backend is not running or is unreachable from this page — check that it is up and that VITE_API_PROXY_TARGET / VITE_API_BASE_URL points at it.'],
] as const

export function HelpPanel({ onClose }: HelpPanelProps) {
  return (
    <Dialog title="How it works" description="What happens between your question and the answer, and how to read what comes back." onClose={onClose} wide>
      <div className="flex flex-col gap-7 text-[14px] leading-relaxed text-ink-dim">
        <Section title="Asking questions">
          <p>
            Ask about the connected database in plain language and press Enter (Shift+Enter for a new line). Be as
            specific as a real analytical question would be — a country, a year, a metric, a comparison. If your
            question is ambiguous, the model asks a clarifying question instead of guessing; if it can answer with a
            stated assumption instead, it will (e.g. "latest available year"), and the assumption is shown under the
            answer.
          </p>
          <p>
            Follow-ups work within a chat: "and Germany?" after a question about France reuses the last few turns of
            context. Up to 3 prior turns are sent with each new question; the server itself keeps no conversation
            state. Chats are saved in this browser only.
          </p>
        </Section>

        <Section title="What happens to your question">
          <ol className="flex flex-col gap-3">
            {PIPELINE_STEPS.map(([label, description], index) => (
              <li key={label} className="flex gap-3">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-raised text-[12px] font-medium text-ink tabular-nums">
                  {index + 1}
                </span>
                <span>
                  <span className="font-medium text-ink capitalize">{label}</span> — {description}
                </span>
              </li>
            ))}
          </ol>
          <p>
            Every answer starts with a one-line summary of this — open it to see the plan, the exact SQL that ran, each
            step's timing and every check.
          </p>
        </Section>

        <Section title="Keyboard">
          <ul className="flex flex-col gap-1.5">
            <li>
              <Key>Enter</Key> send · <Key>Shift</Key> + <Key>Enter</Key> new line
            </li>
            <li>
              <Key>↑</Key> / <Key>↓</Key> in an empty message box — recall earlier questions from this chat, like shell
              history
            </li>
          </ul>
        </Section>

        <Section title="Connecting your own database">
          <p>
            <span className="font-medium text-ink">Connect a database</span> (settings menu, bottom left) adds one at
            runtime: a name, a connection URL, and a sampling mode. The account must be strictly read-only — an account
            that can write data is refused after connecting, with the specific privileges that disqualified it. This is
            disabled unless the server sets ALLOW_UI_CONNECTIONS=true (local/self-hosted use only: it lets anyone who
            can reach the server make it connect to any address they choose, so it is never enabled on a public
            deployment).
          </p>
          <ul className="flex flex-col gap-1.5">
            <li>
              <span className="font-medium text-ink">Off</span> — structure only (table/column names, types, comments).
              No values ever leave the database.
            </li>
            <li>
              <span className="font-medium text-ink">Safe</span> (default) — off, plus numeric/date ranges and the
              complete set of values of short categorical columns. Free text and columns that look sensitive (email,
              password, phone, token, ...) are never sampled.
            </li>
            <li>
              <span className="font-medium text-ink">Full</span> — safe, plus a few truncated example values from other
              text columns. Still never sensitive-looking columns. Sampled values are sent to the LLM provider as schema
              context, so pick "off" for anything you would not want leaving the database at all.
            </li>
          </ul>
          <p>
            <span className="font-medium text-ink">Browse schema</span> shows what the profiler found on the selected
            database: tables, columns, types, inferred joins, and (depending on sampling) value ranges — the same
            information the model is given, so you can see exactly what it knows.
          </p>
        </Section>

        <Section title="The safety model">
          <p>
            The model's SQL is never trusted on its own. It is parsed and checked against a syntax tree before it can
            run (see Validate above), it executes on a database account that cannot write, and every query carries a
            timeout and a row limit enforced independently of the model. If any of that fails, the question fails
            safely — nothing is ever executed outside these guarantees.
          </p>
        </Section>

        <Section title="Reading an error">
          <dl className="flex flex-col gap-2">
            {ERRORS.map(([label, description]) => (
              <div key={label}>
                <dt className="inline font-medium text-ink">{label}</dt> <dd className="inline">— {description}</dd>
              </div>
            ))}
          </dl>
        </Section>
      </div>
    </Dialog>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2.5">
      <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
      {children}
    </section>
  )
}

function Key({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded-md border border-line bg-code px-1.5 py-0.5 font-mono text-[12px] text-ink">{children}</kbd>
  )
}
