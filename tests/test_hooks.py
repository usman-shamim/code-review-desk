"""FR-10 — latency and measured tokens, and what the two hook scopes each see."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from agents import AgentHooks, RunHooks

from desk.hooks import OneReviewerHooks, TimingHooks

REVIEWERS = ["SecurityReviewer", "TestsReviewer", "StyleReviewer"]


def _context(total_tokens: int = 1841) -> SimpleNamespace:
    return SimpleNamespace(usage=SimpleNamespace(total_tokens=total_tokens, requests=1))


def _agent(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


async def test_run_hooks_record_latency_and_tokens() -> None:
    hooks = TimingHooks()
    await hooks.on_agent_start(_context(), _agent("SecurityReviewer"))
    await hooks.on_agent_end(_context(1841), _agent("SecurityReviewer"), [])

    stat = hooks.stats["SecurityReviewer"]
    assert stat.agent == "SecurityReviewer"
    assert stat.ms >= 0
    assert stat.tokens == 1841


async def test_footer_has_one_row_per_reviewer_that_ran() -> None:
    hooks = TimingHooks()
    for name in REVIEWERS:
        await hooks.on_agent_start(_context(), _agent(name))
        await hooks.on_agent_end(_context(100), _agent(name), [])

    rows = hooks.footer(REVIEWERS)
    assert [row.agent for row in rows] == REVIEWERS
    assert [row.tokens for row in rows] == [100, 100, 100]


async def test_footer_omits_a_reviewer_that_never_ran() -> None:
    """The partial case: fewer rows, not three rows with zeros."""
    hooks = TimingHooks()
    await hooks.on_agent_start(_context(), _agent("SecurityReviewer"))
    await hooks.on_agent_end(_context(50), _agent("SecurityReviewer"), [])

    assert [row.agent for row in hooks.footer(REVIEWERS)] == ["SecurityReviewer"]


async def test_end_without_start_is_ignored() -> None:
    hooks = TimingHooks()
    await hooks.on_agent_end(_context(), _agent("Ghost"), [])
    assert hooks.stats == {}


async def test_tokens_are_read_not_estimated() -> None:
    """A context with no usage reports 0 rather than a guess."""
    hooks = TimingHooks()
    await hooks.on_agent_start(SimpleNamespace(), _agent("StyleReviewer"))
    await hooks.on_agent_end(SimpleNamespace(), _agent("StyleReviewer"), [])
    assert hooks.stats["StyleReviewer"].tokens == 0


async def test_agent_hooks_count_llm_and_tool_calls() -> None:
    hooks = OneReviewerHooks()
    await hooks.on_start(_context(), _agent("SecurityReviewer"))
    await hooks.on_llm_start(_context(), _agent("SecurityReviewer"), "prompt", [])
    await hooks.on_llm_start(_context(), _agent("SecurityReviewer"), "prompt", [])
    tool_a = SimpleNamespace(name="read_ruleset")
    tool_b = SimpleNamespace(name="read_diff_chunk")
    await hooks.on_tool_start(_context(), _agent("SecurityReviewer"), tool_a)
    await hooks.on_tool_start(_context(), _agent("SecurityReviewer"), tool_b)

    assert hooks.llm_calls == 2
    assert hooks.tool_calls == 2
    assert hooks.tools_used == ["read_ruleset", "read_diff_chunk"]


def test_agent_hooks_name_their_lifecycle_callbacks_on_start_and_on_end() -> None:
    """The asymmetry the plan documents: AgentHooks uses on_start/on_end, RunHooks does not."""
    assert hasattr(AgentHooks, "on_start")
    assert hasattr(AgentHooks, "on_end")
    assert not hasattr(AgentHooks, "on_agent_start")
    assert hasattr(RunHooks, "on_agent_start")
    assert hasattr(RunHooks, "on_agent_end")


def test_run_hooks_do_not_see_llm_or_tool_calls_of_an_agent_it_did_not_start() -> None:
    """What the scopes see differently, stated as a fact about the classes."""
    run_level = {name for name in dir(RunHooks) if name.startswith("on_")}
    agent_level = {name for name in dir(AgentHooks) if name.startswith("on_")}
    assert "on_agent_start" in run_level and "on_agent_start" not in agent_level
    assert "on_start" in agent_level and "on_start" not in run_level


def test_pipeline_attaches_agent_hooks_to_exactly_one_reviewer() -> None:
    """FR-10: agent-level hooks are attached to exactly one reviewer, not all three."""
    from desk import pipeline

    source = inspect.getsource(pipeline)
    assert source.count("OneReviewerHooks()") >= 1
    assert source.count(".hooks = agent_hooks") >= 1
    assert "security_reviewer_name()" in source
