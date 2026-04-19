"""In-memory rolling metrics for the Visualang pipeline.

Not persistent — resets on uvicorn reload. Safe for hackathon demo only.
Thread-safe enough for FastAPI's single-process dev mode; swap for a real
metrics backend before anything prod-shaped.
"""

from __future__ import annotations

import threading
from collections import Counter, deque

from fastapi import APIRouter

router = APIRouter()

# Per-metric rolling window of recent samples (FIFO, capped).
_WINDOW_SIZE = 200
_samples: dict[str, deque] = {}
_counters: Counter = Counter()
_lock = threading.Lock()


def record(name: str, value: int | float) -> None:
    """Append a sample or increment a counter.

    Names ending in `_ms`, `_ms_total`, `_size` are treated as samples
    (we'll compute p50/p95). Others are counters incremented by value.
    """
    with _lock:
        if name.endswith(("_ms", "_size")):
            _samples.setdefault(name, deque(maxlen=_WINDOW_SIZE)).append(value)
        else:
            _counters[name] += int(value)


def _pct(sorted_samples: list, q: float) -> float | None:
    if not sorted_samples:
        return None
    k = max(0, min(len(sorted_samples) - 1, int(round(q * (len(sorted_samples) - 1)))))
    return sorted_samples[k]


@router.get("/metrics")
def read_metrics():
    with _lock:
        samples_snapshot = {k: list(v) for k, v in _samples.items()}
        counters_snapshot = dict(_counters)

    summaries: dict[str, dict] = {}
    for name, vals in samples_snapshot.items():
        if not vals:
            continue
        sorted_vals = sorted(vals)
        summaries[name] = {
            "count": len(sorted_vals),
            "p50": _pct(sorted_vals, 0.50),
            "p95": _pct(sorted_vals, 0.95),
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
        }

    return {
        "samples": summaries,
        "counters": counters_snapshot,
        "window_size": _WINDOW_SIZE,
    }


@router.post("/metrics/reset")
def reset_metrics():
    with _lock:
        _samples.clear()
        _counters.clear()
    return {"status": "reset"}
