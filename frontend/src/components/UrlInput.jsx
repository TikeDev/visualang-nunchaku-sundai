import { useState } from 'react'
import { UploadSimple, Warning, YoutubeLogo } from '@phosphor-icons/react'

const YT_REGEX = /(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&?/]+)/
const MAX_FILE_BYTES = 25 * 1024 * 1024
const ALLOWED_EXT = ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']

export default function UrlInput({ onSubmit }) {
  const [mode, setMode] = useState('youtube')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState(null)
  const [error, setError] = useState('')

  function handleUrlChange(e) {
    setUrl(e.target.value)
    setError('')
  }

  function handleFileChange(e) {
    const f = e.target.files[0]
    if (!f) return
    const ext = '.' + f.name.split('.').pop().toLowerCase()
    if (!ALLOWED_EXT.includes(ext)) {
      setError(`Unsupported file type. Allowed: ${ALLOWED_EXT.join(', ')}`)
      setFile(null)
      return
    }
    if (f.size > MAX_FILE_BYTES) {
      setError('File exceeds 25 MB limit.')
      setFile(null)
      return
    }
    setError('')
    setFile(f)
  }

  function handleSubmit() {
    if (mode === 'youtube') {
      if (!YT_REGEX.test(url)) {
        setError('Please enter a valid YouTube URL.')
        return
      }
      onSubmit({ type: 'youtube', url })
    } else {
      if (!file) {
        setError('Please select an audio file.')
        return
      }
      onSubmit({ type: 'file', file })
    }
  }

  const isValid =
    mode === 'youtube' ? YT_REGEX.test(url) : file !== null

  return (
    <div style={styles.container}>
      <div style={styles.inner}>
        <h1 style={styles.logo}>Visualang</h1>
        <p style={styles.tagline}>
          Paste a YouTube URL or upload audio to generate an illustrated language learning video.
        </p>

        <div style={styles.modeToggle}>
          <button
            style={{ ...styles.modeBtn, ...(mode === 'youtube' ? styles.modeBtnActive : {}) }}
            onClick={() => { setMode('youtube'); setError('') }}
          >
            <YoutubeLogo size={18} weight={mode === 'youtube' ? 'fill' : 'regular'} />
            YouTube URL
          </button>
          <button
            style={{ ...styles.modeBtn, ...(mode === 'file' ? styles.modeBtnActive : {}) }}
            onClick={() => { setMode('file'); setError('') }}
          >
            <UploadSimple size={18} weight={mode === 'file' ? 'fill' : 'regular'} />
            Upload Audio
          </button>
        </div>

        {mode === 'youtube' ? (
          <input
            style={styles.input}
            type="text"
            placeholder="https://www.youtube.com/watch?v=..."
            value={url}
            onChange={handleUrlChange}
            onKeyDown={e => e.key === 'Enter' && isValid && handleSubmit()}
          />
        ) : (
          <label style={styles.fileLabel}>
            <input
              type="file"
              accept={ALLOWED_EXT.join(',')}
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <UploadSimple size={20} />
            {file ? file.name : `Choose file — ${ALLOWED_EXT.join(', ')} · max 25 MB`}
          </label>
        )}

        {error && (
          <p style={styles.error}>
            <Warning size={16} weight="fill" />
            {error}
          </p>
        )}

        <button
          style={{ ...styles.submit, ...(!isValid ? styles.submitDisabled : {}) }}
          onClick={handleSubmit}
          disabled={!isValid}
        >
          Generate
        </button>
      </div>
    </div>
  )
}

const styles = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '2rem',
  },
  inner: {
    width: '100%',
    maxWidth: '520px',
    display: 'flex',
    flexDirection: 'column',
    gap: '1.25rem',
  },
  logo: {
    fontFamily: 'var(--font-heading)',
    fontSize: '2.8rem',
    color: 'var(--color-warm-dark)',
    letterSpacing: '-0.02em',
  },
  tagline: {
    fontSize: '1rem',
    color: 'var(--color-warm-mid)',
    lineHeight: 1.6,
  },
  modeToggle: {
    display: 'flex',
    gap: '0.5rem',
    marginTop: '0.5rem',
  },
  modeBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
    padding: '0.5rem 1rem',
    border: '1.5px solid var(--color-warm-light)',
    borderRadius: '8px',
    background: 'transparent',
    color: 'var(--color-warm-mid)',
    fontSize: '0.9rem',
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  modeBtnActive: {
    background: 'var(--color-warm-dark)',
    color: 'var(--color-cream)',
    borderColor: 'var(--color-warm-dark)',
  },
  input: {
    width: '100%',
    padding: '0.75rem 1rem',
    border: '1.5px solid var(--color-warm-light)',
    borderRadius: '8px',
    fontSize: '0.95rem',
    color: 'var(--color-warm-dark)',
    background: 'white',
    outline: 'none',
    transition: 'border-color 0.15s',
  },
  fileLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.6rem',
    padding: '0.75rem 1rem',
    border: '1.5px dashed var(--color-warm-light)',
    borderRadius: '8px',
    fontSize: '0.9rem',
    color: 'var(--color-warm-mid)',
    cursor: 'pointer',
    background: 'white',
    transition: 'border-color 0.15s',
  },
  error: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
    color: '#b94040',
    fontSize: '0.875rem',
  },
  submit: {
    padding: '0.75rem 1.5rem',
    background: 'var(--color-terracotta)',
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    fontSize: '1rem',
    fontFamily: 'var(--font-heading)',
    letterSpacing: '0.02em',
    cursor: 'pointer',
    transition: 'background 0.15s',
    alignSelf: 'flex-start',
  },
  submitDisabled: {
    background: 'var(--color-warm-light)',
    cursor: 'not-allowed',
    color: 'var(--color-warm-mid)',
  },
}
