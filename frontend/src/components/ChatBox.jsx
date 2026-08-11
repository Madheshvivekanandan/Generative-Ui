import { Fragment, useEffect, useRef, useState } from 'react'

/** Openers, shown only before the first message. After that the follow-ups
    come from the model, contextual to whatever it just rendered. */
const OPENERS = [
  'Show revenue as a line chart',
  'Expenses by category as a bar chart',
  'Revenue vs expenses over time',
  'Break down revenue by region',
  'List the largest transactions',
  'What was net cash flow in August?',
]

function Suggestions({ items, busy, onSend }) {
  if (!items?.length) return null
  return (
    <div className="chips">
      {items.map((item) => (
        <button
          key={item}
          type="button"
          className="chip"
          disabled={busy}
          onClick={() => onSend(item)}
        >
          {item}
        </button>
      ))}
    </div>
  )
}

export default function ChatBox({ messages, busy, onSend }) {
  const [draft, setDraft] = useState('')
  const logRef = useRef(null)

  useEffect(() => {
    // busy is a dependency because the "Thinking…" row changes the height too.
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [messages, busy])

  function submit(event) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || busy) return
    setDraft('')
    onSend(text)
  }

  return (
    <aside className="chat">
      <div className="chat-head">
        <h2>Ask for a component</h2>
        <p>Each request adds a card to the dashboard.</p>
      </div>

      <div className="chat-log" ref={logRef}>
        {messages.length === 0 ? (
          <Suggestions items={OPENERS} busy={busy} onSend={onSend} />
        ) : (
          messages.map((message) => (
            <Fragment key={message.id}>
              <div
                className={[
                  'chat-msg',
                  message.role === 'user' ? 'chat-msg-user' : '',
                  message.error ? 'chat-msg-error' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                {message.text}
              </div>
              <Suggestions items={message.followUps} busy={busy} onSend={onSend} />
            </Fragment>
          ))
        )}
        {busy ? <div className="chat-msg chat-msg-busy">Thinking…</div> : null}
      </div>

      <div className="chat-foot">
        <form className="chat-form" onSubmit={submit}>
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask for a chart, a number, or a table…"
            aria-label="Describe the component you want"
            disabled={busy}
          />
          <button type="submit" disabled={busy || !draft.trim()}>
            {busy ? '…' : 'Send'}
          </button>
        </form>
      </div>
    </aside>
  )
}
