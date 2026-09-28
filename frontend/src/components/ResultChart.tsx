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
import { columnLabel, formatCell } from '../lib/format'
import type { ChartSpec } from '../api/types'

const AXIS_STYLE = { fontFamily: 'var(--font-mono)', fontSize: 12, fill: 'var(--color-ink-dim)' }
const GRID_STROKE = 'var(--color-line)'

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
      <div className="border border-line px-4 py-3">
        <div className="font-mono text-[32px] leading-none text-ink tabular-nums">
          {formatCell(value, unit)}
        </div>
        <div className="mt-1 font-mono text-[12px] text-ink-faint">{label}</div>
      </div>
    )
  }

  const records = toRecords(columns, rows)

  if (chart.type === 'bar') {
    const category = chart.x ?? columns[0]
    const measures = chart.y
    return (
      <div className="h-72 border border-line p-2" role="img" aria-label={chart.reason}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={records} layout={chart.orientation === 'horizontal' ? 'vertical' : 'horizontal'} margin={{ top: 4, right: 8, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={GRID_STROKE} strokeDasharray="2 2" />
            {chart.orientation === 'horizontal' ? (
              <>
                <XAxis type="number" tick={AXIS_STYLE} stroke={GRID_STROKE} />
                <YAxis type="category" dataKey={category} tick={AXIS_STYLE} stroke={GRID_STROKE} width={110} />
              </>
            ) : (
              <>
                <XAxis dataKey={category} tick={AXIS_STYLE} stroke={GRID_STROKE} />
                <YAxis tick={AXIS_STYLE} stroke={GRID_STROKE} />
              </>
            )}
            <Tooltip content={<GridTooltip units={units} />} cursor={{ fill: 'var(--color-paper-raised)' }} />
            {measures.map((measure, index) => (
              <Bar key={measure} dataKey={measure} name={columnLabel(measure, units)} fill={SERIES_COLORS[index % SERIES_COLORS.length]} />
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
      <div className="h-72 border border-line p-2" role="img" aria-label={chart.reason}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={GRID_STROKE} strokeDasharray="2 2" />
            <XAxis dataKey={x} tick={AXIS_STYLE} stroke={GRID_STROKE} />
            <YAxis tick={AXIS_STYLE} stroke={GRID_STROKE} />
            <Tooltip content={<GridTooltip units={units} />} />
            {seriesKeys.map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={hasSeries ? key : key}
                name={hasSeries ? key : columnLabel(key, units)}
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
    <div className="h-72 border border-line p-2" role="img" aria-label={chart.reason}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 4, right: 8, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={GRID_STROKE} strokeDasharray="2 2" />
          <XAxis dataKey={x} name={columnLabel(x, units)} tick={AXIS_STYLE} stroke={GRID_STROKE} />
          <YAxis dataKey={y} name={columnLabel(y, units)} tick={AXIS_STYLE} stroke={GRID_STROKE} />
          <Tooltip content={<GridTooltip units={units} />} cursor={{ stroke: GRID_STROKE }} />
          <Scatter data={records} fill={SERIES_COLORS[0]} />
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
  payload?: { name?: string; value?: unknown; color?: string }[]
  units: Record<string, string>
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="border border-line bg-paper px-2 py-1 font-mono text-[12px] text-ink shadow-none">
      {payload.map((entry, index) => (
        <div key={index} style={{ color: entry.color }}>
          {entry.name}: {formatCell(entry.value, entry.name ? units[entry.name] : undefined)}
        </div>
      ))}
    </div>
  )
}
