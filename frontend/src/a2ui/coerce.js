/**
 * Readers for untrusted payloads.
 *
 * Everything a view renders arrives from an agent, via A2UI's data model. A
 * missing field, a `null`, or a string where a number belongs is expected
 * input, not an exceptional case -- so nothing here throws. A value that cannot
 * be used becomes a fallback the caller can render.
 *
 * These live apart from the views so the coercion rules are readable in one
 * place, and so a new view has an obvious set of readers to reach for rather
 * than indexing into the payload directly.
 */

const MAX_SERIES = 4

/** A string, or `fallback` for anything else. */
export const str = (value, fallback = '') => (typeof value === 'string' ? value : fallback)

/** A finite number, or `null` -- which every view renders as an em dash. */
export const num = (value) => (typeof value === 'number' && Number.isFinite(value) ? value : null)

/** An array, or an empty one. Never `undefined`, so `.map` is always safe. */
export const arr = (value) => (Array.isArray(value) ? value : [])

/**
 * Turn `[{name, points:[{x,y}]}]` into the row-per-x shape Recharts wants.
 *
 * Series are capped at MAX_SERIES to match the backend's own limit, and any
 * series with no usable points is dropped rather than drawn as a gap.
 * Categories are collected in first-seen order, so a series that skips a month
 * still lines up with one that does not.
 */
export function toChartRows(rawSeries) {
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
