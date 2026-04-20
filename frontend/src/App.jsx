import { useEffect, useRef, useState } from 'react'
import { CircleNotch } from '@phosphor-icons/react'
import { API_URL } from './config.js'
import LoadingScreen from './components/LoadingScreen.jsx'
import Player from './components/Player.jsx'
import UrlInput from './components/UrlInput.jsx'

const LOGO_SRC = new URL('../../logos/Visualang-logo.png', import.meta.url).href

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
      if (attempt === 2) {
        onRetry?.('Connection issue, retrying...')
      } else if (attempt === 3) {
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
  const exportPollRef = useRef(null)

  const [title, setTitle] = useState('')
  const [images, setImages] = useState([])
  const [audioSrc, setAudioSrc] = useState(null)
  const [exportJobId, setExportJobId] = useState(null)
  const [error, setError] = useState('')
  const [gateWarning, setGateWarning] = useState('')
  const [genProgress, setGenProgress] = useState({ index: 0, total: 0, concept: '' })
  const [retryMsg, setRetryMsg] = useState('')

  function clearExportPoll() {
    if (exportPollRef.current) {
      clearInterval(exportPollRef.current)
      exportPollRef.current = null
    }
  }

  useEffect(() => clearExportPoll, [])

  function resetToIdle() {
    clearExportPoll()
    setAppState(STATES.IDLE)
    setTitle('')
    setImages([])
    setAudioSrc(null)
    setExportJobId(null)
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
      }
      transcriptData = await res.json()
      setTitle(transcriptData.title)
      setAudioSrc(toAbsoluteUrl(transcriptData.audio_url))
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
          if (data.error) throw new Error(data.error)

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

    transition(setAppState, STATES.PREVIEW_READY)
    kickOffExport(concepts, transcriptData, generatedImages)
  }

  async function kickOffExport(concepts, transcriptData, generatedImages) {
    transition(setAppState, STATES.EXPORTING)
    try {
      const exportImages = concepts.map((concept, index) => ({
        timestamp_seconds: concept.timestamp_seconds,
        image_url: generatedImages[index]?.image_url ?? '',
        duration_seconds:
          index < concepts.length - 1
            ? concepts[index + 1].timestamp_seconds - concept.timestamp_seconds
            : 30,
        concept: concept.concept,
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

  async function pollExport(jobId) {
    clearExportPoll()
    exportPollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/export/${jobId}`)
        const data = await res.json()
        if (data.status === 'done') {
          clearExportPoll()
          transition(setAppState, STATES.DONE)
        } else if (data.status === 'error') {
          clearExportPoll()
          console.error('[Visualang] Export error:', data.error)
          transition(setAppState, STATES.PREVIEW_READY)
        }
      } catch (err) {
        console.error('[Visualang] Export poll failed:', err)
      }
    }, 3000)
  }

  function buildSteps() {
    const stepDefs = [
      { key: STATES.LOADING_TRANSCRIPT, label: 'Fetching transcript' },
      { key: STATES.LOADING_CONCEPTS, label: 'Extracting concepts' },
      { key: STATES.GENERATING_IMAGES, label: 'Generating images' },
    ]
    const order = [STATES.LOADING_TRANSCRIPT, STATES.LOADING_CONCEPTS, STATES.GENERATING_IMAGES]
    const currentIdx = order.indexOf(appState)
    return stepDefs.map((step, index) => {
      let state = 'pending'
      if (index < currentIdx) state = 'complete'
      else if (index === currentIdx) state = 'active'

      let detail = ''
      if (step.key === STATES.GENERATING_IMAGES && appState === STATES.GENERATING_IMAGES) {
        detail =
          genProgress.total > 0
            ? `${genProgress.index} of ${genProgress.total} — "${genProgress.concept}"`
            : ''
      }
      return { label: step.label, state, detail }
    })
  }

  const isLoading = [
    STATES.LOADING_TRANSCRIPT,
    STATES.LOADING_CONCEPTS,
    STATES.GENERATING_IMAGES,
  ].includes(appState)
  const isPreviewState = [
    STATES.PREVIEW_READY,
    STATES.EXPORTING,
    STATES.DONE,
  ].includes(appState)
  const hasDownloads = appState === STATES.DONE && exportJobId
  const previewTitle = title || 'Your Visualang preview'

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand" aria-label="Visualang">
          <img src={LOGO_SRC} alt="Visualang" className="app-brand__image" />
        </div>
        <div className="app-header__actions">
          {isPreviewState && (
            <button type="button" className="button button--secondary" onClick={resetToIdle}>
              Create Another Video
            </button>
          )}
        </div>
      </header>

      <main className="app-main">
        {error && (
          <div className="notice notice--error" role="alert">
            <span>{error}</span>
            <button type="button" className="notice__dismiss" onClick={() => setError('')}>
              Dismiss
            </button>
          </div>
        )}

        {appState === STATES.IDLE && <UrlInput onSubmit={handleSubmit} />}

        {isLoading && (
          <LoadingScreen steps={buildSteps()} title={title || retryMsg} warning={gateWarning} />
        )}

        {isPreviewState && (
          <section className="stage-view" aria-labelledby="preview-title">
            <div className="stage-view__intro">
              <div className="stage-view__copy">
                <p className="eyebrow">Story Preview</p>
                <h1 id="preview-title" className="stage-view__title">
                  {previewTitle}
                </h1>
                <p className="stage-view__summary">
                  Review the illustrated sequence, listen through the narration, and export the
                  packaged assets when rendering finishes.
                </p>
              </div>
              <div className="stage-view__status">
                {appState === STATES.PREVIEW_READY && (
                  <div className="notice notice--info" role="status">
                    Preview is ready. Export will retry if the background render was interrupted.
                  </div>
                )}
                {appState === STATES.EXPORTING && (
                  <div className="notice notice--info" role="status" aria-live="polite">
                    <span className="stage-view__status-indicator">
                      <CircleNotch
                        size={20}
                        weight="bold"
                        aria-hidden="true"
                        className="stage-view__status-spinner"
                      />
                      <span>
                        Rendering your video in the background. You can review the visuals while
                        the export finishes.
                      </span>
                    </span>
                  </div>
                )}
                {appState === STATES.DONE && (
                  <div className="notice notice--success" role="status">
                    Export complete. Download the video, transcript, or images below.
                  </div>
                )}
                {gateWarning && (
                  <div className="notice notice--warning" role="status">
                    {gateWarning}
                  </div>
                )}
              </div>
            </div>

            <Player
              images={images.length > 0 ? images : SAMPLE_IMAGES}
              audioSrc={isDemoMode ? DEMO_AUDIO_SRC : audioSrc}
              title={title}
            />

            <div className="stage-meta">
              <p className="stage-meta__text">
                Controls stay visible across narrow viewports, and the player scales without
                clipping action areas.
              </p>
            </div>

            {hasDownloads && (
              <div className="stage-actions" aria-label="Export downloads">
                <a
                  href={`${API_URL}/export/${exportJobId}/video`}
                  download="visualang.mp4"
                  className="button button--primary"
                >
                  Download Video
                </a>
                <a
                  href={`${API_URL}/export/${exportJobId}/transcript`}
                  download="transcript.txt"
                  className="button button--secondary"
                >
                  Transcript
                </a>
                <a
                  href={`${API_URL}/export/${exportJobId}/images`}
                  download="visualang_images.zip"
                  className="button button--secondary"
                >
                  Images
                </a>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  )
}
