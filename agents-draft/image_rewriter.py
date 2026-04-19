"""ImagePromptRewriter — recovery agent for bad images.

Called by /generate when a generated image fails a post-check (text detected
via vision, content-policy error, etc.). Returns a revised prompt to retry
once. Bounded to one rewrite per image to keep latency predictable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from . import base, prompts
from .graph import END, Graph

logger = logging.getLogger(__name__)


@dataclass
class Rewrite:
    revised_prompt: str
    reasoning: str


async def _rewrite_node(state: dict) -> str:
    user = (
        f"Original prompt: {state['original_prompt']}\n"
        f"Concept: {state['concept']}\n"
        f"Failure signal: {state['failure_signal']}\n\n"
        "Return the JSON object."
    )
    text = await base.run_claude(
        model=prompts.IMAGE_REWRITER_MODEL,
        system=prompts.IMAGE_REWRITER_SYSTEM,
        user=user,
        max_tokens=400,
    )
    parsed = base.parse_json_strict(text)
    state["result"] = Rewrite(
        revised_prompt=parsed["revised_prompt"],
        reasoning=parsed.get("reasoning", ""),
    )
    return END


_graph = Graph({"rewrite": _rewrite_node}, name="ImagePromptRewriter")


async def run(original_prompt: str, failure_signal: str, concept: str) -> Rewrite:
    """Entry point: rewrite a prompt that failed post-check or generation.

    Args:
        original_prompt: the prompt that produced a bad image or errored
        failure_signal: short description of what went wrong
            (e.g. "vision check detected letters on a sign in the output")
        concept: the original concept word/phrase for context
    """
    final = await _graph.run(
        initial_state={
            "original_prompt": original_prompt,
            "failure_signal": failure_signal,
            "concept": concept,
        },
        start="rewrite",
    )
    result: Rewrite = final["result"]
    logger.info("ImagePromptRewriter: %s", result.reasoning[:80])
    return result
