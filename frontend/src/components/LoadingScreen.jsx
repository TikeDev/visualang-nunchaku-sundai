import { CheckCircle, CircleNotch, Clock } from '@phosphor-icons/react'

function StepIcon({ state }) {
  if (state === 'complete') {
    return <CheckCircle size={24} color="var(--color-sage-strong)" weight="fill" />
  }
  if (state === 'active') {
    return (
      <CircleNotch
        size={24}
        color="var(--color-terracotta-strong)"
        style={{ animation: 'spin 1s linear infinite' }}
      />
    )
  }
  return <Clock size={24} color="var(--color-warm-muted)" />
}

export default function LoadingScreen({ steps, title, warning }) {
  return (
    <section className="panel panel--loading" aria-labelledby="loading-title">
      <div className="panel__copy">
        <p className="eyebrow">Processing Workflow</p>
        <h1 id="loading-title" className="panel__title">
          Building your illustrated sequence.
        </h1>
        <p className="panel__description">
          Visualang is fetching the transcript, extracting concepts, and preparing the generated
          frames. Progress updates remain readable across narrow viewports.
        </p>
      </div>

      {title && (
        <div className="loading-screen__context" aria-label="Current source title">
          <p className="loading-screen__context-label">Current source</p>
          <p className="loading-screen__context-title">{title}</p>
        </div>
      )}

      <div className="loading-screen__card" role="status" aria-live="polite">
        <ol className="loading-screen__list">
          {steps.map(step => (
            <li key={step.label} className={`loading-screen__step is-${step.state}`}>
              <span className="loading-screen__icon" aria-hidden="true">
                <StepIcon state={step.state} />
              </span>
              <span className="loading-screen__body">
                <span className="loading-screen__label">{step.label}</span>
                {step.detail && <span className="loading-screen__detail">{step.detail}</span>}
              </span>
            </li>
          ))}
        </ol>

        {warning && (
          <div className="notice notice--warning loading-screen__warning" role="status">
            {warning}
          </div>
        )}
      </div>
    </section>
  )
}
