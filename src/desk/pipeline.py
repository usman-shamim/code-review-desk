"""FR-5, FR-6, FR-7, FR-8, FR-9 — orchestration.

The fan-out is programmatic on purpose. FR-5 grades the difference between concurrent and
sequential wall-clock time, and that difference is only demonstrable if this module controls
the scheduling rather than delegating it to a model.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from agents import (
    Agent,
    MaxTurnsExceeded,
    OutputGuardrailTripwireTriggered,
    RunConfig,
    RunErrorHandlerResult,
    Runner,
)

from . import agents, config, ledger
from .guardrails import REFUSAL_MESSAGE
from .hooks import OneReviewerHooks, TimingHooks
from .models import (
    Finding,
    Report,
    ReviewContext,
    ReviewerStat,
    dedupe_findings,
    sort_findings,
)

PARTIAL_MESSAGE = (
    "Review stopped at the {ceiling}-turn ceiling. Findings so far are shown as partial."
)
DEGRADED_MESSAGE = (
    "Review completed without the merge specialist: findings were reconciled deterministically."
)


@dataclass
class RunSignals:
    """Mutable per-review flags the error handlers and the pipeline share."""

    partial: bool = False
    ceiling: int = config.DEFAULT_MAX_TURNS


@dataclass
class ReviewOutcome:
    report: Report
    elapsed_ms: int
    parallel: bool
    reviewer_names: list[str] = field(default_factory=list)
    agent_hook_summary: str = ""


def build_run_config(cheap: bool = False, workflow: str = "code-review-desk") -> RunConfig:
    """FR-7's run-level override, plus the FR-13 tracing settings.

    `trace_include_sensitive_data=False` is load-bearing, not a preference: the SDK default is
    True, which records prompts and tool I/O — and the diff is both. Left at the default the
    trace would carry the very credential FR-8 exists to refuse (NFR-1, Principle III).
    """
    return RunConfig(
        model=config.cheap_model_name() if cheap else None,
        workflow_name=workflow,
        trace_include_sensitive_data=False,
    )


def _reviewer_error_handlers(signals: RunSignals) -> dict[str, Any]:
    def on_max_turns(data: Any) -> RunErrorHandlerResult[Any]:
        signals.partial = True
        # An empty list keeps the declared output type honest; the ceiling is reported by
        # the message on the report rather than by a string in a list[Finding] field.
        return RunErrorHandlerResult(final_output=[], include_in_history=False)

    return {"max_turns": on_max_turns}


def _desk_error_handlers(signals: RunSignals) -> dict[str, Any]:
    def on_max_turns(data: Any) -> RunErrorHandlerResult[Any]:
        signals.partial = True
        return RunErrorHandlerResult(
            final_output=Report(
                findings=[],
                partial=True,
                refusal_message=PARTIAL_MESSAGE.format(ceiling=signals.ceiling),
            ),
            include_in_history=False,
        )

    return {"max_turns": on_max_turns}


def review_prompt(context: ReviewContext, diff_text: str) -> str:
    """The diff is the input under review; the run context is not in here (FR-2)."""
    return (
        f"Review this unified diff.\n\n"
        f"```diff\n{diff_text}\n```\n"
    )


def _findings_from(result: Any) -> list[Finding]:
    output = getattr(result, "final_output", None)
    if not isinstance(output, list):
        return []
    return [item for item in output if isinstance(item, Finding)]


async def _run_reviewer(
    reviewer: Agent[ReviewContext],
    context: ReviewContext,
    prompt: str,
    hooks: TimingHooks,
    run_config: RunConfig,
    signals: RunSignals,
) -> Any:
    return await Runner.run(
        reviewer,
        prompt,
        context=context,
        max_turns=signals.ceiling,
        hooks=hooks,
        run_config=run_config,
        error_handlers=_reviewer_error_handlers(signals),
    )


async def review(
    context: ReviewContext,
    diff_text: str,
    *,
    cheap: bool = False,
    parallel: bool = True,
) -> ReviewOutcome:
    """One pass of the Desk over one diff."""
    ceiling = config.max_turns()
    signals = RunSignals(ceiling=ceiling)
    hooks = TimingHooks()
    run_config = build_run_config(cheap=cheap)
    prompt = review_prompt(context, diff_text)

    crew = agents.reviewers()
    names = [reviewer.name for reviewer in crew]

    # FR-10: agent-level hooks on exactly one reviewer, not on all three.
    agent_hooks = OneReviewerHooks()
    for reviewer in crew:
        if reviewer.name == agents.security_reviewer_name():
            reviewer.hooks = agent_hooks

    started = time.perf_counter()
    if parallel:
        # C2: return_exceptions=True. With the default False, one reviewer exhausting its
        # ceiling would abort the group and cancel the other two, discarding their work —
        # the outcome constitution Principle IV exists to prevent.
        results: list[Any] = await asyncio.gather(
            *(
                _run_reviewer(reviewer, context, prompt, hooks, run_config, signals)
                for reviewer in crew
            ),
            return_exceptions=True,
        )
    else:
        results = []
        for reviewer in crew:
            try:
                results.append(
                    await _run_reviewer(reviewer, context, prompt, hooks, run_config, signals)
                )
            except Exception as exc:  # noqa: BLE001 - a serial reviewer must not stop the rest
                results.append(exc)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    collected: list[Finding] = []
    for reviewer, result in zip(crew, results, strict=True):
        if isinstance(result, BaseException):
            if isinstance(result, MaxTurnsExceeded):
                signals.partial = True
            else:
                signals.partial = True
            continue
        findings = _findings_from(result)
        collected.extend(findings)
        # FR-11: supply the count the trace processor cannot know at span end.
        processor = ledger.current()
        if processor is not None:
            processor.note_findings(reviewer.name, len(findings))

    report = await _assemble(context, collected, hooks, run_config, signals, names)
    report.footer = hooks.footer(names)

    processor = ledger.current()
    if processor is not None:
        processor.flush()

    return ReviewOutcome(
        report=report,
        elapsed_ms=elapsed_ms,
        parallel=parallel,
        reviewer_names=names,
        agent_hook_summary=(
            f"{agent_hooks.llm_calls} LLM call(s), {agent_hooks.tool_calls} tool call(s), "
            f"tools: {', '.join(agent_hooks.tools_used) or 'none'}"
        ),
    )


async def _assemble(
    context: ReviewContext,
    collected: list[Finding],
    hooks: TimingHooks,
    run_config: RunConfig,
    signals: RunSignals,
    names: list[str],
) -> Report:
    """Run the Desk: merge as a tool, remediation as a handoff, guardrail on the report."""
    has_critical_security = any(
        finding.severity == "critical" for finding in collected
    )
    desk = agents.desk_agent(with_remediation=has_critical_security)

    payload = json.dumps([finding.model_dump() for finding in collected])
    handoff_hint = (
        "A critical security finding exists. Hand off to the remediation specialist."
        if has_critical_security
        else "No critical security finding exists. Do not hand off."
    )

    try:
        result = await Runner.run(
            desk,
            f"Findings from the three reviewers:\n{payload}\n\n{handoff_hint}",
            context=context,
            max_turns=signals.ceiling,
            hooks=hooks,
            run_config=run_config,
            error_handlers=_desk_error_handlers(signals),
        )
    except OutputGuardrailTripwireTriggered:
        # FR-8: caught, reported, no crash. The guardrail runs after the spend, so the
        # refusal prevents disclosure rather than cost.
        return Report(
            findings=[],
            partial=signals.partial,
            refused=True,
            refusal_message=REFUSAL_MESSAGE,
        )
    except MaxTurnsExceeded:
        signals.partial = True
        return _fallback_report(collected, signals, PARTIAL_MESSAGE.format(ceiling=signals.ceiling))
    except Exception:  # noqa: BLE001 - the review must still complete (NFR-4)
        return _fallback_report(collected, signals, DEGRADED_MESSAGE)

    output = getattr(result, "final_output", None)
    if isinstance(output, Report):
        output.partial = output.partial or signals.partial
        if not output.findings and collected:
            # The model returned nothing usable; the reviewers' work is not lost.
            output = output.model_copy(update={"findings": sort_findings(collected)})
        return output

    return _fallback_report(collected, signals, DEGRADED_MESSAGE)


def _fallback_report(collected: list[Finding], signals: RunSignals, message: str) -> Report:
    """Deterministic reconciliation, used when the merge specialist cannot run."""
    return Report(
        findings=dedupe_findings(collected),
        partial=True,
        refusal_message=message,
    )


def render_footer(rows: list[ReviewerStat]) -> str:
    if not rows:
        return "(no reviewer statistics recorded)"
    width = max(len(row.agent) for row in rows)
    lines = ["-" * 46]
    for row in rows:
        lines.append(f"{row.agent:<{width}}  {row.ms:>6} ms  {row.tokens:>7} tokens")
    return "\n".join(lines)


async def stream_review(
    context: ReviewContext,
    diff_text: str,
    *,
    cheap: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """Yield an event per reviewer as it finishes, then the final report.

    FR-12 needs findings visible before the review completes, so the interface consumes this
    rather than awaiting review() and rendering afterwards. The fan-out is identical to
    review(); only the joining strategy differs, which is why the interface does not have to
    reimplement it.
    """
    ceiling = config.max_turns()
    signals = RunSignals(ceiling=ceiling)
    hooks = TimingHooks()
    run_config = build_run_config(cheap=cheap)
    prompt = review_prompt(context, diff_text)

    crew = agents.reviewers()
    names = [reviewer.name for reviewer in crew]

    agent_hooks = OneReviewerHooks()
    for reviewer in crew:
        if reviewer.name == agents.security_reviewer_name():
            reviewer.hooks = agent_hooks

    pending: dict[asyncio.Task[Any], Agent[ReviewContext]] = {
        asyncio.ensure_future(
            _run_reviewer(reviewer, context, prompt, hooks, run_config, signals)
        ): reviewer
        for reviewer in crew
    }

    collected: list[Finding] = []
    while pending:
        finished, _ = await asyncio.wait(
            list(pending), return_when=asyncio.FIRST_COMPLETED
        )
        for task in finished:
            reviewer = pending.pop(task)
            error = task.exception()
            if error is not None:
                signals.partial = True
                yield {"event": "reviewer_failed", "agent": reviewer.name, "error": str(error)}
                continue
            findings = _findings_from(task.result())
            collected.extend(findings)
            processor = ledger.current()
            if processor is not None:
                processor.note_findings(reviewer.name, len(findings))
            yield {"event": "reviewer", "agent": reviewer.name, "findings": findings}

    report = await _assemble(context, collected, hooks, run_config, signals, names)
    report.footer = hooks.footer(names)

    processor = ledger.current()
    if processor is not None:
        processor.flush()

    yield {
        "event": "report",
        "report": report,
        "agent_hook_summary": agent_hooks,
    }
