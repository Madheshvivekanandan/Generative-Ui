import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import Card from './Card'
import ChartTooltip from './ChartTooltip'
import { formatCompact, formatFull, normalizeUnit, seriesColor } from '../lib/format'

const CHART_HEIGHT = 260
const MAX_SERIES = 4
const MAX_SLICES = 6

/* ---------- defensive readers -------------------------------------------
   The backend validates against the schema, but this renderer is the last
   line of defense: it assumes every field could be missing or the wrong
   type and coerces rather than throws.                                    */

const str = (value, fallback = '') => (typeof value === 'string' ? value : fallback)
const num = (value) => (typeof value === 'number' && Number.isFinite(value) ? value : null)
const arr = (value) => (Array.isArray(value) ? value : [])

/** Turn [{name, points:[{x,y}]}] into the row-per-x shape Recharts wants. */
function toChartRows(rawSeries) {
  const series = arr(rawSeries)
    .slice(0, MAX_SERIES)
    .map((entry, index) => ({
      name: str(entry?.name, `Series ${index + 1}`),
      points: arr(entry?.points),
    }))
    .filter((entry) => entry.points.length > 0)

  const xValues = []
  for (const entry of series) {
    for (const point of entry.points) {
      const x = str(point?.x)
      if (x && !xValues.includes(x)) xValues.push(x)
    }
  }

  const rows = xValues.map((x) => {
    const row = { x }
    series.forEach((entry, index) => {
      const match = entry.points.find((point) => str(point?.x) === x)
      row[`s${index}`] = match ? num(match.y) : null
    })
    return row
  })

  return { series, rows }
}

function AxisLabels({ xLabel, yLabel }) {
  if (!xLabel && !yLabel) return null
  return (
    <p className="card-sub" style={{ marginTop: 8 }}>
      {[yLabel, xLabel].filter(Boolean).join(' by ')}
    </p>
  )
}

const axisProps = {
  stroke: 'var(--axis)',
  tickLine: false,
  axisLine: { stroke: 'var(--axis)' },
}

/* ---------- the six renderers ------------------------------------------ */

function StatCardView({ component }) {
  const unit = normalizeUnit(component.unit)
  const value = num(component.value)
  const delta = num(component.delta_pct)
  const direction = ['up', 'down', 'flat'].includes(component.delta_direction)
    ? component.delta_direction
    : 'flat'
  const arrow = { up: '▲', down: '▼', flat: '■' }[direction]

  return (
    <>
      <div className="stat-label">{str(component.label, 'Value')}</div>
      <div className="stat-value">{value === null ? '—' : formatFull(value, unit)}</div>
      <div className="stat-foot">
        {delta !== null && delta !== 0 ? (
          <span className={`delta delta-${direction}`}>
            {arrow} {Math.abs(delta).toFixed(1)}%
          </span>
        ) : null}
        <span>{str(component.caption)}</span>
      </div>
    </>
  )
}

function LineChartView({ component }) {
  const unit = normalizeUnit(component.unit)
  const { series, rows } = toChartRows(component.series)
  if (!rows.length) return <EmptyState />

  return (
    <>
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="x" {...axisProps} />
          <YAxis {...axisProps} width={62} tickFormatter={(v) => formatCompact(v, unit)} />
          <Tooltip content={<ChartTooltip unit={unit} />} cursor={{ stroke: 'var(--axis)' }} />
          {series.length > 1 ? <Legend iconType="plainline" /> : null}
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
        </LineChart>
      </ResponsiveContainer>
      <AxisLabels xLabel={str(component.x_label)} yLabel={str(component.y_label)} />
    </>
  )
}

function BarChartView({ component }) {
  const unit = normalizeUnit(component.unit)
  const { series, rows } = toChartRows(component.series)
  if (!rows.length) return <EmptyState />

  const stacked = component.stacked === true && series.length > 1

  return (
    <>
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <BarChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }} barCategoryGap="22%">
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="x" {...axisProps} interval={0} tickMargin={6} />
          <YAxis {...axisProps} width={62} tickFormatter={(v) => formatCompact(v, unit)} />
          <Tooltip content={<ChartTooltip unit={unit} />} cursor={{ fill: 'var(--hover)' }} />
          {series.length > 1 ? <Legend iconType="square" /> : null}
          {series.map((entry, index) => (
            <Bar
              key={entry.name}
              dataKey={`s${index}`}
              name={entry.name}
              fill={seriesColor(index)}
              stackId={stacked ? 'stack' : undefined}
              radius={[4, 4, 0, 0]}
              stroke="var(--surface)"
              strokeWidth={stacked ? 2 : 0}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <AxisLabels xLabel={str(component.x_label)} yLabel={str(component.y_label)} />
    </>
  )
}

function DonutChartView({ component }) {
  const unit = normalizeUnit(component.unit)
  const slices = arr(component.slices)
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
        <Tooltip content={<ChartTooltip unit={unit} />} />
        <Legend iconType="square" />
      </PieChart>
    </ResponsiveContainer>
  )
}

function DataTableView({ component }) {
  const columns = arr(component.columns).map((column, index) => ({
    key: str(column?.key, `c${index}`),
    label: str(column?.label, `Column ${index + 1}`),
    align: column?.align === 'right' ? 'right' : 'left',
  }))
  const rows = arr(component.rows).filter(Array.isArray)

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

function TextNoteView({ component }) {
  return <p className="note-body">{str(component.body, 'No details provided.')}</p>
}

function EmptyState() {
  return <div className="empty">No data to plot for this request.</div>
}

/* ---------- dispatch ---------------------------------------------------- */

/** A whitelist, not a lookup with a dynamic key: an unknown type renders a
    note instead of throwing. */
const RENDERERS = {
  stat_card: StatCardView,
  line_chart: LineChartView,
  bar_chart: BarChartView,
  donut_chart: DonutChartView,
  data_table: DataTableView,
  text_note: TextNoteView,
}

/** Charts and tables get the wide slot; a stat card is one column. */
const WIDE_TYPES = new Set(['line_chart', 'bar_chart', 'data_table'])

export default function ComponentRenderer({ component, subtitle, onDismiss, generated }) {
  if (!component || typeof component !== 'object') {
    return (
      <Card title="Nothing to render" onDismiss={onDismiss} generated={generated}>
        <p className="note-body">The server returned an empty response.</p>
      </Card>
    )
  }

  const View = Object.prototype.hasOwnProperty.call(RENDERERS, component.type)
    ? RENDERERS[component.type]
    : null

  if (!View) {
    return (
      <Card title="Unsupported component" onDismiss={onDismiss} generated={generated}>
        <p className="note-body">
          The server asked for a <code>{String(component.type)}</code>, which this dashboard doesn't
          know how to draw.
        </p>
      </Card>
    )
  }

  return (
    <Card
      title={str(component.title, 'Untitled')}
      subtitle={subtitle}
      onDismiss={onDismiss}
      generated={generated}
      wide={WIDE_TYPES.has(component.type)}
    >
      <View component={component} />
    </Card>
  )
}
