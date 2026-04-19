import { CheckCircle, CircleNotch, Clock } from '@phosphor-icons/react'

function StepIcon({ state }) {
  if (state === 'complete') return <CheckCircle size={22} color="var(--color-sage)" weight="fill" />
  if (state === 'active')
    return (
      <CircleNotch
        size={22}
        color="var(--color-terracotta)"
        style={{ animation: 'spin 1s linear infinite' }}
      />
    )
  return <Clock size={22} color="var(--color-warm-light)" />
}

export default function LoadingScreen({ steps, title }) {
  return (
    <div style={styles.container}>
      {title && <p style={styles.title}>{title}</p>}
      <div style={styles.card}>
        <h2 style={styles.heading}>Processing</h2>
        <ul style={styles.list}>
          {steps.map((step, i) => (
            <li key={i} style={styles.step}>
              <span style={styles.icon}>
                <StepIcon state={step.state} />
              </span>
              <span style={{ ...styles.label, opacity: step.state === 'pending' ? 0.45 : 1 }}>
                {step.label}
                {step.detail && <span style={styles.detail}>{step.detail}</span>}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

const styles = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '2rem',
    gap: '1.5rem',
  },
  title: {
    fontFamily: 'var(--font-heading)',
    fontSize: '1.1rem',
    color: 'var(--color-warm-mid)',
    fontStyle: 'italic',
    maxWidth: '480px',
    textAlign: 'center',
  },
  card: {
    background: 'white',
    borderRadius: '12px',
    padding: '2rem 2.5rem',
    width: '100%',
    maxWidth: '420px',
    boxShadow: '0 2px 16px rgba(44,36,22,0.08)',
  },
  heading: {
    fontFamily: 'var(--font-heading)',
    fontSize: '1.4rem',
    color: 'var(--color-warm-dark)',
    marginBottom: '1.5rem',
  },
  list: {
    listStyle: 'none',
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  step: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  icon: {
    flexShrink: 0,
    display: 'flex',
    alignItems: 'center',
  },
  label: {
    fontFamily: 'var(--font-body)',
    fontSize: '0.95rem',
    color: 'var(--color-warm-dark)',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.1rem',
    transition: 'opacity 0.3s',
  },
  detail: {
    fontSize: '0.8rem',
    color: 'var(--color-warm-mid)',
  },
}
