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

  useEffect(() => {
    loadedRef.current = 0
    setCurrentIndex(0)
    setIsReady(false)
    if (images.length === 0) return

    images.forEach(image => {
      const img = new Image()
      img.onload = () => {
        loadedRef.current += 1
        if (loadedRef.current === images.length) setIsReady(true)
      }
      img.onerror = () => {
        loadedRef.current += 1
        if (loadedRef.current === images.length) setIsReady(true)
      }
      img.src = image.image_url
    })
  }, [images])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    function syncCurrentImage() {
      const currentTime = audio.currentTime
      let nextIndex = 0
      for (let index = images.length - 1; index >= 0; index--) {
        if (currentTime >= images[index].timestamp_seconds) {
          nextIndex = index
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

  function handleRateChange(event) {
    const rate = parseFloat(event.target.value)
    setPlaybackRate(rate)
    if (audioRef.current) {
      audioRef.current.playbackRate = rate
    }
  }

  return (
    <section className="player-card" aria-label="Illustrated preview player">
      {audioSrc && <audio ref={audioRef} src={audioSrc} style={{ display: 'none' }} />}

      <div className="player-card__stage">
        {images.map((image, index) => {
          const duration = getImageDuration(images, index)
          const kbClass = KB_ANIMATIONS[index % 4]
          const isActive = index === currentIndex

          return (
            <div
              key={`${image.image_url}${index}`}
              className="player-card__slide"
              style={{
                opacity: isActive ? 1 : 0,
                zIndex: isActive ? 1 : 0,
              }}
            >
              <img
                src={image.image_url}
                alt=""
                className="player-card__image"
                style={{
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

        <div className="player-card__vignette" />

        <div className="player-card__controls">
          <div className="player-card__controls-main">
            {!isReady ? (
              <div className="player-card__loading" role="status" aria-live="polite">
                <CircleNotch size={22} style={{ animation: 'spin 1s linear infinite' }} />
                <span>Loading images...</span>
              </div>
            ) : (
              <button
                type="button"
                className="player-card__play-button"
                onClick={isPlaying ? handlePause : handlePlay}
                disabled={!isReady}
                aria-label={isPlaying ? 'Pause narration' : 'Play narration'}
              >
                {isPlaying ? <Pause size={22} weight="fill" /> : <Play size={22} weight="fill" />}
              </button>
            )}

            {title && <p className="player-card__title">{title}</p>}
          </div>

          <div className="player-card__controls-side">
            <label className="player-card__rate">
              <span className="sr-only">Playback speed</span>
              <select
                value={playbackRate}
                onChange={handleRateChange}
                className="player-card__select"
                aria-label="Playback speed"
              >
                {[0.75, 1, 1.25, 1.5].map(rate => (
                  <option key={rate} value={rate}>
                    {rate}x
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </div>
    </section>
  )
}
