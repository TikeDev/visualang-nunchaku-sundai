import io
import os
import sys
from types import SimpleNamespace
from unittest.mock import mock_open

from fastapi.testclient import TestClient

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import app
from routers import concepts, transcript


client = TestClient(app)


def _gate_result(verdict="proceed", reason="looks good", detected_language="es"):
    return SimpleNamespace(
        verdict=verdict,
        reason=reason,
        detected_language=detected_language,
    )


class FakeFetchedTranscript:
    def __init__(self, segments):
        self._segments = segments

    def to_raw_data(self):
        return self._segments


class FakeCaptionTrack:
    def __init__(self, *, language_code, language, is_generated, segments):
        self.language_code = language_code
        self.language = language
        self.is_generated = is_generated
        self._segments = segments

    def fetch(self):
        return FakeFetchedTranscript(self._segments)


class FakeYouTubeTranscriptApi:
    def __init__(self, transcripts):
        self._transcripts = transcripts

    def list(self, video_id):
        assert video_id == "abc123"
        return self._transcripts


def test_transcript_youtube_unified_success(monkeypatch):
    monkeypatch.setattr(
        transcript,
        "YouTubeTranscriptApi",
        lambda: FakeYouTubeTranscriptApi(
            [
                FakeCaptionTrack(
                    language_code="es",
                    language="Spanish",
                    is_generated=False,
                    segments=[
                        {"text": "hola", "start": 0.0, "duration": 1.2},
                        {"text": "mundo", "start": 1.2, "duration": 1.0},
                    ],
                )
            ]
        ),
    )
    monkeypatch.setattr(transcript, "get_video_info", lambda url: {"title": "Breakfast Spanish", "duration": 42})
    monkeypatch.setattr(transcript, "extract_audio", lambda video_url, output_base: None)

    async def fake_gate_run(normalized, *, title, duration):
        assert len(normalized) == 2
        assert title == "Breakfast Spanish"
        assert duration == 42
        return _gate_result()

    monkeypatch.setattr(transcript.transcript_gate, "run", fake_gate_run)

    response = client.post("/transcript", json={"video_url": "https://www.youtube.com/watch?v=abc123"})

    assert response.status_code == 200
    assert response.json() == {
        "transcript": [
            {"text": "hola", "start": 0.0, "duration": 1.2},
            {"text": "mundo", "start": 1.2, "duration": 1.0},
        ],
        "audio_path": "/tmp/visualang_images/abc123.mp3",
        "title": "Breakfast Spanish",
        "gate": {
            "verdict": "proceed",
            "reason": "looks good",
            "detected_language": "es",
        },
    }


def test_transcript_upload_unified_success(monkeypatch):
    monkeypatch.setattr(
        transcript,
        "transcribe_audio",
        lambda audio_path: [
            {"text": "bonjour", "start": 0.0, "duration": 1.5},
            {"text": "tout le monde", "start": 1.5, "duration": 2.0},
        ],
    )

    async def fake_gate_run(normalized, *, title, duration):
        assert title == "lesson"
        assert duration == 3.5
        return _gate_result(verdict="warn", reason="low confidence opening segment", detected_language="fr")

    monkeypatch.setattr(transcript.transcript_gate, "run", fake_gate_run)

    response = client.post(
        "/transcript",
        files={"file": ("lesson.mp3", io.BytesIO(b"fake-audio"), "audio/mpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "lesson"
    assert body["transcript"] == [
        {"text": "bonjour", "start": 0.0, "duration": 1.5},
        {"text": "tout le monde", "start": 1.5, "duration": 2.0},
    ]
    assert body["gate"] == {
        "verdict": "warn",
        "reason": "low confidence opening segment",
        "detected_language": "fr",
    }
    assert body["audio_path"].endswith("_lesson.mp3")


def test_transcribe_audio_uses_whisper_verbose_json(monkeypatch):
    captured = {}

    class FakeTranscriptions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                segments=[
                    SimpleNamespace(text="hola", start=0.0, end=1.0),
                    SimpleNamespace(text="mundo", start=1.0, end=2.5),
                ]
            )

    class FakeAudio:
        def __init__(self):
            self.transcriptions = FakeTranscriptions()

    class FakeOpenAI:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.audio = FakeAudio()

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    monkeypatch.setattr("builtins.open", mock_open(read_data=b"audio-bytes"))

    normalized = transcript.transcribe_audio("/tmp/fake.mp3")

    assert captured["api_key"] == transcript.OPENAI_API_KEY
    assert captured["model"] == "whisper-1"
    assert captured["response_format"] == "verbose_json"
    assert captured["timestamp_granularities"] == ["segment"]
    assert normalized == [
        {"text": "hola", "start": 0.0, "duration": 1.0},
        {"text": "mundo", "start": 1.0, "duration": 1.5},
    ]


def test_transcript_invalid_youtube_url_returns_400():
    response = client.post("/transcript", json={"video_url": "https://example.com/not-youtube"})
    assert response.status_code == 400
    assert "Could not extract video ID" in response.json()["detail"]


def test_transcript_unsupported_file_type_returns_400():
    response = client.post(
        "/transcript",
        files={"file": ("notes.txt", io.BytesIO(b"not-audio"), "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type: .txt"


def test_transcript_upload_rejects_removed_legacy_file_types():
    response = client.post(
        "/transcript",
        files={"file": ("lesson.ogg", io.BytesIO(b"fake-audio"), "audio/ogg")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type: .ogg"


def test_transcript_upload_rejects_files_over_25_mb():
    response = client.post(
        "/transcript",
        files={"file": ("lesson.mp3", io.BytesIO(b"x" * (25 * 1024 * 1024 + 1)), "audio/mpeg")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "File exceeds 25 MB limit."


def test_transcript_gate_reject_returns_422(monkeypatch):
    monkeypatch.setattr(
        transcript,
        "YouTubeTranscriptApi",
        lambda: FakeYouTubeTranscriptApi(
            [
                FakeCaptionTrack(
                    language_code="es",
                    language="Spanish",
                    is_generated=False,
                    segments=[{"text": "hola", "start": 0.0, "duration": 1.0}],
                )
            ]
        ),
    )
    monkeypatch.setattr(transcript, "get_video_info", lambda url: {"title": "Rejected clip", "duration": 10})
    monkeypatch.setattr(transcript, "extract_audio", lambda video_url, output_base: None)

    async def fake_gate_run(normalized, *, title, duration):
        return _gate_result(verdict="reject", reason="too sparse", detected_language="unknown")

    monkeypatch.setattr(transcript.transcript_gate, "run", fake_gate_run)

    response = client.post("/transcript", json={"video_url": "https://youtu.be/abc123"})

    assert response.status_code == 422
    assert response.json()["detail"] == "Transcript rejected: too sparse"


def test_transcript_youtube_falls_back_to_generated_non_english_track(monkeypatch):
    monkeypatch.setattr(
        transcript,
        "YouTubeTranscriptApi",
        lambda: FakeYouTubeTranscriptApi(
            [
                FakeCaptionTrack(
                    language_code="es",
                    language="Spanish",
                    is_generated=True,
                    segments=[
                        {"text": "buenos dias", "start": 0.0, "duration": 1.5},
                        {"text": "amigos", "start": 1.5, "duration": 1.0},
                    ],
                )
            ]
        ),
    )
    monkeypatch.setattr(transcript, "get_video_info", lambda url: {"title": "Morning Spanish", "duration": 15})
    monkeypatch.setattr(transcript, "extract_audio", lambda video_url, output_base: None)

    async def fake_gate_run(normalized, *, title, duration):
        assert normalized[0]["text"] == "buenos dias"
        assert title == "Morning Spanish"
        assert duration == 15
        return _gate_result(verdict="proceed", reason="generated captions are usable", detected_language="es")

    monkeypatch.setattr(transcript.transcript_gate, "run", fake_gate_run)

    response = client.post("/transcript", json={"video_url": "https://www.youtube.com/watch?v=abc123"})

    assert response.status_code == 200
    assert response.json()["gate"] == {
        "verdict": "proceed",
        "reason": "generated captions are usable",
        "detected_language": "es",
    }
    assert response.json()["transcript"] == [
        {"text": "buenos dias", "start": 0.0, "duration": 1.5},
        {"text": "amigos", "start": 1.5, "duration": 1.0},
    ]


def test_concepts_parse_failure_returns_500(monkeypatch):
    async def fake_run(transcript_input):
        raise ValueError("malformed JSON from model")

    monkeypatch.setattr(concepts.concept_extractor, "run", fake_run)

    response = client.post(
        "/concepts",
        json={"transcript": [{"text": "hola", "start": 0.0, "duration": 1.0}]},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Concept extraction failed: malformed JSON from model"
