import os
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import app
from routers import export


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_export_state():
    export.jobs.clear()
    yield
    export.jobs.clear()


def _write_image(name: str) -> Path:
    path = export.IMAGE_DIR / name
    path.write_bytes(b"fake-image")
    return path


def _cleanup_paths(*paths: Path):
    for path in paths:
        path.unlink(missing_ok=True)


def test_get_ken_burns_variant_wraps_deterministically():
    first = export.get_ken_burns_variant(0)
    wrapped = export.get_ken_burns_variant(len(export.KEN_BURNS_VARIANTS))

    assert first["name"] == "ken-burns-zoom-in-left"
    assert wrapped == first


def test_build_transition_plan_uses_expected_xfade_offsets():
    transitions = export.build_transition_plan([3.0, 4.0, 5.0], fade_duration=0.8)

    assert transitions == [
        {"index": 1, "type": "xfade", "duration": 0.8, "offset": 2.2},
        {"index": 2, "type": "xfade", "duration": 0.8, "offset": 5.4},
    ]


def test_build_transition_plan_falls_back_to_concat_for_short_scenes():
    transitions = export.build_transition_plan([0.6, 4.0, 0.7], fade_duration=0.8)

    assert transitions == [
        {"index": 1, "type": "concat", "duration": 0.0, "offset": 0.6},
        {"index": 2, "type": "concat", "duration": 0.0, "offset": 4.6},
    ]


def test_build_ffmpeg_args_contains_non_empty_filter_graph(tmp_path):
    image_one = _write_image("ffmpeg-one.jpg")
    image_two = _write_image("ffmpeg-two.jpg")
    try:
        images = [
            {"image_url": "/images/ffmpeg-one.jpg", "duration_seconds": 3.0},
            {"image_url": "/images/ffmpeg-two.jpg", "duration_seconds": 4.0},
        ]

        args = export.build_ffmpeg_args(
            "/tmp/fake-audio.mp3",
            images,
            str(tmp_path / "out.mp4"),
        )

        filter_graph = args[args.index("-filter_complex") + 1]
        assert filter_graph
        assert "zoompan" in filter_graph
        assert "xfade=transition=fade" in filter_graph
        assert args[args.index("-map") + 1] == "[video]"
    finally:
        _cleanup_paths(image_one, image_two)


def test_start_export_route_accepts_multiple_images_and_writes_zip(monkeypatch):
    image_one = _write_image("route-one.jpg")
    image_two = _write_image("route-two.jpg")
    captured = {}
    job_id = None

    async def fake_run_ffmpeg_export(job_id, audio_path, images, output_path):
        captured["job_id"] = job_id
        captured["audio_path"] = audio_path
        captured["images"] = images
        captured["output_path"] = output_path
        export.jobs[job_id]["status"] = "done"
        export.jobs[job_id]["video_path"] = output_path

    monkeypatch.setattr(export, "run_ffmpeg_export", fake_run_ffmpeg_export)

    response = client.post(
        "/export",
        json={
            "audio_path": "/tmp/test-audio.mp3",
            "images": [
                {
                    "timestamp_seconds": 0,
                    "image_url": "/images/route-one.jpg",
                    "duration_seconds": 3.0,
                    "concept": "scene one",
                },
                {
                    "timestamp_seconds": 3,
                    "image_url": "/images/route-two.jpg",
                    "duration_seconds": 4.0,
                    "concept": "scene two",
                },
            ],
            "transcript": [{"start": 0, "text": "hola"}],
        },
    )

    try:
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        assert captured["job_id"] == job_id
        assert len(captured["images"]) == 2

        zip_path = Path(export.jobs[job_id]["zip_path"])
        transcript_path = Path(export.jobs[job_id]["transcript_path"])
        assert zip_path.exists()
        assert transcript_path.exists()

        with zipfile.ZipFile(zip_path, "r") as zf:
            assert sorted(zf.namelist()) == [
                "00_0s_scene_one.jpg",
                "01_3s_scene_two.jpg",
            ]
        assert transcript_path.read_text() == "[00:00] hola"
    finally:
        cleanup_targets = [image_one, image_two]
        if job_id and job_id in export.jobs:
            cleanup_targets.extend(
                [
                    Path(export.jobs[job_id]["zip_path"]),
                    Path(export.jobs[job_id]["transcript_path"]),
                ]
            )
        _cleanup_paths(*cleanup_targets)
