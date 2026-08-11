import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import ChatBox from './components/ChatBox'
import ComponentRenderer from './components/ComponentRenderer'
import ErrorBoundary from './components/ErrorBoundary'
import { fetchDashboard, generateComponent } from './api'
import { formatFull } from './lib/format'

/**
 * The baseline dashboard is built out of the same component catalog the LLM
 * chooses from. Nothing here is special-cased -- if a component renders on
 * load, the model can produce it too.
 */
function baselineComponents(data) {
  if (!data) return { cards: [], charts: [] }

  const monthly = Array.isArray(data.monthly) ? data.monthly : []
  const kpis = Array.isArray(data.kpis) ? data.kpis : []

  const cards = kpis.map((kpi) => ({
    type: 'stat_card',
    title: kpi.label,
    label: kpi.label,
    value: kpi.value,
    unit: kpi.unit,
    delta_pct: kpi.delta_pct,
    delta_direction: kpi.delta_direction,
    caption: kpi.caption,
  }))

  const charts = [
    {
      type: 'line_chart',
      title: 'Revenue vs. Expenses',
      x_label: 'Month',
      y_label: 'Amount',
      unit: 'USD',
      series: [
        { name: 'Revenue', points: monthly.map((row) => ({ x: row.month, y: row.revenue })) },
        { name: 'Expenses', points: monthly.map((row) => ({ x: row.month, y: row.expenses })) },
      ],
    },
    {
      type: 'bar_chart',
      title: 'Net Cash Flow by Month',
      x_label: 'Month',
      y_label: 'Net cash flow',
      unit: 'USD',
      stacked: false,
      series: [
        { name: 'Net cash flow', points: monthly.map((row) => ({ x: row.month, y: row.cash_flow })) },
      ],
    },
    {
      type: 'bar_chart',
      title: 'Expenses by Category',
      x_label: 'Category',
      y_label: 'Amount',
      unit: 'USD',
      stacked: false,
      series: [
        {
          name: 'Expenses',
          points: (data.expenses_by_category || []).map((row) => ({
            x: row.category,
            y: row.amount,
          })),
        },
      ],
    },
    {
      type: 'donut_chart',
      title: 'Revenue by Product Line',
      unit: 'USD',
      slices: (data.revenue_by_product || []).map((row) => ({
        label: row.product,
        value: row.amount,
      })),
    },
    {
      type: 'data_table',
      title: 'Recent Transactions',
      columns: [
        { key: 'date', label: 'Date', align: 'left' },
        { key: 'description', label: 'Description', align: 'left' },
        { key: 'category', label: 'Category', align: 'left' },
        { key: 'amount', label: 'Amount', align: 'right' },
        { key: 'status', label: 'Status', align: 'left' },
      ],
      rows: (data.transactions || []).map((row) => [
        row.date,
        row.description,
        row.category,
        formatFull(row.amount, 'USD'),
        row.status,
      ]),
    },
  ]

  return { cards, charts }
}

export default function App() {
  const [data, setData] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [generated, setGenerated] = useState([])
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const nextId = useRef(1)

  useEffect(() => {
    let cancelled = false
    fetchDashboard()
      .then((payload) => {
        if (!cancelled) setData(payload)
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const baseline = useMemo(() => baselineComponents(data), [data])

  const send = useCallback(
    async (text) => {
      setMessages((prev) => [...prev, { id: nextId.current++, role: 'user', text }])
      setBusy(true)

      const result = await generateComponent(text)
      const cardId = nextId.current++

      setMessages((prev) => [
        ...prev,
        {
          id: nextId.current++,
          role: 'assistant',
          text: result.explanation || 'Done.',
          error: !result.ok,
          followUps: Array.isArray(result.follow_ups) ? result.follow_ups : [],
        },
      ])
      setGenerated((prev) => [
        { id: cardId, prompt: text, component: result.component, fallback: result.fallback },
        ...prev,
      ])
      setBusy(false)
    },
    [],
  )

  const dismiss = useCallback((id) => {
    setGenerated((prev) => prev.filter((card) => card.id !== id))
  }, [])

  return (
    <div className="shell">
      <main className="dashboard">
        <div className="dashboard-inner">
          <header className="app-header">
            <div>
              <h1>Acme Analytics — Finance</h1>
              <p>
                {data
                  ? `${data.period?.start} to ${data.period?.end} · all amounts in ${
                      data.currency || 'USD'
                    }`
                  : 'Loading…'}
              </p>
            </div>
          </header>

          {loadError ? (
            <div className="empty">
              Couldn't load the dashboard data: {loadError}. Is the backend running on port 8000?
            </div>
          ) : null}

          {generated.length > 0 ? (
            <>
              <div className="section-label">Generated</div>
              <div className="grid">
                {generated.map((card) => (
                  <ErrorBoundary key={card.id}>
                    <ComponentRenderer
                      component={card.component}
                      subtitle={`“${card.prompt}”${card.fallback ? ' · fallback' : ''}`}
                      onDismiss={() => dismiss(card.id)}
                      generated
                    />
                  </ErrorBoundary>
                ))}
              </div>
            </>
          ) : null}

          {data ? (
            <>
              <div className="section-label">Overview</div>
              <div className="grid grid-kpi">
                {baseline.cards.map((component) => (
                  <ErrorBoundary key={component.title}>
                    <ComponentRenderer component={component} />
                  </ErrorBoundary>
                ))}
              </div>

              <div className="section-label">Reports</div>
              <div className="grid">
                {baseline.charts.map((component) => (
                  <ErrorBoundary key={component.title}>
                    <ComponentRenderer component={component} />
                  </ErrorBoundary>
                ))}
              </div>
            </>
          ) : null}
        </div>
      </main>

      <ChatBox messages={messages} busy={busy} onSend={send} />
    </div>
  )
}
