import asyncio
import logging
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

IMAGE_DIR = Path("/tmp/visualang_images")
IMAGE_DIR.mkdir(exist_ok=True)

# In-memory job registry
jobs: dict = {}


class ExportImage(BaseModel):
    timestamp_seconds: float
    image_url: str
    duration_seconds: float
    concept: str = ""


class ExportRequest(BaseModel):
    audio_path: str
    images: list[ExportImage]
    transcript: list = []


async def run_ffmpeg_export(job_id: str, audio_path: str, images: list, output_path: str):
    jobs[job_id]["status"] = "running"
    try:
        # Build concat demuxer input file
        concat_file = IMAGE_DIR / f"{job_id}_concat.txt"
        lines = []
        for img in images:
            filename = Path(urlparse(img["image_url"]).path).name
            img_path = IMAGE_DIR / filename
            duration = img.get("duration_seconds", 25)
            lines.append(f"file '{img_path}'")
            lines.append(f"duration {duration}")
        # Last image needs to be listed again for concat demuxer
        if lines:
            last_filename = Path(urlparse(images[-1]["image_url"]).path).name
            lines.append(f"file '{IMAGE_DIR / last_filename}'")
        concat_file.write_text("\n".join(lines))

        ffmpeg_args = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-i", audio_path,
            "-vf", "scale=1280:720,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path,
        ]
        logger.info(f"Running FFmpeg export for job {job_id}")
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f"FFmpeg failed for job {job_id}: {stderr.decode()}")
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = stderr.decode()
            return

        output_size = Path(output_path).stat().st_size
        logger.info(f"FFmpeg export complete for job {job_id}: {output_size} bytes")
        jobs[job_id]["status"] = "done"
        jobs[job_id]["video_path"] = output_path
        concat_file.unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Export failed for job {job_id}: {e}")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@router.post("/export")
async def start_export(body: ExportRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    output_path = str(IMAGE_DIR / f"{job_id}.mp4")

    images_dicts = [img.model_dump() for img in body.images]
    jobs[job_id] = {"status": "pending", "video_path": None}

    background_tasks.add_task(
        run_ffmpeg_export, job_id, body.audio_path, images_dicts, output_path
    )

    # Also write transcript txt and images zip immediately
    if body.transcript:
        txt_path = IMAGE_DIR / f"{job_id}_transcript.txt"
        lines = []
        for seg in body.transcript:
            start = int(seg.get("start", 0))
            mm, ss = divmod(start, 60)
            lines.append(f"[{mm:02d}:{ss:02d}] {seg.get('text', '')}")
        txt_path.write_text("\n".join(lines))
        jobs[job_id]["transcript_path"] = str(txt_path)

    zip_path = IMAGE_DIR / f"{job_id}_images.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for i, img in enumerate(body.images):
            filename = Path(urlparse(img.image_url).path).name
            img_path = IMAGE_DIR / filename
            if img_path.exists():
                ts = int(img.timestamp_seconds)
                concept = img.concept.replace(" ", "_")[:40]
                zf.write(img_path, f"{i:02d}_{ts}s_{concept}.jpg")
    jobs[job_id]["zip_path"] = str(zip_path)

    return {"job_id": job_id}


@router.get("/export/{job_id}")
async def get_export_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@router.get("/export/{job_id}/video")
async def download_video(job_id: str):
    if job_id not in jobs or jobs[job_id].get("status") != "done":
        raise HTTPException(status_code=404, detail="Video not ready")
    return FileResponse(jobs[job_id]["video_path"], media_type="video/mp4",
                        filename="visualang.mp4")


@router.get("/export/{job_id}/transcript")
async def download_transcript(job_id: str):
    if job_id not in jobs or "transcript_path" not in jobs[job_id]:
        raise HTTPException(status_code=404, detail="Transcript not available")
    return FileResponse(jobs[job_id]["transcript_path"], media_type="text/plain",
                        filename="transcript.txt")


@router.get("/export/{job_id}/images")
async def download_images(job_id: str):
    if job_id not in jobs or "zip_path" not in jobs[job_id]:
        raise HTTPException(status_code=404, detail="Images zip not available")
    return FileResponse(jobs[job_id]["zip_path"], media_type="application/zip",
                        filename="visualang_images.zip")
