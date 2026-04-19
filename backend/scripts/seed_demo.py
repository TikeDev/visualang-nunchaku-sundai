"""Seed a demo fixture by running the full pipeline once and saving the outputs.

Run from the backend/ directory with the venv active and .env populated:

    python scripts/seed_demo.py --slug spanish-news --url "https://www.youtube.com/watch?v=..."
    python scripts/seed_demo.py --slug my-clip --audio path/to/clip.mp3

Fixtures land in backend/demo_seeds/<slug>/ and include:
- transcript.json, concepts.json, images.json, meta.json
- audio.mp3 (copied from the pipeline's working file)
- image_NN.jpg (copied from /tmp/visualang_images)

The /demo/<slug> endpoint then serves these without hitting any live APIs,
so a single network hiccup during the pitch doesn't kill the demo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

# Ensure we can import backend modules when invoked from scripts/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents import concept_extractor, transcript_gate  # noqa: E402
from routers.generate import _generate_with_recovery  # noqa: E402
from routers.transcript import (  # noqa: E402
    extract_audio,
    extract_video_id,
    get_video_info,
    normalize_transcript,
    select_youtube_transcript,
    transcribe_audio,
)

SEEDS_DIR = ROOT / "demo_seeds"


async def _seed_from_youtube(slug: str, url: str, out_dir: Path) -> dict:
    video_id = extract_video_id(url)
    selected = select_youtube_transcript(video_id)
    raw = selected.fetch().to_raw_data()
    transcript = normalize_transcript(raw, "youtube")

    info = get_video_info(url) or {}
    title = info.get("title", "Untitled")
    duration = info.get("duration") or (
        transcript[-1]["start"] + transcript[-1]["duration"] if transcript else 0
    )

    audio_base = str(out_dir / "audio")
    extract_audio(url, audio_base)
    audio_path = audio_base + ".mp3"

    return {
        "transcript": transcript,
        "title": title,
        "duration": duration,
        "audio_path": audio_path,
        "source": {"type": "youtube", "url": url, "video_id": video_id},
    }


async def _seed_from_audio(slug: str, audio_file: Path, out_dir: Path) -> dict:
    dest = out_dir / "audio.mp3"
    shutil.copy(audio_file, dest)
    transcript = transcribe_audio(str(dest))
    title = audio_file.stem
    duration = (
        transcript[-1]["start"] + transcript[-1]["duration"] if transcript else 0
    )
    return {
        "transcript": transcript,
        "title": title,
        "duration": duration,
        "audio_path": str(dest),
        "source": {"type": "audio", "path": str(audio_file)},
    }


async def _run_pipeline(transcript: list, out_dir: Path) -> tuple[list, list]:
    import asyncio as _asyncio

    concepts = await concept_extractor.run(transcript)

    semaphore = _asyncio.Semaphore(3)
    tasks = [_generate_with_recovery(c, semaphore) for c in concepts]
    generated = await _asyncio.gather(*tasks)

    images = []
    for i, (concept, gen) in enumerate(zip(concepts, generated)):
        dest = out_dir / f"image_{i:02d}.jpg"
        shutil.copy(gen["filepath"], dest)
        images.append({
            "timestamp_seconds": concept["timestamp_seconds"],
            "image_url": f"/demo/{out_dir.name}/image_{i:02d}.jpg",
            "concept": concept["concept"],
        })
    return concepts, images


async def seed(slug: str, url: str | None, audio: Path | None) -> None:
    out_dir = SEEDS_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Seeding {slug} -> {out_dir}")

    if url:
        pre = await _seed_from_youtube(slug, url, out_dir)
    else:
        assert audio is not None
        pre = await _seed_from_audio(slug, audio, out_dir)

    verdict = await transcript_gate.run(
        pre["transcript"], title=pre["title"], duration=pre["duration"]
    )
    if verdict.verdict == "reject":
        raise SystemExit(f"TranscriptGate rejected: {verdict.reason}")
    print(f"Gate: {verdict.verdict} — {verdict.reason}")

    concepts, images = await _run_pipeline(pre["transcript"], out_dir)

    (out_dir / "transcript.json").write_text(
        json.dumps(pre["transcript"], ensure_ascii=False, indent=2)
    )
    (out_dir / "concepts.json").write_text(
        json.dumps(concepts, ensure_ascii=False, indent=2)
    )
    (out_dir / "images.json").write_text(
        json.dumps(images, ensure_ascii=False, indent=2)
    )
    (out_dir / "meta.json").write_text(json.dumps({
        "slug": slug,
        "title": pre["title"],
        "duration": pre["duration"],
        "source": pre["source"],
        "gate": {
            "verdict": verdict.verdict,
            "reason": verdict.reason,
            "detected_language": verdict.detected_language,
        },
        "image_count": len(images),
    }, ensure_ascii=False, indent=2))
    print(f"Done. {len(concepts)} concepts, {len(images)} images.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, help="URL-safe name for the fixture")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--url", help="YouTube URL")
    g.add_argument("--audio", type=Path, help="Local audio file")
    args = ap.parse_args()
    asyncio.run(seed(args.slug, args.url, args.audio))


if __name__ == "__main__":
    main()
