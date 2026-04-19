import logging
import re
import uuid
from pathlib import Path

import yt_dlp
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi

from agents import transcript_gate
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)
router = APIRouter()

IMAGE_DIR = Path("/tmp/visualang_images")
IMAGE_DIR.mkdir(exist_ok=True)


# --- Normalizers ---

def normalize_segment(segment: dict, source: str) -> dict:
    if source == "youtube":
        return {
            "text": segment["text"],
            "start": segment["start"],
            "duration": segment["duration"],
        }
    elif source == "whisper":
        return {
            "text": segment["text"],
            "start": segment["start"],
            "duration": segment["end"] - segment["start"],
        }


def normalize_transcript(segments: list, source: str) -> list:
    return [normalize_segment(s, source) for s in segments]


# --- Helpers ---

def get_video_info(video_url: str) -> dict:
    ydl_opts = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return {"title": info.get("title", "Untitled"), "duration": info.get("duration", 0)}


def extract_audio(video_url: str, output_base: str):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_base,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])


def transcribe_audio(audio_path: str) -> list:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    return normalize_transcript(response.segments, source="whisper")


def extract_video_id(url: str) -> str:
    patterns = [
        r"youtube\.com/watch\?v=([^&]+)",
        r"youtu\.be/([^?]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


# --- Routes ---

class YoutubeRequest(BaseModel):
    video_url: str


@router.post("/transcript/youtube")
async def transcript_youtube(body: YoutubeRequest):
    logger.info(f"Transcript request for YouTube URL: {body.video_url}")
    try:
        video_id = extract_video_id(body.video_url)
        logger.info(f"Extracted video ID: {video_id}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        ytt_api = YouTubeTranscriptApi()
        raw_transcript = ytt_api.fetch(video_id).to_raw_data()
        normalized = normalize_transcript(raw_transcript, "youtube")
        logger.info(f"Fetched transcript: {len(normalized)} segments")
    except Exception as e:
        logger.error(f"Transcript fetch failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch transcript: {e}")

    info: dict | None = None
    try:
        info = get_video_info(body.video_url)
        title = info["title"]
        logger.info(f"Video title: {title}")
    except Exception as e:
        logger.warning(f"Could not fetch video info: {e}")
        title = "Untitled"

    # Prefer yt-dlp duration; fall back to last segment end time.
    if info and info.get("duration"):
        duration = info["duration"]
    elif normalized:
        last = normalized[-1]
        duration = last["start"] + last["duration"]
    else:
        duration = 0
    verdict = await transcript_gate.run(normalized, title=title, duration=duration)
    if verdict.verdict == "reject":
        raise HTTPException(status_code=422, detail=f"Transcript rejected: {verdict.reason}")

    audio_base = str(IMAGE_DIR / video_id)
    audio_path = audio_base + ".mp3"
    try:
        extract_audio(body.video_url, audio_base)
        logger.info(f"Audio extracted to: {audio_path}")
    except Exception as e:
        logger.error(f"Audio extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Audio extraction failed: {e}")

    return {
        "transcript": normalized,
        "audio_path": audio_path,
        "title": title,
        "gate": {
            "verdict": verdict.verdict,
            "reason": verdict.reason,
            "detected_language": verdict.detected_language,
        },
    }


@router.post("/transcript/upload")
async def transcript_upload(file: UploadFile = File(...)):
    logger.info(f"Transcript upload: {file.filename}, size={file.size}")

    allowed = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    filename = f"{uuid.uuid4()}_{file.filename}"
    audio_path = IMAGE_DIR / filename
    try:
        audio_path.write_bytes(await file.read())
        logger.info(f"Saved upload to: {audio_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    try:
        normalized = transcribe_audio(str(audio_path))
        logger.info(f"Transcribed: {len(normalized)} segments")
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

    title = Path(file.filename).stem
    duration = (normalized[-1]["start"] + normalized[-1]["duration"]) if normalized else 0
    verdict = await transcript_gate.run(normalized, title=title, duration=duration)
    if verdict.verdict == "reject":
        raise HTTPException(status_code=422, detail=f"Transcript rejected: {verdict.reason}")

    return {
        "transcript": normalized,
        "audio_path": str(audio_path),
        "title": title,
        "gate": {
            "verdict": verdict.verdict,
            "reason": verdict.reason,
            "detected_language": verdict.detected_language,
        },
    }
