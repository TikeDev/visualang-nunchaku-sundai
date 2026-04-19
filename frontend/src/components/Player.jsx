import { useEffect, useRef, useState } from 'react'
import { CircleNotch, Pause, Play } from '@phosphor-icons/react'

const KB_ANIMATIONS = [
  'ken-burns-zoom-in-left',
  'ken-burns-zoom-in-right',
  'ken-burns-zoom-out-left',
  'ken-burns-zoom-out-right',
]

function getImageDuration(images, index) {
  if (index < images.length - 1) {
    return images[index + 1].timestamp_seconds - images[index].timestamp_seconds
  }
  return 30
}

export default function Player({ images, audioSrc, title }) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isReady, setIsReady] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const audioRef = useRef(null)
  const loadedRef = useRef(0)

  // Preload all images
  useEffect(() => {
    loadedRef.current = 0
    setCurrentIndex(0)
    setIsReady(false)
    if (images.length === 0) return
    images.forEach(img => {
      const el = new Image()
      el.onload = () => {
        loadedRef.current += 1
        if (loadedRef.current === images.length) setIsReady(true)
      }
      el.onerror = () => {
        loadedRef.current += 1
        if (loadedRef.current === images.length) setIsReady(true)
      }
      el.src = img.image_url
    })
  }, [images])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    function syncCurrentImage() {
      const currentTime = audio.currentTime
      let nextIndex = 0
      for (let i = images.length - 1; i >= 0; i--) {
        if (currentTime >= images[i].timestamp_seconds) {
          nextIndex = i
          break
        }
      }
      setCurrentIndex(nextIndex)
    }

    function handlePlayEvent() {
      setIsPlaying(true)
      syncCurrentImage()
    }

    function handlePauseEvent() {
      setIsPlaying(false)
    }

    function handleEndedEvent() {
      setIsPlaying(false)
      syncCurrentImage()
    }

    function handleLoadedData() {
      audio.currentTime = 0
      syncCurrentImage()
    }

    audio.addEventListener('play', handlePlayEvent)
    audio.addEventListener('pause', handlePauseEvent)
    audio.addEventListener('ended', handleEndedEvent)
    audio.addEventListener('timeupdate', syncCurrentImage)
    audio.addEventListener('seeked', syncCurrentImage)
    audio.addEventListener('loadeddata', handleLoadedData)

    syncCurrentImage()
    return () => {
      audio.removeEventListener('play', handlePlayEvent)
      audio.removeEventListener('pause', handlePauseEvent)
      audio.removeEventListener('ended', handleEndedEvent)
      audio.removeEventListener('timeupdate', syncCurrentImage)
      audio.removeEventListener('seeked', syncCurrentImage)
      audio.removeEventListener('loadeddata', handleLoadedData)
    }
  }, [images, audioSrc])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    audio.pause()
    audio.currentTime = 0
    setIsPlaying(false)
    setCurrentIndex(0)
  }, [audioSrc])

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackRate
    }
  }, [playbackRate])

  function handlePlay() {
    audioRef.current?.play().catch(err => {
      console.error('[Visualang] Audio play failed:', err)
      setIsPlaying(false)
    })
  }

  function handlePause() {
    audioRef.current?.pause()
  }

  function handleRateChange(e) {
    const rate = parseFloat(e.target.value)
    setPlaybackRate(rate)
    if (audioRef.current) {
      audioRef.current.playbackRate = rate
    }
  }

  return (
    <div style={styles.root}>
      {audioSrc && (
        <audio ref={audioRef} src={audioSrc} style={{ display: 'none' }} />
      )}

      {/* Image stack */}
      <div style={styles.imageStack}>
        {images.map((img, i) => {
          const duration = getImageDuration(images, i)
          const kbClass = KB_ANIMATIONS[i % 4]
          const isActive = i === currentIndex
          return (
            <div
              key={img.image_url + i}
              style={{
                ...styles.imageSlide,
                opacity: isActive ? 1 : 0,
                zIndex: isActive ? 1 : 0,
              }}
            >
              <img
                src={img.image_url}
                alt=""
                style={{
                  ...styles.image,
                  animationName: isPlaying && isActive ? kbClass : 'none',
                  animationDuration: `${duration}s`,
                  animationTimingFunction: 'linear',
                  animationFillMode: 'both',
                  animationPlayState: isPlaying ? 'running' : 'paused',
                }}
              />
            </div>
          )
        })}

        {/* Vignette */}
        <div style={styles.vignette} />

        {/* Controls overlay */}
        <div style={styles.controls}>
          <div style={styles.controlsLeft}>
            {!isReady ? (
              <div style={styles.loadingMsg}>
                <CircleNotch size={20} style={{ animation: 'spin 1s linear infinite' }} />
                <span>Loading images...</span>
              </div>
            ) : (
              <button
                style={styles.playBtn}
                onClick={isPlaying ? handlePause : handlePlay}
                disabled={!isReady}
              >
                {isPlaying
                  ? <Pause size={22} weight="fill" />
                  : <Play size={22} weight="fill" />
                }
              </button>
            )}
          </div>

          {title && <span style={styles.titleText}>{title}</span>}

          <div style={styles.controlsRight}>
            <select
              value={playbackRate}
              onChange={handleRateChange}
              style={styles.speedSelect}
            >
              {[0.75, 1, 1.25, 1.5].map(r => (
                <option key={r} value={r}>{r}x</option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </div>
  )
}

const styles = {
  root: {
    position: 'relative',
    width: '100%',
    maxWidth: '900px',
    margin: '0 auto',
    aspectRatio: '16 / 9',
    background: '#1a1410',
    overflow: 'hidden',
    borderRadius: '12px',
  },
  imageStack: {
    position: 'absolute',
    inset: 0,
  },
  imageSlide: {
    position: 'absolute',
    inset: 0,
    transition: 'opacity 0.8s ease-in-out',
    overflow: 'hidden',
  },
  image: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    transformOrigin: 'center center',
  },
  vignette: {
    position: 'absolute',
    inset: 0,
    boxShadow: 'inset 0 0 120px rgba(44,36,22,0.35)',
    zIndex: 2,
    pointerEvents: 'none',
  },
  controls: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 3,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '1.25rem 1.5rem',
    background: 'linear-gradient(to top, rgba(28,20,10,0.75) 0%, transparent 100%)',
  },
  controlsLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  controlsRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  loadingMsg: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    color: 'rgba(255,255,255,0.7)',
    fontSize: '0.85rem',
  },
  playBtn: {
    background: 'rgba(255,255,255,0.15)',
    border: '1px solid rgba(255,255,255,0.25)',
    borderRadius: '50%',
    width: '44px',
    height: '44px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'white',
    cursor: 'pointer',
    backdropFilter: 'blur(4px)',
    transition: 'background 0.15s',
  },
  titleText: {
    color: 'rgba(255,255,255,0.85)',
    fontSize: '0.9rem',
    fontFamily: 'var(--font-heading)',
    fontStyle: 'italic',
    maxWidth: '40%',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  speedSelect: {
    background: 'rgba(255,255,255,0.12)',
    border: '1px solid rgba(255,255,255,0.2)',
    borderRadius: '6px',
    color: 'white',
    padding: '0.3rem 0.5rem',
    fontSize: '0.85rem',
    cursor: 'pointer',
    backdropFilter: 'blur(4px)',
  },
}
