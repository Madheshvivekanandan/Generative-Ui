import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { MessageProcessor } from '@a2ui/web_core/v0_9'
import { A2uiSurface, MarkdownContext } from '@a2ui/react/v0_9'
// A2UI's Text component renders Markdown, but only if the host supplies a
// renderer -- there is no default, by design, so an agent's text cannot inject
// markup the host never opted into. This one sanitises through DOMPurify.
import { renderMarkdown } from '@a2ui/markdown-it'

import ChatBox from './components/ChatBox'
import ErrorBoundary from './components/ErrorBoundary'
import { financeCatalog } from './a2ui/catalog'
import { fetchBaseline, streamTurn } from './a2ui/transport'

/**
 * The one surface everything renders into -- the baseline at load, every
 * generated answer after it. Must match `CANVAS_SURFACE` in `backend/main.py`.
 * A fixed id is what makes the dashboard re-compose in place: `send` deletes
 * it, the incoming stream's `createSurface` re-opens the same id at the same
 * position, and replace-wins semantics do the rest.
 */
const CANVAS_SURFACE = 'dashboard'

/** One id per browser tab, so two tabs are two conversations. */
function newSessionId() {
  return crypto.randomUUID?.() ?? `s-${Math.random().toString(36).slice(2)}`
}

/**
 * The renderer is the only thing that turns agent output into UI.
 *
 * There is no branch here for "what kind of card is this" -- the agent names
 * components from `financeCatalog` and A2UI resolves them. Adding a component
 * means adding it to the catalog and to the backend's compiler; this file does
 * not change.
 */
export default function App() {
  const sessionId = useRef(newSessionId())
  const nextId = useRef(1)

  const [loadError, setLoadError] = useState(null)
  // The request whose answer the canvas currently shows; null means the
  // baseline overview. Chrome, not a component -- it never enters the surface.
  const [canvasPrompt, setCanvasPrompt] = useState(null)
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)

  // A snapshot of the processor's surfaces. This is not mirrored React state:
  // `processor.model.surfacesMap` is an externally-owned map that is mutated in
  // place, so React cannot observe it. Re-snapshotting on the processor's own
  // create/delete events is what makes a new surface render.
  const [surfaceMap, setSurfaceMap] = useState(() => new Map())

  // `send` and the processor's action handler each need the other, so the
  // handler reads through a ref that is filled in once `send` exists. `busy`
  // is mirrored into a ref for the same reason -- and the guard matters more
  // now than it did: with a single canvas, a button press mid-stream would put
  // two writers on the same surface.
  const sendRef = useRef(null)
  const busyRef = useRef(false)
  busyRef.current = busy

  const processor = useMemo(
    () =>
      new MessageProcessor([financeCatalog], (action) => {
        // The client-to-server half of A2UI. The agent put the request it
        // wants back into the action context, so every button -- whatever the
        // model invented -- comes through this one path.
        if (busyRef.current) return
        sendRef.current?.(action.context?.label || action.context?.prompt || 'Refine this', {
          url: '/api/action',
          body: {
            session_id: sessionId.current,
            name: action.name,
            surface_id: action.surfaceId,
            context: {
              prompt: String(action.context?.prompt ?? ''),
              label: String(action.context?.label ?? ''),
            },
          },
        })
      }),
    [],
  )

  useEffect(() => {
    const sync = () => setSurfaceMap(new Map(processor.model.surfacesMap))
    const created = processor.onSurfaceCreated(sync)
    const deleted = processor.onSurfaceDeleted(sync)
    sync()
    return () => {
      created.unsubscribe()
      deleted.unsubscribe()
    }
  }, [processor])

  useEffect(() => {
    let cancelled = false
    fetchBaseline()
      .then(({ messages: batch }) => {
        if (!cancelled) processor.processMessages(batch)
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error.message)
      })
    return () => {
      cancelled = true
    }
  }, [processor])

  /**
   * Clear the canvas through the protocol, so the processor's state and ours
   * cannot drift apart. The delete has to precede the stream: `createSurface`
   * on a live surface keeps its existing components, so stale cards from the
   * previous answer could leak into the new one wherever ids don't collide.
   */
  const clearCanvas = useCallback(() => {
    if (processor.model.surfacesMap.has(CANVAS_SURFACE)) {
      processor.processMessages([{ version: 'v0.9', deleteSurface: { surfaceId: CANVAS_SURFACE } }])
    }
  }, [processor])

  /**
   * Run one turn. `text` is what goes in the chat log; `request` is where to
   * send it, which differs for a typed message and a button press. The answer
   * re-composes the canvas in place -- it does not stack under the last one.
   */
  const send = useCallback(
    async (text, request) => {
      const url = request?.url ?? '/api/generate'
      const body = request?.body ?? { session_id: sessionId.current, message: text }

      setMessages((prev) => [...prev, { id: nextId.current++, role: 'user', text }])
      setBusy(true)
      clearCanvas()
      setCanvasPrompt(text)

      await streamTurn(url, body, {
        onOpen: () => {
          // The turn always re-composes the canvas; the id in the frame is
          // announced for non-browser clients and needs nothing from us here.
        },
        onMessage: (message) => {
          try {
            processor.processMessages([message])
          } catch (error) {
            // A message the renderer rejects is a bug on our side, not
            // something the user can act on. Keep the turn alive.
            console.error('A2UI message rejected', error, message)
          }
        },
        onMeta: (meta) => {
          setMessages((prev) => [
            ...prev,
            {
              id: nextId.current++,
              role: 'assistant',
              text: meta.explanation || 'Done.',
              error: meta.ok === false,
              followUps: Array.isArray(meta.follow_ups) ? meta.follow_ups : [],
            },
          ])
        },
        onError: (detail) => {
          setMessages((prev) => [
            ...prev,
            { id: nextId.current++, role: 'assistant', text: detail, error: true, followUps: [] },
          ])
          // The transport died with the canvas already cleared. The backend
          // cannot report this one, so restore the baseline rather than
          // leaving an empty dashboard behind.
          fetchBaseline()
            .then(({ messages: batch }) => {
              clearCanvas()
              processor.processMessages(batch)
              setCanvasPrompt(null)
            })
            .catch(() => setLoadError('The dashboard could not be restored. Reload the page.'))
        },
      })

      setBusy(false)
    },
    [clearCanvas, processor],
  )

  sendRef.current = send

  /** Put the baseline overview back on the canvas. */
  const reset = useCallback(() => {
    fetchBaseline()
      .then(({ messages: batch }) => {
        clearCanvas()
        processor.processMessages(batch)
        setCanvasPrompt(null)
      })
      .catch((error) => setLoadError(error.message))
  }, [clearCanvas, processor])

  const canvas = useMemo(() => surfaceMap.get(CANVAS_SURFACE), [surfaceMap])

  return (
    <div className="shell">
      <main className="dashboard">
        <div className="dashboard-inner">
          <header className="app-header">
            <div>
              <h1>Acme Analytics — Finance</h1>
              <p>
                Rendered from A2UI v0.9 · catalog <code>finance/v1</code>
              </p>
            </div>
          </header>

          {loadError ? (
            <div className="empty">
              Couldn't load the dashboard: {loadError}. Is the backend running on port 8000?
            </div>
          ) : null}

          <MarkdownContext.Provider value={renderMarkdown}>
            {canvasPrompt ? (
              <div className="turn-head">
                <span className="turn-prompt">“{canvasPrompt}”</span>
                <button
                  type="button"
                  className="card-dismiss"
                  onClick={reset}
                  disabled={busy}
                  aria-label="Reset to the overview"
                >
                  ×
                </button>
              </div>
            ) : (
              <div className="section-label">Overview</div>
            )}

            <div className="sr-status" role="status">
              {busy ? 'Re-composing the dashboard…' : null}
            </div>

            {canvas ? (
              <section className="turn">
                <ErrorBoundary>
                  <A2uiSurface surface={canvas} />
                </ErrorBoundary>
              </section>
            ) : busy ? (
              // The canvas is cleared and the first frame hasn't landed: a
              // skeleton shaped like the layout it replaces, not a spinner.
              <div className="skeleton" aria-hidden="true">
                <div className="skeleton-row">
                  <div className="skeleton-tile" />
                  <div className="skeleton-tile" />
                </div>
                <div className="skeleton-chart" />
              </div>
            ) : null}
          </MarkdownContext.Provider>
        </div>
      </main>

      <ChatBox messages={messages} busy={busy} onSend={send} />
    </div>
  )
}
