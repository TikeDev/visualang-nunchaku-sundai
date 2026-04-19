# Visualang Runtime Agents

Three async agents live in [`agents/`](./agents/) and plug into the FastAPI
routers. They use the Anthropic SDK with tool use and a hand-rolled async
state-machine runner (no LangChain/LangGraph).

## Quick reference

| Agent | Entry point | Called from | Model | Purpose |
|---|---|---|---|---|
| TranscriptGate | `transcript_gate.run(transcript, title=, duration=)` | `/transcript` | Haiku 4.5 | Reject unusable transcripts before the pipeline spends money |
| ConceptExtractor | `concept_extractor.run(transcript)` | `/concepts` | Sonnet 4.6 (+ Haiku critique) | Draft → critique → fix loop for visual concepts |
| ImagePromptRewriter | `image_rewriter.run(prompt, failure_signal, concept)` | `/generate` (per image, on vision-check failure) | Haiku 4.5 | Rewrite prompts that produced bad images |

## Flow through the pipeline

```
POST /transcript          POST /concepts          POST /generate (stream)
      │                        │                         │
      ▼                        ▼                         ▼
  TranscriptGate           ConceptExtractor         per-image:
  (proceed/warn/           (3-node graph:          1. Nunchaku call
   reject)                  extract→critique        2. analyze_image tool (Haiku vision)
                            →fix)                   3. if has_text → ImagePromptRewriter
                                                       → regenerate once
```

## File layout

```
agents/
├── __init__.py           # exports transcript_gate, concept_extractor, image_rewriter
├── base.py               # Anthropic client wrapper, tool-use loop, OpenAI fallback
├── graph.py              # ~40-line async state machine
├── prompts.py            # system prompts + model IDs (all in one file)
├── tools.py              # 7 tools: 4 pure-Python, 3 sub-LLM (incl. vision)
├── transcript_gate.py    # single-node agent
├── concept_extractor.py  # 3-node graph
└── image_rewriter.py     # single-node agent
```

## Integration points (already wired)

- [`routers/transcript.py`](./routers/transcript.py) — the unified endpoint runs
  `TranscriptGate` after normalization for either YouTube JSON input or local
  audio upload. Rejects with HTTP 422. Verdict is returned in the response
  body under `gate: { verdict, reason, detected_language }` so the frontend
  can surface warnings.
- [`routers/concepts.py`](./routers/concepts.py) — replaced the naive single
  Claude call with `ConceptExtractor`.
- [`routers/generate.py`](./routers/generate.py) — each generated image is
  vision-checked via Haiku. On `has_text=true`, `ImagePromptRewriter` produces
  a revised prompt and the image is regenerated once (bounded to keep latency
  predictable).

## Env vars required

- `ANTHROPIC_API_KEY` — used by all three agents
- `OPENAI_API_KEY` — used only if Anthropic returns 5xx (fallback to `gpt-4.1`)
- `NUNCHAKU_API_KEY` — used by `/generate`, not by agents directly

## Model swaps

All model IDs live in [`agents/prompts.py`](./agents/prompts.py) (`SONNET`,
`HAIKU`, `OPENAI_FALLBACK`) and the per-agent `*_MODEL` constants. Swap there
to change model selection without touching agent logic.

## Cost notes

- Every generated image incurs one Haiku vision call (~$0.003). For an
  8-image video: +~$0.024 on top of ~$0.032 Nunchaku cost. Accepted for MVP;
  can be made opt-in later (only run on explicit user regenerate).
- `ConceptExtractor` critique pass is mostly deterministic Python; only the
  visualizability rating calls Haiku. Typical overhead: 1 extra Sonnet fix
  call only when concepts are flagged.

## Logging

Every agent and node logs via `logging.getLogger(__name__)`. Look for these
prefixes in `uvicorn` output:

- `[TranscriptGate]`, `[ConceptExtractor]`, `[ImagePromptRewriter]` — graph
  node transitions
- `claude <model>: ... in, ... out, ...ms` — every LLM call
- `openai gpt-4.1 fallback: ...ms` — fallback path took over

## Adding a new agent

1. Add the system prompt and `*_MODEL` constant to `prompts.py`
2. Add any new tools (schema + handler) to `tools.py`, plus a bundle near the
   bottom of the file
3. Create `<your_agent>.py` with one or more async node functions and a
   `Graph` wiring them together
4. Export an `async def run(...)` entry point
5. Register it in `__init__.py`
6. Call it from the appropriate router
