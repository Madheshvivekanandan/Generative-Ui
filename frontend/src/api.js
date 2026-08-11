/**
 * The entire backend contract, in one place.
 *
 * Both calls resolve rather than throw on a bad response: the dashboard's
 * rule is that nothing the server does can break the render.
 */

async function getJson(url, options) {
  const response = await fetch(url, options)
  const text = await response.text()

  let body
  try {
    body = JSON.parse(text)
  } catch {
    throw new Error(`Server returned non-JSON (HTTP ${response.status})`)
  }

  if (!response.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail : `HTTP ${response.status}`
    throw new Error(detail)
  }
  return body
}

/** GET /api/dashboard -> the mock dataset rendered on load. */
export function fetchDashboard() {
  return getJson('/api/dashboard')
}

/**
 * POST /api/generate -> { ok, explanation, component, fallback, error }
 *
 * The backend already converts its own failures into a text_note component,
 * so the only thing left to handle here is the network itself being down.
 */
export async function generateComponent(message) {
  try {
    return await getJson('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    })
  } catch (error) {
    return {
      ok: false,
      fallback: true,
      explanation: "Couldn't reach the server.",
      follow_ups: [],
      error: error.message,
      component: {
        type: 'text_note',
        title: 'Backend unreachable',
        body: `${error.message}. Is the FastAPI server running on port 8000?`,
      },
    }
  }
}
