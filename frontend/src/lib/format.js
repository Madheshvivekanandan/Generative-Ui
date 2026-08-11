/** Number formatting shared by every card, so a value looks the same everywhere. */

const UNITS = new Set(['USD', '%', 'count', 'none'])

export function normalizeUnit(unit) {
  return UNITS.has(unit) ? unit : 'none'
}

/** Compact form for axes and legends: $6.1M, 68.4%, 1.2k. */
export function formatCompact(value, unit = 'none') {
  if (!Number.isFinite(value)) return '—'
  const u = normalizeUnit(unit)
  if (u === '%') return `${round(value, 1)}%`

  const sign = value < 0 ? '-' : ''
  const abs = Math.abs(value)
  let body
  if (abs >= 1_000_000_000) body = `${round(abs / 1_000_000_000, 1)}B`
  else if (abs >= 1_000_000) body = `${round(abs / 1_000_000, 1)}M`
  else if (abs >= 1_000) body = `${round(abs / 1_000, 1)}k`
  else body = `${round(abs, 2)}`

  return u === 'USD' ? `${sign}$${body}` : `${sign}${body}`
}

/** Full precision for tooltips and stat values: $6,062,000. */
export function formatFull(value, unit = 'none') {
  if (!Number.isFinite(value)) return '—'
  const u = normalizeUnit(unit)
  if (u === '%') return `${round(value, 1)}%`

  const sign = value < 0 ? '-' : ''
  const abs = Math.abs(value)
  const body = abs.toLocaleString('en-US', { maximumFractionDigits: 2 })
  return u === 'USD' ? `${sign}$${body}` : `${sign}${body}`
}

function round(value, places) {
  return Number(value.toFixed(places))
}

/** Series colors are assigned by slot index and never cycled past the palette. */
export const SERIES_COLORS = [
  'var(--series-1)',
  'var(--series-2)',
  'var(--series-3)',
  'var(--series-4)',
  'var(--series-5)',
  'var(--series-6)',
]

export function seriesColor(index) {
  return SERIES_COLORS[index % SERIES_COLORS.length]
}
