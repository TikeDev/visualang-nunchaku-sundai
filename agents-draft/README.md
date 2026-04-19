# Visualang Runtime Agents — Draft

These modules are written against the monorepo layout in `visualang_cc.md`. Once
your partner's scaffold lands at `visualang/backend/`, copy this folder to
`visualang/backend/agents/` — no rewrites needed.

## What's here

Three runtime agents used by the Visualang pipeline:

- `TranscriptGate` — decides whether a transcript is usable before the pipeline commits
- `ConceptExtractor` — self-critiquing concept generator (replaces a naive single-call `/concepts`)
- `ImagePromptRewriter` — recovery agent invoked when a generated image fails post-checks

Shared infrastructure:

- `base.py` — `Agent` base class with a tool-use loop, retries, Anthropic→OpenAI fallback, per-turn logging
- `graph.py` — ~40-line hand-rolled state machine (no framework)
- `tools.py` — tool implementations (regex, math, and sub-LLM critique tools)
- `prompts.py` — system prompts per agent

## Entry points

```python
from agents import transcript_gate, concept_extractor, image_rewriter

verdict = await transcript_gate.run(transcript, title="...", duration=312)
concepts = await concept_extractor.run(transcript)
revised = await image_rewriter.run(original_prompt, failure_signal, concept_context)
```

Each entry point is an `async def run(...)` that a FastAPI route calls directly.

## Config

Reads `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` from env (via `config.py` in the
backend once wired). Model IDs are centralized in `prompts.py` so you can swap
Sonnet↔Haiku without touching agent code.

## What this does NOT do

- No HTTP routing — routes live in `backend/routers/`, they call into these agents
- No image generation — `/generate` calls Nunchaku directly; `ImagePromptRewriter`
  only *rewrites prompts* when Nunchaku output fails a post-check
- No FFmpeg / export logic
