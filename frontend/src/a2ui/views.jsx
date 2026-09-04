/**
 * The six data-visualisation views, as ordinary React components.
 *
 * These know nothing about A2UI. They take plain resolved props and draw
 * pixels; `catalog.jsx` is what binds them to the protocol. Keeping the split
 * means the charts stay testable and could be reused behind any transport.
 *
 * Every field is read through `./coerce` rather than indexed into directly:
 * A2UI's binder hands over whatever the data model holds at that path, and an
 * agent wrote that model. A view returns `<EmptyState/>` when there is nothing
 * to draw -- empty is a normal outcome, not an error.
 */

import { useId } from 'react'
import {
  Area,
  Bar,
  BarChart as RechartsBarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import ChartTooltip from '../components/ChartTooltip'
import { formatCompact, formatFull, normalizeUnit, seriesColor } from '../lib/format'
import { arr, num, str, toChartRows } from './coerce'

const CHART_HEIGHT = 260

// Mirrors the backend's own donut limit; change both together.
const MAX_SLICES = 6

function AxisLabels({ xLabel, yLabel }) {
  if (!xLabel && !yLabel) return null
  return (
    <p className="card-sub" style={{ marginTop: 8 }}>
      {[yLabel, xLabel].filter(Boolean).join(' by ')}
    </p>
  )
}

/* Recessive axes: no axis or tick lines at all -- the dashed horizontal grid
   carries alignment, and the ticks are small muted labels. */
const axisProps = {
  tickLine: false,
  axisLine: false,
  tick: { fill: 'var(--text-muted)', fontSize: 11 },
  tickMargin: 8,
}

export function EmptyState({ label = 'No data to plot for this request.' }) {
  return <div className="empty">{label}</div>
}

export function StatCardView({ title, value, unit, deltaPct, deltaDirection, caption }) {
  const resolvedUnit = normalizeUnit(unit)
  const resolvedValue = num(value)
  const delta = num(deltaPct)
  const direction = ['up', 'down', 'flat'].includes(deltaDirection) ? deltaDirection : 'flat'
  const arrow = { up: '▲', down: '▼', flat: '■' }[direction]

  return (
    <>
      {/* A tile carries its own heading -- the compiler emits no separate
          title component above it, so this is the card's only name. */}
      <h3 className="stat-label">{str(title, 'Value')}</h3>
      <div className="stat-value">
        {resolvedValue === null ? '—' : formatFull(resolvedValue, resolvedUnit)}
      </div>
      <div className="stat-foot">
        {delta !== null && delta !== 0 ? (
          <span className={`delta delta-${direction}`}>
            {arrow} {Math.abs(delta).toFixed(1)}%
          </span>
        ) : null}
        <span>{str(caption)}</span>
      </div>
    </>
  )
}

export function LineChartView({ series: rawSeries, unit, xLabel, yLabel }) {
  const resolvedUnit = normalizeUnit(unit)
  const { series, rows } = toChartRows(rawSeries)
  // Gradient ids are document-global in SVG; several charts can be on the
  // canvas at once, so each card's gradient gets its own id.
  const gradientId = useId()
  if (!rows.length) return <EmptyState />

  // A soft fill under the line reads as "amount", so it is reserved for the
  // single-series case -- stacked translucent fills over each other go muddy.
  const hasAreaFill = series.length === 1

  return (
    <>
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <ComposedChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          {hasAreaFill ? (
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={seriesColor(0)} stopOpacity={0.22} />
                <stop offset="100%" stopColor={seriesColor(0)} stopOpacity={0} />
              </linearGradient>
            </defs>
          ) : null}
          <CartesianGrid stroke="var(--grid)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="x" {...axisProps} />
          <YAxis {...axisProps} width={62} tickFormatter={(v) => formatCompact(v, resolvedUnit)} />
          <Tooltip
            content={<ChartTooltip unit={resolvedUnit} />}
            cursor={{ stroke: 'var(--axis)' }}
          />
          {series.length > 1 ? <Legend iconType="circle" iconSize={8} /> : null}
          {hasAreaFill ? (
            <Area
              dataKey="s0"
              type="monotone"
              fill={`url(#${gradientId})`}
              stroke="none"
              connectNulls
              legendType="none"
              tooltipType="none"
            />
          ) : null}
          {series.map((entry, index) => (
            <Line
              key={entry.name}
              type="monotone"
              dataKey={`s${index}`}
              name={entry.name}
              stroke={seriesColor(index)}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
              connectNulls
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
      <AxisLabels xLabel={str(xLabel)} yLabel={str(yLabel)} />
    </>
  )
}

export function BarChartView({ series: rawSeries, unit, xLabel, yLabel, stacked }) {
  const resolvedUnit = normalizeUnit(unit)
  const { series, rows } = toChartRows(rawSeries)
  if (!rows.length) return <EmptyState />

  const isStacked = stacked === true && series.length > 1

  return (
    <>
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <RechartsBarChart
          data={rows}
          margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
          barCategoryGap="22%"
        >
          <CartesianGrid stroke="var(--grid)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="x" {...axisProps} interval={0} />
          <YAxis {...axisProps} width={62} tickFormatter={(v) => formatCompact(v, resolvedUnit)} />
          <Tooltip content={<ChartTooltip unit={resolvedUnit} />} cursor={{ fill: 'var(--hover)' }} />
          {series.length > 1 ? <Legend iconType="circle" iconSize={8} /> : null}
          {series.map((entry, index) => (
            <Bar
              key={entry.name}
              dataKey={`s${index}`}
              name={entry.name}
              fill={seriesColor(index)}
              stackId={isStacked ? 'stack' : undefined}
              radius={[4, 4, 0, 0]}
              stroke="var(--surface)"
              strokeWidth={isStacked ? 2 : 0}
            />
          ))}
        </RechartsBarChart>
      </ResponsiveContainer>
      <AxisLabels xLabel={str(xLabel)} yLabel={str(yLabel)} />
    </>
  )
}

export function DonutChartView({ slices: rawSlices, unit }) {
  const resolvedUnit = normalizeUnit(unit)
  const slices = arr(rawSlices)
    .map((slice, index) => ({
      label: str(slice?.label, `Slice ${index + 1}`),
      value: num(slice?.value) ?? 0,
    }))
    .filter((slice) => slice.value > 0)
    .slice(0, MAX_SLICES)

  if (slices.length < 2) return <EmptyState />

  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <PieChart>
        <Pie
          data={slices}
          dataKey="value"
          nameKey="label"
          innerRadius="52%"
          outerRadius="78%"
          paddingAngle={2}
          stroke="var(--surface)"
          strokeWidth={2}
        >
          {slices.map((slice, index) => (
            <Cell key={slice.label} fill={seriesColor(index)} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip unit={resolvedUnit} />} />
        <Legend iconType="circle" iconSize={8} />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function DataTableView({ columns: rawColumns, rows: rawRows }) {
  const columns = arr(rawColumns).map((column, index) => ({
    key: str(column?.key, `c${index}`),
    label: str(column?.label, `Column ${index + 1}`),
    align: column?.align === 'right' ? 'right' : 'left',
  }))
  const rows = arr(rawRows).filter(Array.isArray)

  if (!columns.length || !rows.length) return <EmptyState />

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={column.align === 'right' ? 'align-right' : undefined}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column, cellIndex) => (
                <td
                  key={column.key}
                  className={column.align === 'right' ? 'align-right' : undefined}
                >
                  {str(row[cellIndex], '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function TextNoteView({ body }) {
  return <p className="note-body">{str(body, 'No details provided.')}</p>
}
