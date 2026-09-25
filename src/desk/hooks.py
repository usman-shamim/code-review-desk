"""FR-10, NFR-3 — per-reviewer latency and measured tokens.

Two scopes, deliberately: RunHooks observe every agent in a run, AgentHooks observe the work
inside one agent. The token numbers come from the run context's usage, so they are measured
rather than estimated.
"""

from __future__ import annotations

import time
from typing import Any

from agents import AgentHooks, RunHooks

from .models import ReviewerStat


def _total_tokens(context: Any) -> int:
    usage = getattr(context, "usage", None)
    if usage is None:
        return 0
    return int(getattr(usage, "total_tokens", 0) or 0)


class TimingHooks(RunHooks):
    """Run-level. Sees every agent in the run, including the merge and any handoff."""

    def __init__(self) -> None:
        self.stats: dict[str, ReviewerStat] = {}
        self._started: dict[str, float] = {}

    async def on_agent_start(self, context: Any, agent: Any) -> None:
        self._started[agent.name] = time.perf_counter()

    async def on_agent_end(self, context: Any, agent: Any, output: Any) -> None:
        began = self._started.pop(agent.name, None)
        if began is None:
            return
        self.stats[agent.name] = ReviewerStat(
            agent=agent.name,
            ms=int((time.perf_counter() - began) * 1000),
            tokens=_total_tokens(context),
        )

    def footer(self, names: list[str]) -> list[ReviewerStat]:
        """One row per reviewer that actually ran, in the order given."""
        return [self.stats[name] for name in names if name in self.stats]


class OneReviewerHooks(AgentHooks):
    """Agent-level. Attached to exactly one reviewer.

    What these see that the run-level hooks do not: this one agent's individual LLM and tool
    calls, in sequence. RunHooks see agents as units; AgentHooks see the work inside one.

    Naming trap worth knowing: AgentHooks names its lifecycle callbacks `on_start`/`on_end`,
    while RunHooks names the equivalent pair `on_agent_start`/`on_agent_end`.
    """

    def __init__(self) -> None:
        self.llm_calls = 0
        self.tool_calls = 0
        self.tools_used: list[str] = []

    async def on_start(self, context: Any, agent: Any) -> None:
        self.llm_calls = 0
        self.tool_calls = 0
        self.tools_used = []

    async def on_llm_start(
        self, context: Any, agent: Any, system_prompt: Any, input_items: Any
    ) -> None:
        self.llm_calls += 1

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
        self.tool_calls += 1
        self.tools_used.append(getattr(tool, "name", "unknown"))
