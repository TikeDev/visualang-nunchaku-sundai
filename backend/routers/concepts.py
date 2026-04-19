import json
import logging

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)
router = APIRouter()

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


class ConceptsRequest(BaseModel):
    transcript: list


@router.post("/concepts")
async def extract_concepts(body: ConceptsRequest):
    transcript_text = "\n".join(
        f"[{seg['start']:.1f}s] {seg['text']}" for seg in body.transcript
    )
    logger.info(f"Sending transcript to Claude ({len(transcript_text)} chars)")

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": transcript_text}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        concepts = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"Claude returned malformed JSON: {raw}")
        raise HTTPException(status_code=500, detail="LLM returned unparseable JSON")

    logger.info(f"Extracted {len(concepts)} concepts")
    return concepts
