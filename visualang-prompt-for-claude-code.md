# Visualang — Claude Code Scaffold Prompt

## Project Overview

**Visualang** is a comprehensible input visual companion for language learning. It takes a YouTube URL (or local audio file), extracts the transcript, uses an LLM to identify key visual moments, generates storybook-style illustrations using Nunchaku (fast FLUX.2 diffusion inference — ~1 second per image), and renders them into a self-contained downloadable `.mp4` — audio + Ken Burns illustrated visuals synced together. A live browser preview plays while the video renders in the background.

**The core product is the downloaded video**, not the browser player. The browser player is a preview only.

---

## Stack

- **Frontend:** React + Vite, pnpm
- **Backend:** FastAPI (Python)
- **LLM:** Anthropic Claude API (Python SDK)
- **Image generation:** Nunchaku API (`https://api.nunchaku.dev`) — OpenAI-compatible, key from `https://sundai.nunchaku.dev`
- **Transcript (YouTube):** `youtube-transcript-api` v1.2.4+
- **Transcript (local audio):** OpenAI `gpt-4o-transcribe` (unknown quality uploads) or `gpt-4o-mini-transcribe` (YouTube, clean audio)
- **Audio extraction:** `yt-dlp`
- **Video export:** FFmpeg at 720p output
- **Monorepo structure:** `/frontend` and `/backend` in one repo

---

## Monorepo Structure

```
visualang/
├── README.md
├── .gitignore
├── frontend/
│   ├── package.json         # pnpm
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── config.js        # API base URL from env
│       └── components/
│           ├── Player.jsx        # preview player (hidden YouTube embed + image overlay)
│           ├── LoadingScreen.jsx
│           └── UrlInput.jsx      # handles both YouTube URL and local file upload
└── backend/
    ├── requirements.txt
    ├── main.py              # FastAPI app entry point
    ├── config.py            # System prompt + settings loaded from .env
    ├── .env.example
    └── routers/
        ├── transcript.py    # YouTube transcript OR Whisper for local files
        ├── concepts.py      # LLM concept extraction
        ├── generate.py      # Nunchaku image generation
        └── export.py        # FFmpeg video render + downloads
```

---

## Phase 1 — Scaffold + Hardcoded Player (DO THIS FIRST)

**Goal:** A working React player with Ken Burns animation and fade transitions, using hardcoded data. No APIs yet. This validates the core mechanic before touching any external services.

### Tasks:
1. Scaffold the full monorepo folder structure above
2. Initialize frontend with Vite + React using **pnpm**
3. Initialize backend with FastAPI
4. Install all dependencies (see below)
5. Build the `Player` component with:
   - Accepts an array of `{ timestamp_seconds, image_url }` objects
   - **Hidden** YouTube IFrame embed — audio plays but the video itself is not visible
   - Overlays generated images full-bleed on top of the hidden player
   - Polls the YouTube player's current time every 500ms
   - Fades between images at the correct timestamps using CSS transitions
   - **Ken Burns effect** on each image — slow pan + zoom using CSS keyframe animation. Randomize direction per image (zoom in/pan left, zoom out/pan right, etc.) so it doesn't feel repetitive. Duration should match how long the image is displayed.
   - For local audio input: use an HTML5 `<audio>` element instead of YouTube embed — same polling/sync logic applies
   - **Playback speed control** — a simple selector with options 0.75x, 1x, 1.25x, 1.5x
     - YouTube: `player.setPlaybackRate(rate)`
     - HTML5 audio: `audioElement.playbackRate = rate`
     - The time-polling sync logic works correctly at any speed since it reads actual elapsed time
   - Preloads all images before enabling playback
   - Shows a disabled play button with "Loading images..." until all images are preloaded
   - **Note:** the browser player is a preview only — the real product is the downloaded video
   - **No emojis anywhere in the UI** — use Phosphor Icons for all iconography
6. Hardcode a sample data array of 4–6 entries with real image URLs (use any public placeholder images) and realistic timestamps
7. Confirm the player works end-to-end with hardcoded data before moving to Phase 2

### Frontend dependencies (pnpm):
```
react-youtube
@phosphor-icons/react
```

### Backend dependencies (pip):
```
fastapi
uvicorn
python-dotenv
anthropic
openai
requests
youtube-transcript-api==1.2.4
yt-dlp
httpx
ffmpeg-python
python-multipart
flake8
```

### CORS — Add this immediately after `app = FastAPI()` in `main.py`, before anything else:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Frontend env (`.env`):
```
VITE_API_URL=http://localhost:8000
```

### Backend env (`backend/.env`):
```
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
NUNCHAKU_API_KEY=sk-nunchaku-...
```

### `src/config.js`:
```js
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
```

### `backend/config.py` — all settings in one place:
```python
import os
from dotenv import load_dotenv
load_dotenv()

# API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NUNCHAKU_API_KEY = os.getenv("NUNCHAKU_API_KEY")

# Nunchaku settings — change these to switch models without touching route logic
NUNCHAKU_MODEL = "nunchaku-flux.2-klein-9b"
NUNCHAKU_TIER = "fast"
NUNCHAKU_BASE_URL = "https://api.nunchaku.dev"
NUNCHAKU_NEGATIVE_PROMPT = "text, words, letters, signs, labels, watermark, logo, UI elements, captions"

# Claude settings
CLAUDE_MODEL = "claude-sonnet-4-6"

# System prompt
SYSTEM_PROMPT = """
You are a visual companion generator for language learning videos. Given a transcript with timestamps, identify 1 visual concept every 20-30 seconds that is concrete and visualizable.

For each concept return:
- timestamp_seconds (integer)
- concept (the word or phrase in the original language)
- image_prompt (English image generation prompt)

Rules for image_prompts:
- Describe only visual elements — no text, signs, labels, letters, or words anywhere in the scene
- Simple composition with one clear primary subject
- Translate concepts to English even if the transcript is in another language
- Skip abstract or non-visual moments — pick the next concrete one instead
- End every prompt with: "children's storybook illustration, simple composition, one main subject, soft colors, painterly, no text, no letters"

Output a JSON array only. No preamble, no explanation, no markdown.
"""
```

### `.gitignore` (repo root):
```
# Frontend
node_modules/
frontend/dist/
frontend/.env

# Backend
backend/.env
backend/__pycache__/
backend/.venv/
*.pyc
*.pyo

# Generated files
/tmp/visualang_images/

# OS
.DS_Store
```

---

## Phase 2 — Transcript + LLM Concept Extraction

**Goal:** Wire up YouTube transcript fetching and Claude API concept extraction.

### Important — `youtube-transcript-api` v1.2.4 syntax (breaking change from older versions):
```python
# CORRECT — use this
from youtube_transcript_api import YouTubeTranscriptApi
ytt_api = YouTubeTranscriptApi()
transcript = ytt_api.fetch("VIDEO_ID").to_raw_data()
# Returns: [{ "text": "...", "start": 12.4, "duration": 2.1 }, ...]

# WRONG — do not use these (removed in v1.x)
# YouTubeTranscriptApi.get_transcript(...)
# YouTubeTranscriptApi.list_transcripts(...)
```

### System prompt — defined in `config.py` (see Phase 1 setup), not inline here. Import it:
```python
from config import SYSTEM_PROMPT, CLAUDE_MODEL
```

### `/routers/transcript.py`:
- `POST /transcript` — accepts either `{ video_url: string }` (YouTube) or a local audio file upload
- **YouTube path:** extract video ID, fetch transcript using new API syntax, kick off `yt-dlp` audio extraction saving to a temp file, and fetch the video title using `yt-dlp` info extraction. Return title alongside transcript.
- **Local file path:** accept uploaded audio file, use the original filename as the title, send to OpenAI for transcription. Use `gpt-4o-transcribe` — unknown audio quality, prioritize accuracy ($0.006/min). Requires `response_format="verbose_json"` and `timestamp_granularities=["segment"]` to get timestamps.
- Both paths return: `{ transcript: [...], audio_path: string, title: string }` — title is displayed persistently in the UI
- **Both paths must pass transcript through the normalizer before returning**
- Log which path was taken, title, and transcript segment count

### Fetching YouTube title via `yt-dlp`:
```python
def get_video_info(video_url: str) -> dict:
    ydl_opts = {'quiet': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return {"title": info.get("title", "Untitled"), "duration": info.get("duration", 0)}
```

### Transcript normalizer — put in `routers/transcript.py`:
```python
def normalize_segment(segment: dict, source: str) -> dict:
    """Normalize transcript segments from any source into a consistent format."""
    if source == "youtube":
        # youtube-transcript-api format: { text, start, duration }
        return {
            "text": segment["text"],
            "start": segment["start"],
            "duration": segment["duration"]
        }
    elif source == "whisper":
        # OpenAI Whisper/gpt-4o-transcribe verbose_json format: { text, start, end }
        return {
            "text": segment["text"],
            "start": segment["start"],
            "duration": segment["end"] - segment["start"]
        }

def normalize_transcript(segments: list, source: str) -> list:
    return [normalize_segment(s, source) for s in segments]
```

### OpenAI transcription call (local file path):
```python
from openai import OpenAI
client = OpenAI()

def transcribe_audio(audio_path: str) -> list:
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",         # full model for unknown quality uploads
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"] # required for timestamps
        )
    return normalize_transcript(response.segments, source="whisper")

### `yt-dlp` audio extraction:
```python
import yt_dlp

def extract_audio(video_url: str, output_path: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
```

### `/routers/concepts.py`:
- `POST /concepts` — accepts transcript array, sends to Claude API using `anthropic` Python SDK, parses JSON response, returns array of `{ timestamp_seconds, concept, image_prompt }`
- Use `claude-sonnet-4-6` — best JSON reliability for strict structured output, worth the small cost premium over Haiku
- Set `max_tokens=1000`
- If Claude returns malformed JSON, log the raw response at WARNING level and raise a clear error — do not silently return empty results

---

## Phase 3 — Nunchaku Image Generation

**Goal:** Generate storybook illustrations for each concept using the Nunchaku API.

### API Details (no longer a placeholder — fully known):
- **Base URL:** `https://api.nunchaku.dev`
- **Auth:** `Authorization: Bearer sk-nunchaku-...` (or `X-API-Key: sk-nunchaku-...`)
- **Endpoint:** `POST /v1/images/generations`
- **Get your key:** `https://sundai.nunchaku.dev` (Google login, $10 free credits automatically)
- **Pricing:** `$0.002/image` at `radically_fast`, `$0.004/image` at `fast` — $10 covers 2,500–5,000 images

### Confirmed speed benchmarks (tested April 19, 2026):
| Model | Tier | Speed |
|-------|------|-------|
| `nunchaku-flux.2-klein-9b` | fast | ~1s/image |
| `nunchaku-qwen-image` | radically_fast | ~1.5s/image |
| `nunchaku-qwen-image` | fast | ~13s/image |

**Use `nunchaku-flux.2-klein-9b` fast as the default.** It is the fastest and produces good storybook quality. At 1s/image, 8 images generates in ~8 seconds — the loading experience is fast enough that progress states will feel snappy rather than slow.

**Do not use `nunchaku-qwen-image` fast** — 13s/image is unacceptably slow for this use case.

### `generate_image()` function in `/routers/generate.py`:
```python
import requests
import base64
import os
import uuid
from pathlib import Path

NUNCHAKU_API_KEY = os.getenv("NUNCHAKU_API_KEY")
NUNCHAKU_BASE_URL = "https://api.nunchaku.dev"
IMAGE_OUTPUT_DIR = Path("/tmp/visualang_images")
IMAGE_OUTPUT_DIR.mkdir(exist_ok=True)

def generate_image(prompt: str, model: str = "nunchaku-flux.2-klein-9b", tier: str = "fast") -> str:
    """
    Generate a storybook illustration from a prompt.
    Returns a local file path that the backend serves as a static URL.
    """
    response = requests.post(
        f"{NUNCHAKU_BASE_URL}/v1/images/generations",
        headers={
            "Authorization": f"Bearer {NUNCHAKU_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
            "tier": tier,
            "response_format": "b64_json",
        },
        timeout=60,
    )
    response.raise_for_status()
    b64_data = response.json()["data"][0]["b64_json"]
    img_bytes = base64.b64decode(b64_data)

    # Save to temp file and return path
    filename = f"{uuid.uuid4()}.jpg"
    filepath = IMAGE_OUTPUT_DIR / filename
    filepath.write_bytes(img_bytes)
    return str(filepath)
```

### `/routers/generate.py`:
- `POST /generate` — accepts array of `{ timestamp_seconds, concept, image_prompt }`, calls `generate_image()` for each, returns array of `{ timestamp_seconds, image_url }`
- Process images **sequentially** — one at a time to avoid rate limits and GPU pressure
- The backend must **serve the saved images as static files** so the frontend can load them by URL — mount a static files route in `main.py`:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/images", StaticFiles(directory="/tmp/visualang_images"), name="images")
```
- Return image URLs as `http://localhost:8000/images/{filename}` — frontend loads them directly
- **SSE progress streaming** — emit one event per image as it completes so frontend shows "Generating image 3 of 8..." in real time
- Log each generation: model, tier, prompt (truncated to 80 chars), duration in ms

### `UrlInput` component spec:
- Two modes: YouTube URL input and local file upload — toggled by the user
- **YouTube mode:** text input, validate that the URL contains `youtube.com/watch?v=` or `youtu.be/` before submitting, show inline error if invalid
- **File upload mode:** accept `.mp3`, `.wav`, `.m4a`, `.aac`, `.ogg` only, show file size limit of 25MB (OpenAI Whisper limit), display selected filename once chosen
- Submit button disabled until valid input is provided
- Both modes feed into the same pipeline after submission

### SSE progress streaming — FastAPI side (`/routers/generate.py`):
```python
from fastapi.responses import StreamingResponse
import json

async def generate_images_stream(concepts: list):
    total = len(concepts)
    results = []
    for i, concept in enumerate(concepts):
        filepath = generate_image(concept["image_prompt"])
        filename = Path(filepath).name
        image_url = f"/images/{filename}"
        results.append({"timestamp_seconds": concept["timestamp_seconds"], "image_url": image_url})
        yield f"data: {json.dumps({'index': i + 1, 'total': total, 'image_url': image_url, 'concept': concept['concept']})}\n\n"
    yield f"data: {json.dumps({'done': True, 'images': results})}\n\n"

@router.post("/generate")
async def generate(concepts: list):
    return StreamingResponse(generate_images_stream(concepts), media_type="text/event-stream")
```

### SSE consumption — React side:
```js
const eventSource = new EventSource(`${API_URL}/generate`); // use fetch POST with ReadableStream for POST requests
// Better: use fetch with body and read the stream manually
const response = await fetch(`${API_URL}/generate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ concepts }),
});
const reader = response.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const lines = decoder.decode(value).split('\n').filter(l => l.startsWith('data: '));
  for (const line of lines) {
    const data = JSON.parse(line.slice(6));
    if (data.done) { /* pipeline complete */ }
    else { /* update progress: data.index, data.total, data.concept */ }
  }
}
```
```
"text, words, letters, signs, labels, watermark, logo, UI elements, captions"
```
Add this as `negative_prompt` in the request body to reinforce the no-text constraint from the system prompt.

### Frontend `LoadingScreen` component:
- Show clearly labeled progress: step name + count (e.g. "Fetching transcript...", "Extracting concepts...", "Generating image 3 of 8...")
- Each step should have a visible state: pending, in progress, complete (Phosphor icons per state)
- Do not show a generic spinner — the user should always know exactly what is happening and how far along they are

---

## Phase 4 — Full Pipeline Wiring

**Goal:** Connect all phases into one flow triggered by a YouTube URL input.

### Flow:
1. User pastes YouTube URL or uploads local audio file → `UrlInput` component
2. Frontend calls `POST /transcript` → gets transcript + audio path
3. Frontend calls `POST /concepts` → gets timestamped concepts + image prompts
4. Frontend calls `POST /generate` → gets image URLs with live progress updates
5. Preview player loads — hidden audio + Ken Burns images synced in browser
6. `POST /export` kicks off in background — FFmpeg renders the real `.mp4`
7. Download button appears when export is ready

### `App.jsx` state machine (keep it simple):
```
idle → loading_transcript → loading_concepts → generating_images → preview_ready → exporting → done
```
- `preview_ready` — browser player is active, export is running in background
- `exporting` — show a subtle background progress indicator, don't block the preview
- `done` — download button appears for: video `.mp4`, transcript `.txt`, images `.zip`

Each state maps to a clear UI state. Never leave the user staring at a blank or ambiguous screen.

---

## Phase 5 — Video Export (build last, only if time permits)

**Goal:** Render a self-contained downloadable `.mp4` with ripped audio + Ken Burns illustrated images.

### `/routers/export.py`:
- `POST /export` — accepts array of `{ timestamp_seconds, image_url, duration_seconds }` + `audio_path` (from transcript step)
- Downloads images locally to a temp directory
- Uses FFmpeg `zoompan` filter to replicate Ken Burns effect per image
- Mixes with the extracted audio track
- **Output resolution: 720p** — do not render at 1080p, it's unnecessarily slow for this use case
- Returns downloadable `.mp4`
- Runs asynchronously so it doesn't block the preview player

### FFmpeg output settings:
```python
# Target 720p, reasonable quality, fast enough for hackathon demo
ffmpeg_args = [
    '-vf', 'scale=1280:720',
    '-c:v', 'libx264',
    '-preset', 'fast',
    '-crf', '23',
    '-c:a', 'aac',
    '-b:a', '192k',
]
```

### Also provide as separate downloads (these are easy wins — do them):
- **Transcript** as `.txt` — plain text, one line per segment with timestamp prefix
- **Generated images** as `.zip` — all images named `{index}_{timestamp}_{concept}.png`

---

## UX Spec

### Landing (idle state)
- Clean input area with two options: paste a YouTube URL or upload a local audio file
- Phosphor icons differentiate the two input types
- No other clutter

### Loading screen
- Video title (fetched via `yt-dlp` metadata for YouTube, filename for local uploads) displayed persistently at the top from submission through to done state
- Each pipeline step labeled with current status — pending, in progress, complete — with a Phosphor icon per state:
  1. Fetching transcript
  2. Extracting concepts
  3. Generating image X of Y
- No generic spinners — user always knows exactly what step and how far along
- Given ~1s/image generation speed, steps will feel snappy — loading screen should reflect that energy, not feel like a waiting room

### Network error handling
- Auto-retry once silently on any API failure
- On second failure: show "Connection issue, retrying..." in the affected step
- On third failure: clear error message explaining what failed + "Try again" button that restarts the full pipeline from the input screen
- Never silent failure — always surface errors clearly

### Preview ready (player state)
- First image displayed as a **static frame** before play is pressed — no Ken Burns yet
- Video title or filename shown persistently
- Play button (Phosphor icon), playback speed selector (0.75x, 1x, 1.25x, 1.5x)
- Subtle background indicator that video export is still rendering
- "Start over" button always visible — resets to landing without requiring a page refresh

### Playback
- Audio starts, images **crossfade** at correct timestamps — fade **interrupts** Ken Burns mid-animation, does not wait for it to complete
- Ken Burns begins on each image the moment it appears and runs for the full display duration
- Playback speed control active throughout

### Export ready (done state)
- Export indicator **replaced in place** by download buttons — video `.mp4`, transcript `.txt`, images `.zip`
- Player remains fully active — user can keep watching while downloading
- "Start over" button still visible

### Responsive layout
- Confirmed on desktop, tablet, and mobile
- Player should be full-bleed on all screen sizes
- Controls should reflow gracefully on narrow viewports

---

## Design Direction

The UI should feel warm, editorial, and storybook-adjacent — not corporate or generic. Reference the aesthetic of a beautifully designed language learning app, not a SaaS dashboard.

- **Typography:** Choose a distinctive, characterful font pairing. Avoid Inter, Roboto, Arial, Space Grotesk. Consider something with warmth and personality for headings, paired with a readable serif or humanist sans for body.
- **Color:** Warm, muted palette. Think aged paper, soft terracotta, sage green, warm cream. Avoid purple gradients and cold blues.
- **Icons:** Use **Phosphor Icons** (`@phosphor-icons/react`) for all iconography — play, pause, download, speed, upload, etc. **No emojis anywhere in the UI**, including loading states, buttons, and labels.
- **Player:** Full-bleed image display with the Ken Burns animation. Subtle vignette overlay. Clean minimal controls including the playback speed selector (0.75x, 1x, 1.25x, 1.5x) — style it to feel like part of the player, not a dropdown afterthought.
- **Loading screen:** Thoughtful, not an afterthought. Each step clearly labeled with a Phosphor icon per state. Progress feels intentional.
- **Overall:** Feels like it was designed, not generated.

---

## Pre-commit Hooks (Git)

Set up pre-commit hooks using **husky** + **lint-staged** (frontend) and **pre-commit** (backend). These run automatically on every `git commit` and block the commit if anything fails.

### Setup steps:

**1. Install husky and lint-staged in the repo root:**
```bash
pnpm add -D husky lint-staged -w
pnpm exec husky init
```

**2. `.husky/pre-commit`** — this file runs on every commit:
```sh
#!/bin/sh
. "$(dirname "$0")/_/husky.sh"

# Frontend: lint + build
cd frontend && pnpm lint && pnpm build

# Backend: lint
cd ../backend && python -m flake8 . --max-line-length=100 --exclude=__pycache__,.venv
```

**3. Root `package.json`** — add lint-staged config:
```json
{
  "lint-staged": {
    "frontend/src/**/*.{js,jsx}": ["eslint --fix", "prettier --write"],
    "backend/**/*.py": ["flake8 --max-line-length=100"]
  }
}
```

**4. Frontend — ensure ESLint and Prettier are configured:**
```bash
pnpm add -D eslint prettier eslint-config-prettier -w
```
Add `.prettierrc` at repo root:
```json
{
  "semi": false,
  "singleQuote": true,
  "tabWidth": 2,
  "printWidth": 100
}
```

**5. Backend — add flake8 to requirements:**
```
flake8
```
Add `.flake8` at `backend/` root:
```ini
[flake8]
max-line-length = 100
exclude = __pycache__,.venv
```

### What gets blocked:
- ESLint errors in any `.js` or `.jsx` file
- A broken frontend build (`pnpm build` fails)
- flake8 errors in any `.py` file

### What does NOT block (intentional):
- TypeScript errors (not using TS in this project)
- Warnings — only errors block commits

---

## Logging

Set up consistent, readable logging throughout the backend so it's easy to see what's happening when running locally.

### Backend (`main.py`):
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
```

### In every router, use a named logger:
```python
import logging
logger = logging.getLogger(__name__)
```

### Log these events at minimum:
- **Transcript:** video ID extracted, transcript fetched (log segment count), any fetch errors
- **Concepts:** sending transcript to Claude (log character count), concepts received (log count), JSON parse errors
- **Generate:** each image generation start/complete with index ("Generating image 2/8: 'a bird flying south'"), model used, duration in ms per image
- **Export:** FFmpeg command being run, output file size on completion, any FFmpeg errors
- **All routes:** request received (method + path), response time in ms

### Log levels:
- `INFO` — normal flow (request received, step completed, counts)
- `WARNING` — something unexpected but recoverable (empty transcript, Claude returned malformed JSON — log raw response)
- `ERROR` — something failed (API call failed, FFmpeg crashed — log full exception)

### Frontend:
- `console.log` at each state transition: `[Visualang] State: loading_transcript`, `[Visualang] State: generating_images (3/8)`, etc.
- `console.error` on any failed fetch with the full error object
- Prefix all logs with `[Visualang]` so they're easy to filter in DevTools

---

## Key Constraints & Reminders

- Use **pnpm** for all frontend package management, never npm
- Use `claude-sonnet-4-6` for concept extraction — do not use deprecated `claude-sonnet-4-20250514`
- Use `gpt-4o-mini-transcribe` for YouTube path (clean audio, $0.003/min), `gpt-4o-transcribe` for local file uploads (unknown quality, $0.006/min)
- Always call OpenAI transcription with `response_format="verbose_json"` and `timestamp_granularities=["segment"]` — plain text response has no timestamps
- Always normalize transcript through `normalize_transcript()` before passing downstream — Whisper uses `end`, youtube-transcript-api uses `duration`
- CORS middleware must be added **first** in `main.py` before any routes
- Use **new** `youtube-transcript-api` syntax (`ytt_api.fetch()`) — the old `get_transcript()` static method was removed in v1.x
- All loading states must be explicit and informative — no generic spinners
- Ken Burns animation duration must match the display duration of each image
- Images must be fully preloaded before playback is enabled
- Nunchaku API key goes in `backend/.env` as `NUNCHAKU_API_KEY` — never hardcoded
- Use `nunchaku-flux.2-klein-9b` at `fast` tier as the default — confirmed ~1s/image, best speed/quality tradeoff. `nunchaku-qwen-image` at `radically_fast` is the fallback if needed (~1.5s/image). Never use `nunchaku-qwen-image` at `fast` (~13s/image — too slow). Both configurable in `config.py`
- Always include `negative_prompt: "text, words, letters, signs, labels, watermark, logo, UI elements, captions"` in every Nunchaku request
- Backend must serve generated images as static files via `/images` mount — frontend loads by URL, never raw base64
- System prompt lives in `config.py`, not inline in route logic
- Backend URL comes from `VITE_API_URL` env variable in frontend — never hardcoded
- **The browser player is a preview only** — the real product is the downloaded `.mp4`
- The YouTube IFrame embed in the player must be **visually hidden** — audio plays, video does not show
- For local audio uploads, use an HTML5 `<audio>` element — same sync polling logic as YouTube
- FFmpeg export runs **asynchronously** — do not block the preview player while it renders
- **720p output only** — do not render at 1080p
- `yt-dlp` handles audio extraction for YouTube URLs — audio path is passed through the pipeline and used by the export router
- `UrlInput` component handles both YouTube URL input and local file upload — same pipeline after the transcript step
- **No emojis anywhere in the UI** — use Phosphor Icons (`@phosphor-icons/react`) for all icons
- **Fallback LLM:** if the Anthropic API is down, swap `claude-sonnet-4-6` for `gpt-4.1` from OpenAI — you'll already have an OpenAI key for transcription. The system prompt and response parsing are identical.

---

## Post-MVP / Nice-to-Haves

Do not build these during the hackathon. They are documented here for the pitch roadmap and future development.

**UX & Player:**
- Resumable pipeline — if image generation fails at step 6/8, retry from that step rather than restarting the entire pipeline from the input screen
- Adjustable image frequency — let the user control how often images are generated (e.g. every 15s vs 30s) rather than the hardcoded 20-30s in the system prompt
- Style selector — let the user choose illustration style instead of hardcoded storybook (e.g. watercolor, ink sketch, flat illustration)
- Language selector — explicitly tell the pipeline what language the video is in rather than relying on the LLM to detect it

**Annotations & Visuals:**
- SVG annotation overlays — arrows, motion lines, and directional cues layered on top of generated images (e.g. an arrow showing a bird flying south). LLM outputs optional annotation data, frontend renders SVG on top of the image. Removed from MVP due to diffusion model spatial unreliability.

**Anki Integration:**
- Anki card export — format the generated images + transcript segments + concepts into an Anki-compatible `.apkg` file for direct import. Each card: concept on front, illustrated image + timestamp context on back.

**Content:**
- Support for non-YouTube URLs (direct video links, Vimeo, etc.) via `yt-dlp` which already supports many platforms
- Playlist support — process a full YouTube playlist and generate a multi-video illustrated export
