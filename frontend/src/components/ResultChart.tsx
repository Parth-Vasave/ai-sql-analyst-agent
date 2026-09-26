import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Cell, ChartSpec } from "../api/types";
import { formatCell, formatTick } from "../format";

// Validated categorical palette, light (data-viz reference instance); slots in fixed order.
const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
const color = (slot: number): string => SERIES[slot % SERIES.length] ?? "#2a78d6";
const INK_3 = "#626b76";
const RULE = "#d5dbe2";
const AXIS_TICK = { fill: INK_3, fontSize: 12 };
const TOOLTIP_STYLE = {
  contentStyle: { border: `1px solid ${RULE}`, borderRadius: 3, fontSize: 13, padding: "6px 10px" },
  labelStyle: { color: "#1a1e24", fontWeight: 600 },
};

type Row = Record<string, Cell>;

function toObjects(columns: string[], rows: Cell[][]): Row[] {
  return rows.map((row) => Object.fromEntries(columns.map((c, i) => [c, row[i] ?? null])));
}

/** Long result (x, series, y) to one object per x with a key per series value. */
function pivot(rows: Row[], x: string, series: string, y: string): { data: Row[]; keys: string[] } {
  const keys = [...new Set(rows.map((r) => String(r[series])))];
  const byX = new Map<string, Row>();
  for (const row of rows) {
    const key = String(row[x]);
    const entry = byX.get(key) ?? { [x]: row[x] ?? null };
    entry[String(row[series])] = row[y] ?? null;
    byX.set(key, entry);
  }
  const data = [...byX.values()].sort((a, b) => Number(a[x]) - Number(b[x]));
  return { data, keys };
}

function Stat({ spec, rows, units }: { spec: ChartSpec; rows: Row[]; units: Record<string, string> }) {
  const measure = spec.y[0];
  const row = rows[0];
  if (!measure || !row) return null;
  const label = spec.label ? row[spec.label] : null;
  return (
    <figure className="py-1">
      <div className="tabular text-2xl font-semibold tracking-[-0.01em]">
        {formatCell(measure, row[measure] ?? null)}
        {units[measure] && <span className="ml-1.5 text-lg font-medium text-ink-2">{units[measure]}</span>}
      </div>
      <figcaption className="mt-0.5 text-sm text-ink-2">
        <code>{measure}</code>
        {label !== null && label !== undefined && <> for {String(label)}</>}
      </figcaption>
    </figure>
  );
}

interface ChartProps {
  spec: ChartSpec;
  columns: string[];
  rows: Cell[][];
  units?: Record<string, string>;
}

/** What the value axis measures, with its unit when the database states one. */
function Measured({ measures, units }: { measures: string[]; units: Record<string, string> }) {
  return (
    <figcaption className="mb-1 text-sm text-ink-2">
      {measures.map((m, i) => (
        <span key={m}>
          {i > 0 && ", "}
          <code>{m}</code>
          {units[m] ? ` in ${units[m]}` : ""}
        </span>
      ))}
    </figcaption>
  );
}

export function ResultChart({ spec, columns, rows, units = {} }: ChartProps) {
  const objects = toObjects(columns, rows);
  if (spec.type === "none" || objects.length === 0) return null;
  if (spec.type === "stat") return <Stat spec={spec} rows={objects} units={units} />;

  const x = spec.x ?? columns[0] ?? "";
  const measures = spec.y;
  const legend = measures.length > 1 || spec.series !== null;
  const describe = `${spec.type} chart of ${measures.join(", ")} by ${x}`;

  if (spec.type === "bar") {
    const horizontal = spec.orientation === "horizontal";
    const longest = Math.max(...objects.map((r) => String(r[x]).length));
    const height = horizontal ? Math.max(160, objects.length * (measures.length > 1 ? 44 : 30) + 48) : 280;
    return (
      <figure aria-label={describe} className="w-full">
        <Measured measures={measures} units={units} />
        <ResponsiveContainer width="100%" height={height}>
          <BarChart
            data={objects}
            layout={horizontal ? "vertical" : "horizontal"}
            barCategoryGap="22%"
            barGap={2}
            margin={{ top: 4, right: 16, bottom: 4, left: 4 }}
          >
            <CartesianGrid stroke={RULE} vertical={horizontal} horizontal={!horizontal} />
            {horizontal ? (
              <>
                <XAxis type="number" tick={AXIS_TICK} axisLine={{ stroke: RULE }} tickLine={false} tickFormatter={(v) => formatTick(measures[0] ?? "", v)} />
                <YAxis type="category" dataKey={x} tick={AXIS_TICK} axisLine={{ stroke: RULE }} tickLine={false} width={Math.min(180, longest * 7 + 12)} />
              </>
            ) : (
              <>
                <XAxis dataKey={x} tick={AXIS_TICK} axisLine={{ stroke: RULE }} tickLine={false} tickFormatter={(v) => formatTick(x, v)} />
                <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={56} tickFormatter={(v) => formatTick(measures[0] ?? "", v)} />
              </>
            )}
            <Tooltip {...TOOLTIP_STYLE} cursor={{ fill: "#edf1f5" }} formatter={(value, name) => [formatCell(String(name), value as Cell), String(name)]} />
            {legend && <Legend iconType="square" wrapperStyle={{ fontSize: 13, color: INK_3 }} />}
            {measures.map((measure, i) => (
              <Bar
                key={measure}
                dataKey={measure}
                fill={color(i)}
                radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
                maxBarSize={28}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </figure>
    );
  }

  if (spec.type === "line") {
    const measure = measures[0] ?? "";
    const { data, keys } = spec.series
      ? pivot(objects, x, spec.series, measure)
      : { data: objects, keys: measures };
    return (
      <figure aria-label={describe} className="w-full">
        <Measured measures={[measure]} units={units} />
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={RULE} vertical={false} />
            <XAxis dataKey={x} tick={AXIS_TICK} axisLine={{ stroke: RULE }} tickLine={false} tickFormatter={(v) => formatTick(x, v)} minTickGap={16} />
            <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={56} tickFormatter={(v) => formatTick(measure, v)} />
            <Tooltip {...TOOLTIP_STYLE} labelFormatter={(v) => formatCell(x, v as Cell)} formatter={(value, name) => [formatCell(measure, value as Cell), String(name)]} />
            {legend && <Legend iconType="plainline" wrapperStyle={{ fontSize: 13, color: INK_3 }} />}
            {keys.map((key, i) => (
              <Line
                key={key}
                type="linear"
                dataKey={key}
                stroke={color(i)}
                strokeWidth={2}
                dot={data.length <= 24 ? { r: 3, strokeWidth: 0, fill: color(i) } : false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: "#ffffff" }}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </figure>
    );
  }

  // scatter: one point per row, x and y are both measures
  const yMeasure = measures[0] ?? "";
  return (
    <figure aria-label={`scatter plot of ${yMeasure} against ${x}`} className="w-full">
      <Measured measures={[yMeasure, x]} units={units} />
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 4 }}>
          <CartesianGrid stroke={RULE} />
          <XAxis type="number" dataKey={x} name={x} tick={AXIS_TICK} axisLine={{ stroke: RULE }} tickLine={false} tickFormatter={(v) => formatTick(x, v)} />
          <YAxis type="number" dataKey={yMeasure} name={yMeasure} tick={AXIS_TICK} axisLine={false} tickLine={false} width={56} tickFormatter={(v) => formatTick(yMeasure, v)} />
          <Tooltip
            {...TOOLTIP_STYLE}
            cursor={{ stroke: RULE }}
            content={({ payload }) => {
              const point = payload?.[0]?.payload as Row | undefined;
              if (!point) return null;
              return (
                <div className="rounded-sm border border-rule bg-surface px-2.5 py-1.5 text-[13px]">
                  {spec.label && <div className="font-semibold">{String(point[spec.label])}</div>}
                  <div className="tabular text-ink-2">
                    {x} {formatCell(x, point[x] ?? null)}, {yMeasure} {formatCell(yMeasure, point[yMeasure] ?? null)}
                  </div>
                </div>
              );
            }}
          />
          <Scatter data={objects} fill={color(0)} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </figure>
  );
}
