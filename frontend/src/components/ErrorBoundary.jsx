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
      // The message stays in the console: a render-error string is internal
      // detail (component stacks, upstream text) and not useful to a reader.
      return (
        <section className="card">
          <div className="card-head">
            <h2 className="card-title">Couldn't render this card</h2>
          </div>
          <p className="note-body">
            Something went wrong drawing this component. The details are in the browser console.
          </p>
        </section>
      )
    }
    return this.props.children
  }
}
