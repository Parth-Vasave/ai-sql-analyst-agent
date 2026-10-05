import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { pivotBySeries, statValue, toRecords, SERIES_COLORS } from '../lib/chartData'
import { formatCell } from '../lib/format'
import type { ChartSpec } from '../api/types'

const AXIS_STYLE = { fontFamily: 'var(--font-sans)', fontSize: 12, fill: 'var(--color-ink-faint)' }
const GRID_STROKE = 'var(--color-line)'
// Axis ticks group thousands like the result grid does, so 12000 on the axis reads as 12,000 in the table.
const formatTick = (value: unknown) => (typeof value === 'number' ? value.toLocaleString('en-US') : String(value))
/** The value axis carries the measure's unit (e.g. "2,800 Mt") when every plotted measure shares one. */
function valueTick(measures: string[], units: Record<string, string>) {
  const unitSet = new Set(measures.map((m) => units[m]))
  const unit = unitSet.size === 1 ? [...unitSet][0] : undefined
  return (value: unknown) => (unit ? `${formatTick(value)} ${unit}` : formatTick(value))
}
/** Tooltip names read as words, without the unit the value already carries: "co2_mt" becomes "co2". */
function seriesName(column: string, units: Record<string, string>): string {
  const unit = units[column]
  const words = column.replace(/_/g, ' ')
  return unit ? words.replace(new RegExp(`\\s${unit}$`, 'i'), '') : words
}

interface ResultChartProps {
  chart: ChartSpec
  columns: string[]
  rows: unknown[][]
  units: Record<string, string>
}

export function ResultChart({ chart, columns, rows, units }: ResultChartProps) {
  if (chart.type === 'none') return null

  if (chart.type === 'stat') {
    const { value, label } = statValue(chart, columns, rows)
    const unit = chart.y[0] ? units[chart.y[0]] : undefined
    return (
      <div className="inline-flex flex-col rounded-xl border border-line px-5 py-4">
        <div className="text-[32px] leading-none font-semibold tracking-tight text-ink tabular-nums">{formatCell(value, unit)}</div>
        <div className="mt-2 text-[13px] text-ink-faint">{label}</div>
      </div>
    )
  }

  const records = toRecords(columns, rows)

  if (chart.type === 'bar') {
    const category = chart.x ?? columns[0]
    const measures = chart.y
    return (
      <div className="h-72 rounded-xl border border-line p-3 pr-4" role="img" aria-label={chart.reason}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={records} layout={chart.orientation === 'horizontal' ? 'vertical' : 'horizontal'} margin={{ top: 4, right: 8, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={GRID_STROKE} vertical={chart.orientation === 'horizontal'} horizontal={chart.orientation !== 'horizontal'} />
            {chart.orientation === 'horizontal' ? (
              <>
                <XAxis type="number" tick={AXIS_STYLE} stroke={GRID_STROKE} tickFormatter={valueTick(measures, units)} />
                <YAxis type="category" dataKey={category} tick={AXIS_STYLE} stroke={GRID_STROKE} width={110} tickLine={false} />
              </>
            ) : (
              <>
                <XAxis dataKey={category} tick={AXIS_STYLE} stroke={GRID_STROKE} />
                <YAxis tick={AXIS_STYLE} stroke={GRID_STROKE} tickFormatter={valueTick(measures, units)} width={80} />
              </>
            )}
            <Tooltip content={<GridTooltip units={units} />} cursor={{ fill: 'var(--color-raised)', opacity: 0.6 }} />
            {measures.map((measure, index) => (
              <Bar
                key={measure}
                dataKey={measure}
                name={seriesName(measure, units)}
                isAnimationActive={false}
                fill={SERIES_COLORS[index % SERIES_COLORS.length]}
                radius={chart.orientation === 'horizontal' ? [0, 4, 4, 0] : [4, 4, 0, 0]}
                maxBarSize={36}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    )
  }

  if (chart.type === 'line') {
    const x = chart.x ?? columns[0]
    const y = chart.y[0] ?? columns[1]
    const hasSeries = Boolean(chart.series)
    const { data, seriesKeys } = hasSeries
      ? pivotBySeries(records, x, y, chart.series!)
      : { data: records, seriesKeys: chart.y }
    return (
      <div className="h-72 rounded-xl border border-line p-3 pr-4" role="img" aria-label={chart.reason}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <XAxis dataKey={x} tick={AXIS_STYLE} stroke={GRID_STROKE} />
            <YAxis tick={AXIS_STYLE} stroke={GRID_STROKE} tickFormatter={valueTick([y], units)} width={80} />
            <Tooltip content={<GridTooltip units={units} />} />
            {seriesKeys.map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={hasSeries ? key : key}
                name={hasSeries ? key : seriesName(key, units)}
                isAnimationActive={false}
                stroke={SERIES_COLORS[index % SERIES_COLORS.length]}
                dot={data.length <= 20}
                strokeWidth={1.75}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    )
  }

  // scatter
  const x = chart.x ?? columns[0]
  const y = chart.y[0] ?? columns[1]
  return (
    <div className="h-72 rounded-xl border border-line p-3 pr-4" role="img" aria-label={chart.reason}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 4, right: 8, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={GRID_STROKE} vertical={false} />
          <XAxis dataKey={x} name={seriesName(x, units)} tick={AXIS_STYLE} stroke={GRID_STROKE} tickFormatter={valueTick([x], units)} />
          <YAxis dataKey={y} name={seriesName(y, units)} tick={AXIS_STYLE} stroke={GRID_STROKE} tickFormatter={valueTick([y], units)} width={80} />
          <Tooltip content={<GridTooltip units={units} />} cursor={{ stroke: GRID_STROKE }} />
          <Scatter data={records} fill={SERIES_COLORS[0]} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

function GridTooltip({
  active,
  payload,
  units,
}: {
  active?: boolean
  payload?: { name?: string; dataKey?: unknown; value?: unknown; color?: string }[]
  units: Record<string, string>
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[13px] text-ink shadow-[var(--shadow-menu)] tabular-nums">
      {payload.map((entry, index) => (
        <div key={index} style={{ color: entry.color }}>
          {entry.name}: {formatCell(entry.value, typeof entry.dataKey === 'string' ? units[entry.dataKey] : undefined)}
        </div>
      ))}
    </div>
  )
}
