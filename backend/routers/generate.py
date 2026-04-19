import base64
import json
import logging
import time
import uuid
from pathlib import Path

import requests
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from agents import image_rewriter
from agents.tools import analyze_image_handler
from config import (
    NUNCHAKU_API_KEY,
    NUNCHAKU_BASE_URL,
    NUNCHAKU_MODEL,
    NUNCHAKU_NEGATIVE_PROMPT,
    NUNCHAKU_TIER,
)

logger = logging.getLogger(__name__)
router = APIRouter()

IMAGE_DIR = Path("/tmp/visualang_images")
IMAGE_DIR.mkdir(exist_ok=True)


def _call_nunchaku(prompt: str, model: str, tier: str) -> str:
    """Call Nunchaku and return the raw base64 JPEG (pre-decode)."""
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
            "negative_prompt": NUNCHAKU_NEGATIVE_PROMPT,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["data"][0]["b64_json"]


def _save_b64(b64_data: str) -> str:
    filename = f"{uuid.uuid4()}.jpg"
    filepath = IMAGE_DIR / filename
    filepath.write_bytes(base64.b64decode(b64_data))
    return str(filepath)


def generate_image(prompt: str, model: str = NUNCHAKU_MODEL, tier: str = NUNCHAKU_TIER) -> dict:
    """Generate an image. Returns {filepath, b64} so callers can vision-check
    without re-reading the file."""
    start = time.time()
    b64_data = _call_nunchaku(prompt, model, tier)
    filepath = _save_b64(b64_data)
    elapsed = int((time.time() - start) * 1000)
    logger.info(f"Generated image in {elapsed}ms | model={model} tier={tier} | {prompt[:80]}")
    return {"filepath": filepath, "b64": b64_data}


async def _generate_with_recovery(concept: dict) -> dict:
    """Generate one image. If vision post-check flags text, rewrite the prompt
    and retry once. Returns the final {filepath, b64, prompt_used}."""
    original_prompt = concept["image_prompt"]
    concept_name = concept["concept"]

    result = await run_in_threadpool(generate_image, original_prompt)

    try:
        check = await analyze_image_handler(image_b64=result["b64"])
    except Exception as e:
        logger.warning("vision check raised, skipping recovery: %s", e)
        return {**result, "prompt_used": original_prompt}

    if not check.get("has_text"):
        return {**result, "prompt_used": original_prompt}

    failure_signal = f"vision check detected text in output: {check.get('details', '')}"
    logger.info("Image failed post-check for '%s' — rewriting prompt", concept_name)

    try:
        rewrite = await image_rewriter.run(
            original_prompt=original_prompt,
            failure_signal=failure_signal,
            concept=concept_name,
        )
    except Exception as e:
        logger.warning("rewriter failed, returning original image: %s", e)
        return {**result, "prompt_used": original_prompt}

    retry = await run_in_threadpool(generate_image, rewrite.revised_prompt)
    logger.info("Retry used revised prompt: %s", rewrite.reasoning[:80])
    return {**retry, "prompt_used": rewrite.revised_prompt}


async def generate_images_stream(concepts: list):
    total = len(concepts)
    results = []
    for i, concept in enumerate(concepts):
        logger.info(f"Generating image {i + 1}/{total}: '{concept['concept']}'")
        final = await _generate_with_recovery(concept)
        filename = Path(final["filepath"]).name
        image_url = f"/images/{filename}"
        results.append({
            "timestamp_seconds": concept["timestamp_seconds"],
            "image_url": image_url,
        })
        event = json.dumps({
            "index": i + 1,
            "total": total,
            "image_url": image_url,
            "concept": concept["concept"],
        })
        yield f"data: {event}\n\n"
    yield f"data: {json.dumps({'done': True, 'images': results})}\n\n"


class GenerateRequest(BaseModel):
    concepts: list


@router.post("/generate")
async def generate(body: GenerateRequest):
    return StreamingResponse(
        generate_images_stream(body.concepts),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
