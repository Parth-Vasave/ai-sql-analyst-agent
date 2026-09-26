import type { Cell } from "../api/types";
import { formatCell, isTemporal } from "../format";

interface Props {
  columns: string[];
  rows: Cell[][];
  caption: string;
  units?: Record<string, string>;
}

export function ResultTable({ columns, rows, caption, units = {} }: Props) {
  if (columns.length === 0) return null;
  return (
    <div className="inline-block max-h-96 max-w-full overflow-auto rounded-sm border border-rule align-top">
      <table className="min-w-[16rem] border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 bg-well">
          <tr>
            {columns.map((column, i) => (
              <th
                key={`${column}-${i}`}
                scope="col"
                className={`border-b border-rule px-3 py-1.5 font-mono text-xs font-semibold whitespace-nowrap text-ink-2 ${
                  rows.some((r) => typeof r[i] === "number") && !isTemporal(column) ? "text-right" : "text-left"
                }`}
              >
                {column}
                {units[column] && <span className="ml-1 font-sans font-normal text-ink-3">{units[column]}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-3 text-ink-2">
                No rows.
              </td>
            </tr>
          )}
          {rows.map((row, r) => (
            <tr key={r} className="border-b border-rule last:border-b-0 hover:bg-well/60">
              {row.map((value, c) => (
                <td
                  key={c}
                  className={`px-3 py-1.5 whitespace-nowrap ${typeof value === "number" ? "tabular" : ""} ${
                    typeof value === "number" && !isTemporal(columns[c] ?? "") ? "text-right" : ""
                  } ${
                    value === null ? "text-ink-3" : ""
                  }`}
                >
                  {formatCell(columns[c] ?? "", value)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
