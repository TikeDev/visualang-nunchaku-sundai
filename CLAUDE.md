# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repo contains two things:

**1. Nunchaku API SDK** — Python client wrapper, Gradio demo, multi-language examples, pytest tests for the Nunchaku image/video generation API. Lives in `demo/`, `examples/`, `tests/`.

**2. Visualang** — A comprehensible input visual companion for language learning. Takes a YouTube URL or local audio file, extracts transcript, uses Claude to identify visual moments, generates storybook illustrations via Nunchaku (~1s/image), and renders a downloadable `.mp4` with Ken Burns animations + synced audio. Lives in `frontend/` (React + Vite) and `backend/` (FastAPI).

The backend pipeline is guarded and self-corrected by three runtime agents (TranscriptGate, ConceptExtractor, ImagePromptRewriter) — see [`backend/AGENTS.md`](backend/AGENTS.md) for how they plug into the routers.

## Visualang Commands

```bash
# Backend (from repo root)
cd backend && pip install -r requirements.txt
cp backend/.env.example backend/.env  # fill in API keys
uvicorn main:app --reload             # runs on http://localhost:8000

# Frontend (from repo root)
pnpm install
cd frontend && pnpm dev               # runs on http://localhost:5173

# Required env vars in backend/.env:
# ANTHROPIC_API_KEY, OPENAI_API_KEY, NUNCHAKU_API_KEY
```

## Common Commands

```bash
# Install runtime deps
pip install requests Pillow

# Run the Gradio demo (all 4 endpoints + pipeline tab)
pip install gradio
python demo/app.py

# Run a single example
python examples/python/text_to_image.py

# Run full test suite (live API calls — requires NUNCHAKU_API_KEY)
pytest tests/ -v

# Run only error tests (no API key needed)
pytest tests/test_api.py::TestErrors -v
```

Set `NUNCHAKU_API_KEY=sk-nunchaku-...` before any API call or test.

## Architecture

### Core client: `demo/nunchaku.py` — `NunchakuClient`

Single class with four generation methods. All return raw `bytes`.

| Method | Endpoint |
|---|---|
| `text_to_image(prompt, model, size, tier, seed, ...)` | `/v1/images/generations` |
| `edit_image(image, prompt, model, ...)` | `/v1/images/edits` |
| `text_to_video(prompt, model, ...)` | `/v1/videos/generations` |
| `image_to_video(image, prompt, model, ...)` | `/v1/videos/generations` |

Private helpers: `_to_base64(image)` (accepts path/bytes/str), `_headers()`, `_post(path, payload, timeout)` (auto-retries on 429 via Retry-After).

### Demo: `demo/app.py`

Gradio app with 5 tabs: Text-to-Image, Edit Image, Text-to-Video, Image-to-Video, and Pipeline (chains all three).

### Tests: `tests/test_api.py`

Class per endpoint: `TestTextToImage`, `TestImageToImage`, `TestTextToVideo`, `TestImageToVideo`, `TestNunchakuClient`, `TestErrors`. All live tests hit the real API.

## API Quirks

**Image-to-Image input** — base64 data URI in `url` field, NOT multipart:
```json
{ "url": "data:image/jpeg;base64,..." }
```

**Image-to-Video input** — uses multimodal `messages` array:
```json
{
  "messages": [{
    "role": "user",
    "content": [
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
      {"type": "text", "text": "prompt"}
    ]
  }]
}
```

**OpenAI SDK compatibility** — only Text-to-Image works cleanly; Image-to-Image and video endpoints require raw `requests`.

**Rate limiting** — 429 is retried up to 12× with 10s waits; Retry-After header is respected.

## Models & Tiers

| Model | Type | Tiers |
|---|---|---|
| `nunchaku-qwen-image` | T2I | `fast` (28-step), `radically_fast` (4-step) |
| `nunchaku-flux.2-klein-9b` | T2I | `fast` only |
| `nunchaku-qwen-image-edit` | I2I | `fast`, `radically_fast` |
| `nunchaku-flux.2-klein-9b-edit` | I2I | `fast` only |
| `nunchaku-wan2.2-lightning-t2v` | T2V | `fast` only |
| `nunchaku-wan2.2-lightning-i2v` | I2V | `fast` only |
