# AGENTS.md

This file provides guidance to coding agents working in this repository.

## Session Phrase Mapping

When the user says `see the running browser`, interpret it as:
`check the Chrome DevTools MCP server`.

## Safety Rules

- Never publish passwords, API keys, or tokens to git, npm, Docker, logs, or screenshots.
- Never commit `.env` files. Keep `backend/.env`, `frontend/.env`, `.env`, and `.env.local` out of git.
- Before any commit, verify no secrets are staged.
- `.gitignore` already excludes the main env-file patterns; preserve that coverage if you edit it.

## Browser Rules

- Use the already-running Chrome Beta instance for browser debugging. Do not launch a new browser when the user refers to the running or open browser.
- Chrome Beta binary on macOS: `/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta`
- Expected remote debugging port: `9222`
- DevTools MCP should target `http://127.0.0.1:9222`
- If Chrome DevTools shows regular Chrome tabs instead of Chrome Beta, stop and ask the user to relaunch the correct browser.
- If nothing is available on port `9222`, ask the user to launch Chrome Beta. Do not launch it yourself.

## Project Overview

This repo has two related surfaces:

1. `Visualang`: a language-learning video companion that turns a YouTube URL or uploaded audio file into transcript-driven storybook visuals and an exported video. Frontend lives in `frontend/`; backend lives in `backend/`.
2. `Nunchaku API SDK + examples`: a Python client, Gradio demo, examples, and live API tests for Nunchaku image/video generation. These live in `demo/`, `examples/`, and `tests/`.

## Common Commands

```bash
# Install frontend deps
pnpm install

# Run both apps from repo root
pnpm dev

# Run backend only
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload

# Run frontend only
cd frontend
pnpm dev

# Build frontend
cd frontend
pnpm build

# Run the Gradio demo
pip install gradio
python demo/app.py

# Run tests
pytest tests/ -v
pytest tests/test_api.py::TestErrors -v
```

## Environment

- Backend expects `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and `NUNCHAKU_API_KEY` in `backend/.env`.
- Frontend uses `VITE_API_URL` and defaults to `http://localhost:8000`.
- Generated backend image assets are served from `/tmp/visualang_images` at `/images/*`.

## Architecture Summary

### Frontend

- Stack: React 19 + Vite.
- Entry files: `frontend/src/main.jsx`, `frontend/src/App.jsx`.
- `frontend/src/App.jsx` orchestrates the whole UX:
  - transcript fetch
  - concept extraction
  - SSE image generation
  - background export polling
- `frontend/src/config.js` holds the backend base URL.

### Backend

- Stack: FastAPI.
- Entry file: `backend/main.py`.
- Routers:
  - `backend/routers/transcript.py`
  - `backend/routers/concepts.py`
  - `backend/routers/generate.py`
  - `backend/routers/export.py`
- CORS is currently open to `*`.
- Health check: `GET /health`

### Runtime Agents

- Visualang backend includes three Anthropic-powered runtime agents in `backend/agents/`:
  - `TranscriptGate`
  - `ConceptExtractor`
  - `ImagePromptRewriter`
- They are wired through the backend routers and documented in detail in `backend/AGENTS.md`.

### SDK / Demo / Tests

- `demo/nunchaku.py` contains the `NunchakuClient`.
- `demo/app.py` is the Gradio demo.
- `examples/` contains curl, JavaScript, and Python examples.
- `tests/test_api.py` contains live API tests.

## Working Conventions

- Prefer focused edits over broad rewrites; this repo mixes product code and hackathon/demo code.
- Treat `backend/.env` as local-only. Never print or copy real secrets into docs, fixtures, or commit messages.
- Preserve the frontend/backend split. Shared behavior should usually be coordinated through API contracts, not duplicated logic.
- When changing the generation pipeline, check both `frontend/src/App.jsx` and the corresponding backend router payloads.
- When changing backend agents, also consult `backend/AGENTS.md` before editing prompts, tool wiring, or model selection.
- Live API tests spend credits and require valid keys; avoid running them unless the task needs it.

## Related Documentation

| File | Description | When to consult |
|------|-------------|-----------------|
| [backend/AGENTS.md](backend/AGENTS.md) | Runtime agent flow, files, model usage, router integration | Editing `backend/agents/*` or agent-backed routers |
| [visualang-prompt-for-claude-code.md](visualang-prompt-for-claude-code.md) | Full Visualang build spec, UX goals, implementation phases | Checking product requirements or phase-specific behavior |
| [README.md](README.md) | Nunchaku API usage, models, pricing, examples | Working on the SDK, demo app, or live API examples/tests |
