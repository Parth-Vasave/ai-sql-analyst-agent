const KEYWORDS = new Set(
  (
    "select from where join left right inner outer full cross on and or not in is null as with group by order " +
    "having limit offset distinct union all except intersect case when then else end asc desc between like ilike " +
    "exists nulls first last over partition filter within recursive"
  ).split(" "),
);

const TOKEN = /('(?:[^']|'')*'|"[^"]*"|\b\d+(?:\.\d+)?\b|\b[A-Za-z_][A-Za-z0-9_]*\b|\s+|.)/g;

/** SQL with keywords set in bold; no colour coding, the query is read, not decorated. */
export function SqlBlock({ sql }: { sql: string }) {
  const tokens = sql.match(TOKEN) ?? [sql];
  return (
    <pre className="overflow-x-auto rounded-sm border border-rule bg-well px-3 py-2.5 text-[0.8125rem] leading-relaxed whitespace-pre-wrap text-ink">
      <code>
        {tokens.map((token, i) =>
          KEYWORDS.has(token.toLowerCase()) ? (
            <b key={i} className="font-semibold">
              {token.toUpperCase()}
            </b>
          ) : token.startsWith("'") ? (
            <span key={i} className="text-ink-2">
              {token}
            </span>
          ) : (
            token
          ),
        )}
      </code>
    </pre>
  );
}
