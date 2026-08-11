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

const BASELINE_SURFACE = 'dashboard'

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
  const [generatedIds, setGeneratedIds] = useState([])
  const [prompts, setPrompts] = useState({})
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)

  // A snapshot of the processor's surfaces. This is not mirrored React state:
  // `processor.model.surfacesMap` is an externally-owned map that is mutated in
  // place, so React cannot observe it. Re-snapshotting on the processor's own
  // create/delete events is what makes a new surface render.
  const [surfaceMap, setSurfaceMap] = useState(() => new Map())

  // `send` and the processor's action handler each need the other, so the
  // handler reads through a ref that is filled in once `send` exists.
  const sendRef = useRef(null)

  const processor = useMemo(
    () =>
      new MessageProcessor([financeCatalog], (action) => {
        // The client-to-server half of A2UI. The agent put the request it
        // wants back into the action context, so every button -- whatever the
        // model invented -- comes through this one path.
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
   * Run one turn. `text` is what goes in the chat log; `request` is where to
   * send it, which differs for a typed message and a button press.
   */
  const send = useCallback(
    async (text, request) => {
      const url = request?.url ?? '/api/generate'
      const body = request?.body ?? { session_id: sessionId.current, message: text }

      setMessages((prev) => [...prev, { id: nextId.current++, role: 'user', text }])
      setBusy(true)

      let surfaceId = null

      await streamTurn(url, body, {
        onOpen: ({ surface_id: id }) => {
          surfaceId = id
          // Registered before any component arrives so the card's slot exists
          // while it is still filling in, rather than appearing at the end.
          setGeneratedIds((prev) => [id, ...prev])
          setPrompts((prev) => ({ ...prev, [id]: text }))
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
          // Nothing will ever render into this surface, so don't leave an
          // empty frame behind.
          if (surfaceId) {
            setGeneratedIds((prev) => prev.filter((id) => id !== surfaceId))
          }
        },
      })

      setBusy(false)
    },
    [processor],
  )

  sendRef.current = send

  const dismiss = useCallback(
    (id) => {
      // Dismissal goes through the protocol rather than around it, so the
      // processor's state and ours cannot drift apart.
      processor.processMessages([{ version: 'v0.9', deleteSurface: { surfaceId: id } }])
      setGeneratedIds((prev) => prev.filter((value) => value !== id))
    },
    [processor],
  )

  const { baseline, generated } = useMemo(
    () => ({
      baseline: surfaceMap.get(BASELINE_SURFACE),
      // Newest first, and only surfaces the processor actually holds -- a turn
      // whose stream died leaves an id here with no surface behind it.
      generated: generatedIds
        .map((id) => ({ id, surface: surfaceMap.get(id) }))
        .filter((entry) => entry.surface),
    }),
    [surfaceMap, generatedIds],
  )

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
            {generated.length > 0 ? (
              <>
                <div className="section-label">Generated</div>
                {generated.map(({ id, surface }) => (
                  <section className="turn" key={id}>
                    <div className="turn-head">
                      <span className="turn-prompt">“{prompts[id]}”</span>
                      <button
                        type="button"
                        className="card-dismiss"
                        onClick={() => dismiss(id)}
                        aria-label="Dismiss this answer"
                      >
                        ×
                      </button>
                    </div>
                    <ErrorBoundary>
                      <A2uiSurface surface={surface} />
                    </ErrorBoundary>
                  </section>
                ))}
              </>
            ) : null}

            <div className="sr-status" role="status">
              {busy ? 'Composing an answer…' : null}
            </div>

            {busy && generated.length === 0 ? <div className="empty">Composing…</div> : null}

            {baseline ? (
              <>
                <div className="section-label">Overview</div>
                <ErrorBoundary>
                  <A2uiSurface surface={baseline} />
                </ErrorBoundary>
              </>
            ) : null}
          </MarkdownContext.Provider>
        </div>
      </main>

      <ChatBox messages={messages} busy={busy} onSend={send} />
    </div>
  )
}
