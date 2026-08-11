import { Component } from 'react'

/**
 * One of these wraps every card. A malformed component from the model can
 * take down its own card, but never the dashboard around it.
 */
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Card failed to render:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <section className="card">
          <div className="card-head">
            <h2 className="card-title">Couldn't render this card</h2>
          </div>
          <p className="note-body">{String(this.state.error.message || this.state.error)}</p>
        </section>
      )
    }
    return this.props.children
  }
}
