"""Minimal async state-machine runner.

A graph is a dict mapping node names to async callables. Each node receives a
mutable state dict and returns the name of the next node (or "END" to stop).
No framework — 40 lines of Python.

Usage:
    async def extract(state): ...; return "critique"
    async def critique(state): ...; return "fix" if state["issues"] else "END"
    async def fix(state): ...; return "END"

    graph = Graph({"extract": extract, "critique": critique, "fix": fix})
    final_state = await graph.run(initial_state={"transcript": ...}, start="extract")
"""

from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

END = "END"
NodeFn = Callable[[dict[str, Any]], Awaitable[str]]


class Graph:
    def __init__(self, nodes: dict[str, NodeFn], *, name: str = "graph", max_steps: int = 20):
        self.nodes = nodes
        self.name = name
        self.max_steps = max_steps

    async def run(self, initial_state: dict[str, Any], start: str) -> dict[str, Any]:
        state = dict(initial_state)
        current = start
        steps = 0
        t0 = time.monotonic()

        while current != END:
            if steps >= self.max_steps:
                raise RuntimeError(f"{self.name}: exceeded max_steps={self.max_steps}")
            if current not in self.nodes:
                raise KeyError(f"{self.name}: unknown node '{current}'")

            node_name = current
            node_start = time.monotonic()
            logger.info("[%s] -> %s", self.name, node_name)
            current = await self.nodes[node_name](state)
            logger.info(
                "[%s]    %s done in %dms",
                self.name,
                node_name,
                int((time.monotonic() - node_start) * 1000),
            )
            steps += 1

        logger.info("[%s] END (%d steps, %dms total)", self.name, steps, int((time.monotonic() - t0) * 1000))
        return state
