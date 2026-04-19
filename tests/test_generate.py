import asyncio
import base64
import os
import sys
from types import SimpleNamespace

import pytest
import requests

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from routers import generate


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = str(self._payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Client Error")

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def reset_generate_state(monkeypatch):
    monkeypatch.setattr(generate, "_NEXT_NUNCHAKU_ATTEMPT_AT", 0.0)
    monkeypatch.setattr(generate, "NUNCHAKU_MIN_INTERVAL_SECONDS", 2.0)
    monkeypatch.setattr(generate, "NUNCHAKU_MAX_429_RETRIES", 4)
    monkeypatch.setattr(generate, "NUNCHAKU_BACKOFF_BASE_SECONDS", 3.0)
    monkeypatch.setattr(generate, "NUNCHAKU_ENABLE_REWRITE_RECOVERY", False)


def test_call_nunchaku_success_first_attempt():
    calls = []

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse(200, {"data": [{"b64_json": "abc123"}]})

    result = generate._call_nunchaku("prompt", "model", "tier", post_fn=fake_post)

    assert result == "abc123"
    assert len(calls) == 1


def test_call_nunchaku_retries_429_using_retry_after(monkeypatch):
    responses = [
        FakeResponse(429, headers={"Retry-After": "5"}),
        FakeResponse(200, {"data": [{"b64_json": "ok"}]}),
    ]
    sleeps = []
    current_time = [0.0]

    def fake_sleep(seconds):
        sleeps.append(seconds)
        current_time[0] += seconds

    def fake_now():
        return current_time[0]

    def fake_post(*args, **kwargs):
        return responses.pop(0)

    result = generate._call_nunchaku(
        "prompt",
        "model",
        "tier",
        post_fn=fake_post,
        sleep_fn=fake_sleep,
        now_fn=fake_now,
    )

    assert result == "ok"
    assert sleeps == [5.0]


def test_call_nunchaku_retries_429_using_backoff_when_retry_after_missing():
    responses = [
        FakeResponse(429),
        FakeResponse(200, {"data": [{"b64_json": "ok"}]}),
    ]
    sleeps = []
    current_time = [0.0]

    def fake_sleep(seconds):
        sleeps.append(seconds)
        current_time[0] += seconds

    def fake_now():
        return current_time[0]

    def fake_post(*args, **kwargs):
        return responses.pop(0)

    result = generate._call_nunchaku(
        "prompt",
        "model",
        "tier",
        post_fn=fake_post,
        sleep_fn=fake_sleep,
        now_fn=fake_now,
    )

    assert result == "ok"
    assert sleeps == [3.0]


def test_call_nunchaku_exhausts_429_retry_budget():
    responses = [
        FakeResponse(429),
        FakeResponse(429),
        FakeResponse(429),
    ]
    sleeps = []
    current_time = [0.0]

    def fake_sleep(seconds):
        sleeps.append(seconds)
        current_time[0] += seconds

    def fake_now():
        return current_time[0]

    def fake_post(*args, **kwargs):
        return responses.pop(0)

    generate.NUNCHAKU_MAX_429_RETRIES = 2
    with pytest.raises(requests.HTTPError):
        generate._call_nunchaku(
            "prompt",
            "model",
            "tier",
            post_fn=fake_post,
            sleep_fn=fake_sleep,
            now_fn=fake_now,
        )

    assert sleeps == [3.0, 6.0]


def test_call_nunchaku_enforces_spacing_between_calls():
    responses = [
        FakeResponse(200, {"data": [{"b64_json": "one"}]}),
        FakeResponse(200, {"data": [{"b64_json": "two"}]}),
    ]
    sleeps = []
    current_time = [0.0]

    def fake_sleep(seconds):
        sleeps.append(seconds)
        current_time[0] += seconds

    def fake_now():
        return current_time[0]

    def fake_post(*args, **kwargs):
        return responses.pop(0)

    assert generate._call_nunchaku(
        "prompt-1",
        "model",
        "tier",
        post_fn=fake_post,
        sleep_fn=fake_sleep,
        now_fn=fake_now,
    ) == "one"
    assert generate._call_nunchaku(
        "prompt-2",
        "model",
        "tier",
        post_fn=fake_post,
        sleep_fn=fake_sleep,
        now_fn=fake_now,
    ) == "two"

    assert sleeps == [2.0]


def test_generate_with_recovery_skips_rewrite_when_disabled(monkeypatch):
    prompts = []
    encoded = base64.b64encode(b"image").decode("ascii")

    def fake_call_nunchaku(prompt, model, tier, **kwargs):
        prompts.append(prompt)
        return encoded

    def fake_save_b64(b64_data):
        assert b64_data == encoded
        return "/tmp/fake-image.jpg"

    async def fail_analyze(**kwargs):
        raise AssertionError("vision analysis should be skipped when rewrite recovery is disabled")

    monkeypatch.setattr(generate, "_call_nunchaku", fake_call_nunchaku)
    monkeypatch.setattr(generate, "_save_b64", fake_save_b64)
    monkeypatch.setattr(generate, "analyze_image_handler", fail_analyze)

    result = asyncio.run(
        generate._generate_with_recovery({"concept": "tea", "image_prompt": "original prompt"})
    )

    assert prompts == ["original prompt"]
    assert result == {"filepath": "/tmp/fake-image.jpg", "b64": encoded, "prompt_used": "original prompt"}


def test_generate_with_recovery_uses_rewritten_prompt_when_enabled(monkeypatch):
    prompts = []

    def fake_call_nunchaku(prompt, model, tier, **kwargs):
        prompts.append(prompt)
        encoded = base64.b64encode(prompt.encode("utf-8")).decode("ascii")
        return encoded

    def fake_save_b64(_b64_data):
        return "/tmp/fake-image.jpg"

    async def fake_analyze(**kwargs):
        return {"has_text": True, "details": "letters on mug"}

    async def fake_rewrite_run(**kwargs):
        assert kwargs["original_prompt"] == "original prompt"
        return SimpleNamespace(revised_prompt="rewritten prompt", reasoning="remove text")

    monkeypatch.setattr(generate, "NUNCHAKU_ENABLE_REWRITE_RECOVERY", True)
    monkeypatch.setattr(generate, "_call_nunchaku", fake_call_nunchaku)
    monkeypatch.setattr(generate, "_save_b64", fake_save_b64)
    monkeypatch.setattr(generate, "analyze_image_handler", fake_analyze)
    monkeypatch.setattr(generate.image_rewriter, "run", fake_rewrite_run)

    result = asyncio.run(
        generate._generate_with_recovery({"concept": "tea", "image_prompt": "original prompt"})
    )

    assert prompts == ["original prompt", "rewritten prompt"]
    assert result["filepath"] == "/tmp/fake-image.jpg"
    assert result["prompt_used"] == "rewritten prompt"
