"""TranscriptGate — quality check before the pipeline commits.

Single-node agent: Claude (Haiku) decides proceed/warn/reject after inspecting
the transcript via count_words_per_minute, check_silence_ratio, and
detect_language_sample tools.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from . import base, prompts, tools
from .graph import END, Graph

logger = logging.getLogger(__name__)

Verdict = Literal["proceed", "warn", "reject"]


@dataclass
class GateResult:
    verdict: Verdict
    reason: str
    detected_language: str


async def _gate_node(state: dict) -> str:
    transcript = state["transcript"]
    title = state["title"]
    duration = state["duration"]

    handlers = tools.transcript_gate_handlers(transcript)

    user = (
        f"Title: {title}\n"
        f"Duration (s): {duration}\n"
        f"Segment count: {len(transcript)}\n\n"
        "Inspect the transcript using the available tools, then return your verdict JSON."
    )

    text = await base.run_claude_with_tools(
        model=prompts.TRANSCRIPT_GATE_MODEL,
        system=prompts.TRANSCRIPT_GATE_SYSTEM,
        user=user,
        tools=tools.TRANSCRIPT_GATE_TOOLS,
        tool_handlers=handlers,
        max_iterations=5,
    )

    try:
        parsed = base.parse_json_strict(text)
        state["result"] = GateResult(
            verdict=parsed["verdict"],
            reason=parsed["reason"],
            detected_language=parsed.get("detected_language", "unknown"),
        )
    except (ValueError, KeyError) as e:
        logger.warning("gate parse failed (%s), defaulting to warn", e)
        state["result"] = GateResult(
            verdict="warn",
            reason="quality check inconclusive — proceeding with caution",
            detected_language="unknown",
        )
    return END


_graph = Graph({"gate": _gate_node}, name="TranscriptGate")


async def run(transcript: list[dict], *, title: str, duration: float) -> GateResult:
    """Entry point: inspect transcript quality and return a verdict.

    Args:
        transcript: normalized segments [{text, start, duration}, ...]
        title: video title for context
        duration: total duration in seconds
    """
    if not transcript:
        return GateResult("reject", "empty transcript", "unknown")

    final = await _graph.run(
        initial_state={"transcript": transcript, "title": title, "duration": duration},
        start="gate",
    )
    result: GateResult = final["result"]
    logger.info("TranscriptGate: %s — %s", result.verdict, result.reason)
    return result
