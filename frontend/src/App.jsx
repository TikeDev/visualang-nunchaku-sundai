import { useState } from 'react'
import { API_URL } from './config.js'
import LoadingScreen from './components/LoadingScreen.jsx'
import Player from './components/Player.jsx'
import UrlInput from './components/UrlInput.jsx'

const STATES = {
  IDLE: 'idle',
  LOADING_TRANSCRIPT: 'loading_transcript',
  LOADING_CONCEPTS: 'loading_concepts',
  GENERATING_IMAGES: 'generating_images',
  PREVIEW_READY: 'preview_ready',
  EXPORTING: 'exporting',
  DONE: 'done',
}

const SAMPLE_IMAGES = [
  {
    timestamp_seconds: 0,
    image_url: 'https://images.unsplash.com/photo-1518020382113-a7e8fc38eac9?w=1024',
  },
  {
    timestamp_seconds: 22,
    image_url: 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1024',
  },
  {
    timestamp_seconds: 47,
    image_url: 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=1024',
  },
  {
    timestamp_seconds: 71,
    image_url: 'https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=1024',
  },
  {
    timestamp_seconds: 95,
    image_url: 'https://images.unsplash.com/photo-1501854140801-50d01698950b?w=1024',
  },
]

const DEMO_AUDIO_SRC = 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3'

// --- Retry helper ---
async function fetchWithRetry(url, options, onRetry) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(url, options)
      if (!res.ok) {
        let message = `HTTP ${res.status}`
        try {
          const raw = await res.text()
          if (raw) {
            try {
              const parsed = JSON.parse(raw)
              message = parsed.detail || parsed.error || raw
            } catch {
              message = raw
            }
          }
        } catch {
          // ignore body parsing failures and keep the HTTP status message
        }
        throw new Error(message)
      }
      return res
    } catch (err) {
      if (attempt === 1) {
        // silent retry
      } else if (attempt === 2) {
        onRetry?.(`Connection issue, retrying...`)
      } else {
        throw err
      }
    }
  }
}

async function readErrorMessage(response) {
  let message = `HTTP ${response.status}`
  try {
    const raw = await response.text()
    if (raw) {
      try {
        const parsed = JSON.parse(raw)
        message = parsed.detail || parsed.error || raw
      } catch {
        message = raw
      }
    }
  } catch {
    // ignore body parsing failures and keep the HTTP status message
  }
  return message
}

function toAbsoluteUrl(url) {
  if (!url || /^https?:\/\//.test(url)) return url
  return `${API_URL}${url.startsWith('/') ? url : `/${url}`}`
}

function normalizeImages(images) {
  return images.map(image => ({
    ...image,
    image_url: toAbsoluteUrl(image.image_url),
  }))
}

function transition(setState, state) {
  console.log(`[Visualang] State: ${state}`)
  setState(state)
}

export default function App() {
  const isDemoMode = new URLSearchParams(window.location.search).has('demo')
  const [appState, setAppState] = useState(isDemoMode ? STATES.PREVIEW_READY : STATES.IDLE)

  const [title, setTitle] = useState('')
  const [images, setImages] = useState([])
  const [youtubeVideoId, setYoutubeVideoId] = useState(null)
  const [audioSrc, setAudioSrc] = useState(null)
  const [audioPath, setAudioPath] = useState(null)
  const [transcript, setTranscript] = useState([])
  const [exportJobId, setExportJobId] = useState(null)
  const [exportDone, setExportDone] = useState(false)
  const [error, setError] = useState('')
  const [gateWarning, setGateWarning] = useState('')
  const [genProgress, setGenProgress] = useState({ index: 0, total: 0, concept: '' })
  const [retryMsg, setRetryMsg] = useState('')

  function resetToIdle() {
    setAppState(STATES.IDLE)
    setTitle('')
    setImages([])
    setYoutubeVideoId(null)
    setAudioSrc(null)
    setAudioPath(null)
    setTranscript([])
    setExportJobId(null)
    setExportDone(false)
    setError('')
    setGateWarning('')
    setGenProgress({ index: 0, total: 0, concept: '' })
    setRetryMsg('')
    console.log('[Visualang] State: idle (reset)')
  }

  async function handleSubmit(input) {
    setError('')
    setGateWarning('')
    setRetryMsg('')

    // Extract YouTube video ID if needed
    if (input.type === 'youtube') {
      const match = input.url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&?/]+)/)
      if (match) setYoutubeVideoId(match[1])
    }

    // --- Step 1: Transcript ---
    transition(setAppState, STATES.LOADING_TRANSCRIPT)
    let transcriptData
    try {
      let res
      if (input.type === 'youtube') {
        res = await fetchWithRetry(
          `${API_URL}/transcript`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_url: input.url }),
          },
          setRetryMsg
        )
      } else {
        const form = new FormData()
        form.append('file', input.file)
        res = await fetchWithRetry(
          `${API_URL}/transcript`,
          { method: 'POST', body: form },
          setRetryMsg
        )
        setAudioSrc(URL.createObjectURL(input.file))
      }
      transcriptData = await res.json()
      setTitle(transcriptData.title)
      setTranscript(transcriptData.transcript)
      setAudioPath(transcriptData.audio_path)
      if (transcriptData.gate?.verdict === 'warn' && transcriptData.gate?.reason) {
        setGateWarning(transcriptData.gate.reason)
      }
      console.log(`[Visualang] Transcript: ${transcriptData.transcript.length} segments`)
    } catch (err) {
      console.error('[Visualang] Transcript failed:', err)
      setError(err.message || 'Failed to fetch transcript. Please try again.')
      setAppState(STATES.IDLE)
      return
    }

    // --- Step 2: Concepts ---
    transition(setAppState, STATES.LOADING_CONCEPTS)
    let concepts
    try {
      const res = await fetchWithRetry(
        `${API_URL}/concepts`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ transcript: transcriptData.transcript }),
        },
        setRetryMsg
      )
      concepts = await res.json()
      console.log(`[Visualang] Concepts: ${concepts.length}`)
    } catch (err) {
      console.error('[Visualang] Concepts failed:', err)
      setError(err.message || 'Failed to extract concepts. Please try again.')
      setAppState(STATES.IDLE)
      return
    }

    // --- Step 3: Image generation (SSE) ---
    transition(setAppState, STATES.GENERATING_IMAGES)
    let generatedImages = []
    try {
      const response = await fetch(`${API_URL}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ concepts }),
      })
      if (!response.ok) throw new Error(await readErrorMessage(response))
      if (!response.body) throw new Error('Image stream was empty.')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = JSON.parse(line.slice(6))
          if (data.error) {
            throw new Error(data.error)
          }
          if (data.done) {
            generatedImages = normalizeImages(data.images)
            setImages(generatedImages)
            console.log(
              `[Visualang] State: generating_images (${generatedImages.length}/${generatedImages.length})`
            )
          } else {
            setGenProgress({ index: data.index, total: data.total, concept: data.concept })
            console.log(`[Visualang] State: generating_images (${data.index}/${data.total})`)
          }
        }
      }
    } catch (err) {
      console.error('[Visualang] Image generation failed:', err)
      setError(err.message || 'Image generation failed. Please try again.')
      setAppState(STATES.IDLE)
      return
    }

    // --- Preview ready — kick off export in background ---
    transition(setAppState, STATES.PREVIEW_READY)
    kickOffExport(concepts, transcriptData, generatedImages)
  }

  async function kickOffExport(concepts, transcriptData, generatedImages) {
    transition(setAppState, STATES.EXPORTING)
    try {
      const exportImages = concepts.map((c, i) => ({
        timestamp_seconds: c.timestamp_seconds,
        image_url: generatedImages[i]?.image_url ?? '',
        duration_seconds:
          i < concepts.length - 1
            ? concepts[i + 1].timestamp_seconds - c.timestamp_seconds
            : 30,
        concept: c.concept,
      }))
      const res = await fetch(`${API_URL}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          audio_path: transcriptData.audio_path,
          images: exportImages,
          transcript: transcriptData.transcript,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const { job_id } = await res.json()
      setExportJobId(job_id)
      pollExport(job_id)
    } catch (err) {
      console.error('[Visualang] Export start failed:', err)
      transition(setAppState, STATES.PREVIEW_READY)
    }
  }

  async function pollExport(job_id) {
    const poll = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/export/${job_id}`)
        const data = await res.json()
        if (data.status === 'done') {
          clearInterval(poll)
          setExportDone(true)
          transition(setAppState, STATES.DONE)
        } else if (data.status === 'error') {
          clearInterval(poll)
          console.error('[Visualang] Export error:', data.error)
          transition(setAppState, STATES.PREVIEW_READY)
        }
      } catch (err) {
        console.error('[Visualang] Export poll failed:', err)
      }
    }, 3000)
  }

  // --- Build loading steps ---
  function buildSteps() {
    const stepDefs = [
      { key: STATES.LOADING_TRANSCRIPT, label: 'Fetching transcript' },
      { key: STATES.LOADING_CONCEPTS, label: 'Extracting concepts' },
      { key: STATES.GENERATING_IMAGES, label: 'Generating images' },
    ]
    const order = [STATES.LOADING_TRANSCRIPT, STATES.LOADING_CONCEPTS, STATES.GENERATING_IMAGES]
    const currentIdx = order.indexOf(appState)
    return stepDefs.map((s, i) => {
      let state = 'pending'
      if (i < currentIdx) state = 'complete'
      else if (i === currentIdx) state = 'active'
      let detail = ''
      if (s.key === STATES.GENERATING_IMAGES && appState === STATES.GENERATING_IMAGES) {
        detail =
          genProgress.total > 0
            ? `${genProgress.index} of ${genProgress.total} — "${genProgress.concept}"`
            : ''
      }
      return { label: s.label, state, detail }
    })
  }

  // --- Render ---
  const isLoading = [
    STATES.LOADING_TRANSCRIPT,
    STATES.LOADING_CONCEPTS,
    STATES.GENERATING_IMAGES,
  ].includes(appState)

  if (appState === STATES.IDLE) {
    return (
      <div>
        {error && (
          <div style={styles.errorBanner}>
            {error}{' '}
            <button style={styles.tryAgainBtn} onClick={() => setError('')}>
              Dismiss
            </button>
          </div>
        )}
        <UrlInput onSubmit={handleSubmit} />
      </div>
    )
  }

  if (isLoading) {
    return <LoadingScreen steps={buildSteps()} title={title || retryMsg} warning={gateWarning} />
  }

  if (
    appState === STATES.PREVIEW_READY ||
    appState === STATES.EXPORTING ||
    appState === STATES.DONE
  ) {
    return (
      <div style={{ padding: '2rem', background: 'var(--color-bg, #f5f0e8)', minHeight: '100vh' }}>
        <Player
          images={images.length > 0 ? images : SAMPLE_IMAGES}
          audioSrc={isDemoMode ? DEMO_AUDIO_SRC : audioSrc}
          youtubeVideoId={isDemoMode ? null : youtubeVideoId}
          title={title}
          onStartOver={resetToIdle}
        />
        {appState === STATES.EXPORTING && (
          <div style={styles.exportingBadge}>Rendering video...</div>
        )}
        {gateWarning && <div style={styles.warningBadge}>{gateWarning}</div>}
        {appState === STATES.DONE && exportJobId && (
          <div style={styles.downloadBar}>
            <a
              href={`${API_URL}/export/${exportJobId}/video`}
              download="visualang.mp4"
              style={styles.dlBtn}
            >
              Download Video
            </a>
            <a
              href={`${API_URL}/export/${exportJobId}/transcript`}
              download="transcript.txt"
              style={styles.dlBtn}
            >
              Transcript
            </a>
            <a
              href={`${API_URL}/export/${exportJobId}/images`}
              download="visualang_images.zip"
              style={styles.dlBtn}
            >
              Images
            </a>
          </div>
        )}
      </div>
    )
  }

  return null
}

const styles = {
  errorBanner: {
    position: 'fixed',
    top: '1rem',
    left: '50%',
    transform: 'translateX(-50%)',
    background: '#b94040',
    color: 'white',
    padding: '0.6rem 1.2rem',
    borderRadius: '8px',
    fontSize: '0.9rem',
    zIndex: 100,
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  tryAgainBtn: {
    background: 'rgba(255,255,255,0.2)',
    border: 'none',
    color: 'white',
    padding: '0.2rem 0.6rem',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '0.85rem',
  },
  exportingBadge: {
    position: 'fixed',
    bottom: '5rem',
    right: '1.5rem',
    background: 'rgba(28,20,10,0.75)',
    color: 'rgba(255,255,255,0.75)',
    padding: '0.4rem 0.8rem',
    borderRadius: '6px',
    fontSize: '0.8rem',
    backdropFilter: 'blur(4px)',
    zIndex: 10,
  },
  warningBadge: {
    position: 'fixed',
    top: '1.5rem',
    left: '1.5rem',
    maxWidth: '420px',
    background: 'rgba(255, 243, 224, 0.92)',
    color: '#5b3916',
    padding: '0.75rem 0.95rem',
    borderRadius: '10px',
    border: '1px solid rgba(207, 141, 74, 0.35)',
    boxShadow: '0 10px 30px rgba(44,36,22,0.08)',
    fontSize: '0.85rem',
    lineHeight: 1.5,
    zIndex: 11,
  },
  downloadBar: {
    position: 'fixed',
    bottom: '5rem',
    right: '1.5rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
    zIndex: 10,
  },
  dlBtn: {
    display: 'block',
    background: 'var(--color-terracotta)',
    color: 'white',
    padding: '0.5rem 1rem',
    borderRadius: '6px',
    textDecoration: 'none',
    fontSize: '0.85rem',
    fontFamily: 'var(--font-body)',
    textAlign: 'center',
  },
}
