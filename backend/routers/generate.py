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

from config import NUNCHAKU_API_KEY, NUNCHAKU_BASE_URL, NUNCHAKU_MODEL, NUNCHAKU_NEGATIVE_PROMPT
from config import NUNCHAKU_TIER

logger = logging.getLogger(__name__)
router = APIRouter()

IMAGE_DIR = Path("/tmp/visualang_images")
IMAGE_DIR.mkdir(exist_ok=True)


def generate_image(prompt: str, model: str = NUNCHAKU_MODEL, tier: str = NUNCHAKU_TIER) -> str:
    start = time.time()
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
    b64_data = response.json()["data"][0]["b64_json"]
    img_bytes = base64.b64decode(b64_data)

    filename = f"{uuid.uuid4()}.jpg"
    filepath = IMAGE_DIR / filename
    filepath.write_bytes(img_bytes)

    elapsed = int((time.time() - start) * 1000)
    logger.info(f"Generated image in {elapsed}ms | model={model} tier={tier} | {prompt[:80]}")
    return str(filepath)


async def generate_images_stream(concepts: list):
    total = len(concepts)
    results = []
    for i, concept in enumerate(concepts):
        logger.info(f"Generating image {i + 1}/{total}: '{concept['concept']}'")
        filepath = await run_in_threadpool(generate_image, concept["image_prompt"])
        filename = Path(filepath).name
        image_url = f"/images/{filename}"
        results.append({"timestamp_seconds": concept["timestamp_seconds"], "image_url": image_url})
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
