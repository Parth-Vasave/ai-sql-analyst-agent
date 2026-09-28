import type { ReactNode } from 'react'

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
  ['no database is ready', 'no connected database passed its read-only check. Connect one with :connect, or ask the person running this instance to check DATABASE_URL / databases.toml.'],
  ['rejected: not read-only', 'the account you connected can write data (insert/update/create/etc). Only strictly read-only accounts are accepted — create one and reconnect.'],
  ['no LLM configured', 'the server has no LLM_API_KEY set. Questions cannot be answered until the operator sets one.'],
  ['rate limited', 'you (or the whole server) hit the configured question budget. The banner shows a countdown; retry after it reaches zero.'],
  ['could not reach the API', 'the backend is not running or is unreachable from this page — check that it is up and that VITE_API_PROXY_TARGET / VITE_API_BASE_URL points at it.'],
] as const

export function HelpPanel({ onClose }: HelpPanelProps) {
  return (
    <div className="border-b border-line bg-paper-raised px-4 py-4 sm:px-6">
      <div className="mx-auto flex max-w-4xl flex-col gap-5 font-mono text-[14px] leading-relaxed">
        <div className="flex items-center justify-between gap-2">
          <p className="text-ink">
            <span className="text-accent">{':help'}</span> guide
          </p>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 px-2 py-0.5 text-ink-faint transition-colors hover:text-ink-dim"
          >
            close
          </button>
        </div>

        <Section title="asking questions">
          <p className="text-ink-dim">
            Type a question about the connected database in plain language and press Enter. Be as
            specific as a real analytical question would be — a country, a year, a metric, a
            comparison. If your question is ambiguous, the model asks a clarifying question instead
            of guessing; if it can answer with a stated assumption instead, it will (e.g. "latest
            available year").
          </p>
          <p className="text-ink-dim">
            Follow-ups work: "and Germany?" after a question about France reuses the last few turns
            of context. Up to 3 prior turns are sent with each new question; the server itself keeps
            no conversation state between requests.
          </p>
        </Section>

        <Section title="what happens to your question">
          <ol className="space-y-2">
            {PIPELINE_STEPS.map(([label, description]) => (
              <li key={label} className="flex gap-3">
                <span className="text-accent shrink-0">[{label}]</span>
                <span className="text-ink-dim">{description}</span>
              </li>
            ))}
          </ol>
        </Section>

        <Section title="keyboard shortcuts">
          <ul className="space-y-1 text-ink-dim">
            <li>
              <Key>↑</Key> / <Key>↓</Key> in the question field — recall earlier questions from this
              session, like shell history.
            </li>
            <li>
              <Key>Enter</Key> — submit the question.
            </li>
          </ul>
        </Section>

        <Section title="connecting your own database">
          <p className="text-ink-dim">
            <span className="text-accent">:connect</span> adds a database at runtime: a name, a
            connection URL, and a sampling mode. The account must be strictly read-only — an account
            that can write data is refused after connecting, with the specific privileges that
            disqualified it. This is disabled unless the server sets
            ALLOW_UI_CONNECTIONS=true (local/self-hosted use only: it lets anyone who can reach the
            server make it connect to any address they choose, so it is never enabled on a public
            deployment).
          </p>
          <ul className="space-y-1 text-ink-dim">
            <li>
              <span className="text-ink">off</span> — structure only (table/column names, types,
              comments). No values ever leave the database.
            </li>
            <li>
              <span className="text-ink">safe</span> (default) — off, plus numeric/date ranges and
              the complete set of values of short categorical columns. Free text and columns that
              look sensitive (email, password, phone, token, ...) are never sampled.
            </li>
            <li>
              <span className="text-ink">full</span> — safe, plus a few truncated example values
              from other text columns. Still never sensitive-looking columns. Sampled values are
              sent to the LLM provider as schema context, so pick "off" for anything you would not
              want leaving the database at all.
            </li>
          </ul>
          <p className="text-ink-dim">
            <span className="text-accent">:schema</span> shows what the profiler found on the
            currently selected database: tables, columns, types, inferred joins, and (depending on
            sampling) value ranges — the same information the model is given, so you can see exactly
            what it knows.
          </p>
        </Section>

        <Section title="setting the LLM key">
          <p className="text-ink-dim">
            <span className="text-accent">:llm-key</span> sets, replaces or removes the API key the
            server uses to answer questions (any OpenAI-compatible provider — Gemini, Groq,
            OpenRouter, ...). Like :connect, this is disabled unless the server sets
            ALLOW_UI_LLM_KEY=true (local/self-hosted use only: it lets anyone who can reach the
            server replace or clear the operator's key). The key itself is never shown back to you
            or to anyone else, only whether one is configured and which provider/model it targets.
          </p>
        </Section>

        <Section title="the safety model">
          <p className="text-ink-dim">
            The LLM's SQL is never trusted on its own. It is parsed and checked against a syntax
            tree before it can run (see [validate] above), it executes on a database account that
            cannot write, and every query carries a timeout and a row limit enforced independently
            of the model. If any of that fails, the question fails safely — nothing is ever executed
            outside these guarantees.
          </p>
        </Section>

        <Section title="reading an error">
          <ul className="space-y-2">
            {ERRORS.map(([label, description]) => (
              <li key={label} className="flex gap-3">
                <span className="text-accent shrink-0">{label}</span>
                <span className="text-ink-dim">{description}</span>
              </li>
            ))}
          </ul>
        </Section>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-[12px] tracking-wide text-ink-faint uppercase">{title}</h2>
      {children}
    </section>
  )
}

function Key({ children }: { children: ReactNode }) {
  return <kbd className="border border-line bg-paper px-1 py-0.5 text-[12px] text-ink-dim">{children}</kbd>
}
