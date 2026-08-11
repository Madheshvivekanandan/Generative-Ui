import { formatFull } from '../lib/format'

/** Shared hover tooltip. Every chart ships one -- an SVG chart is interactive. */
export default function ChartTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null

  return (
    <div className="tooltip">
      <div className="tooltip-x">{label}</div>
      {payload.map((entry) => (
        <div className="tooltip-row" key={entry.dataKey ?? entry.name}>
          <span className="tooltip-swatch" style={{ background: entry.color }} />
          <span>{entry.name}</span>
          <span className="tooltip-val">{formatFull(entry.value, unit)}</span>
        </div>
      ))}
    </div>
  )
}
