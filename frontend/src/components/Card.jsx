export default function Card({ title, subtitle, onDismiss, generated = false, wide = false, children }) {
  return (
    <section className={`card${generated ? ' card-generated' : ''}${wide ? ' span-2' : ''}`}>
      <div className="card-head">
        <div>
          <h2 className="card-title">{title}</h2>
          {subtitle ? <p className="card-sub">{subtitle}</p> : null}
        </div>
        {onDismiss ? (
          <button className="card-dismiss" onClick={onDismiss} aria-label={`Remove ${title}`} title="Remove">
            ×
          </button>
        ) : null}
      </div>
      {children}
    </section>
  )
}
