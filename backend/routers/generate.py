import asyncio
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
from routers import metrics

logger = logging.getLogger(__name__)
router = APIRouter()

IMAGE_DIR = Path("/tmp/visualang_images")
IMAGE_DIR.mkdir(exist_ok=True)

# Cap concurrent Nunchaku calls to avoid rate limits while still parallelizing.
# Tuned for the hackathon free tier — increase if the provider allows more RPS.
MAX_CONCURRENT_GENERATIONS = 3


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
    elapsed_ms = int((time.time() - start) * 1000)
    metrics.record("nunchaku_generate_ms", elapsed_ms)
    logger.info(f"Generated image in {elapsed_ms}ms | model={model} tier={tier} | {prompt[:80]}")
    return {"filepath": filepath, "b64": b64_data}


async def _generate_with_recovery(concept: dict, semaphore: asyncio.Semaphore) -> dict:
    """Generate one image with bounded concurrency. If vision post-check flags
    text, rewrite the prompt and retry once."""
    async with semaphore:
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
        metrics.record("rewriter_triggered", 1)

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
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)

    # Launch all tasks up front; stream each event as its image completes,
    # preserving original concept order in the final results.
    async def _one(i: int, concept: dict):
        logger.info(f"Generating image {i + 1}/{total}: '{concept['concept']}'")
        final = await _generate_with_recovery(concept, semaphore)
        return i, concept, final

    tasks = [asyncio.create_task(_one(i, c)) for i, c in enumerate(concepts)]
    results_by_index: dict[int, dict] = {}
    completed = 0
    t0 = time.time()

    try:
        for coro in asyncio.as_completed(tasks):
            i, concept, final = await coro
            completed += 1
            filename = Path(final["filepath"]).name
            image_url = f"/images/{filename}"
            results_by_index[i] = {
                "timestamp_seconds": concept["timestamp_seconds"],
                "image_url": image_url,
            }
            event = json.dumps({
                "index": completed,
                "total": total,
                "image_url": image_url,
                "concept": concept["concept"],
            })
            yield f"data: {event}\n\n"

        ordered = [results_by_index[i] for i in range(total)]
        metrics.record("generate_batch_ms", int((time.time() - t0) * 1000))
        metrics.record("generate_batch_size", total)
        yield f"data: {json.dumps({'done': True, 'images': ordered})}\n\n"
    except Exception as e:
        # Cancel any still-running tasks so a single failure doesn't leak workers.
        for t in tasks:
            if not t.done():
                t.cancel()
        logger.exception("Image generation stream failed")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


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
