/**
 * The transport: A2UI messages over server-sent events.
 *
 * A2UI itself is transport-agnostic -- the spec's own MIME type is
 * `application/a2ui+json` carrying newline-delimited messages. SSE carries the
 * same objects one per frame and is the shape a browser can read without a
 * custom protocol, so that is what the backend speaks.
 *
 * `EventSource` is not usable here because it cannot POST, and a turn needs a
 * request body. So we read the response body ourselves and parse frames.
 *
 * Two channels share the connection, distinguished by the SSE `event:` name:
 *   a2ui — a real A2UI message, handed straight to the MessageProcessor
 *   meta — this app's own chat metadata (explanation, follow-ups). Not A2UI.
 *   open — the surface id for this turn, sent first so the UI can slot it in.
 *   done — the turn is over.
 */

/** Split a raw SSE buffer into complete frames, returning the unconsumed tail. */
function drainFrames(buffer, onFrame) {
  let rest = buffer
  let boundary = rest.indexOf('\n\n')

  while (boundary !== -1) {
    const frame = rest.slice(0, boundary)
    rest = rest.slice(boundary + 2)

    let name = 'message'
    const dataLines = []
    for (const line of frame.split('\n')) {
      if (line.startsWith('event:')) name = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }

    if (dataLines.length) {
      try {
        onFrame(name, JSON.parse(dataLines.join('\n')))
      } catch {
        // A malformed frame is dropped rather than aborting the turn: the
        // authoritative pass at the end of the stream will resend the state.
      }
    }

    boundary = rest.indexOf('\n\n')
  }

  return rest
}

/**
 * POST `body` to `url` and dispatch the A2UI stream that comes back.
 *
 * Resolves when the stream ends. Never rejects: a transport failure is
 * reported through `onError` so the caller has one place to handle "the turn
 * did not work", whatever the reason.
 */
export async function streamTurn(url, body, { onOpen, onMessage, onMeta, onError }) {
  let response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(body),
    })
  } catch (error) {
    onError?.(`Couldn't reach the server. ${error.message}`)
    return
  }

  if (!response.ok || !response.body) {
    onError?.(`The server refused the request (HTTP ${response.status}).`)
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (name, payload) => {
    if (name === 'a2ui') onMessage?.(payload)
    else if (name === 'meta') onMeta?.(payload)
    else if (name === 'open') onOpen?.(payload)
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      buffer = drainFrames(buffer, dispatch)
    }
    // A final frame with no trailing blank line still deserves to be read.
    drainFrames(`${buffer}\n\n`, dispatch)
  } catch (error) {
    onError?.(`The connection dropped mid-answer. ${error.message}`)
  }
}

/** GET the baseline dashboard as a batch of A2UI messages. */
export async function fetchBaseline() {
  const response = await fetch('/api/dashboard/a2ui')
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json()
}
