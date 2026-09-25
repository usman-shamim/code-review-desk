"""FR-12 — findings stream into the interface.

Session state holds the run context and the last report, so a second diff in the same session
reuses the context rather than rebuilding it. The handler awaits its run: the streaming
generator is consumed with `async for`, never a synchronous variant.
"""

from __future__ import annotations

import chainlit as cl

from desk import config, ledger
from desk.config import require_env
from desk.diff import split_diff
from desk.models import NO_REVIEWABLE_FILES, ReviewContext
from desk.pipeline import render_footer, stream_review

CONTEXT_KEY = "review_context"
LAST_REPORT_KEY = "last_report"


@cl.on_chat_start
async def on_chat_start() -> None:
    require_env(*config.REQUIRED_ENV)
    ledger.register(config.REPO_ROOT / ledger.LEDGER_FILENAME)
    await cl.Message(
        content=(
            "Paste a unified diff and I will review it with three reviewers at once.\n"
            "Findings appear as each reviewer finishes."
        )
    ).send()


def _context_for(pasted: str) -> ReviewContext:
    """Reuse the session's context if there is one; otherwise build it once (FR-12)."""
    existing = cl.user_session.get(CONTEXT_KEY)
    if existing is None:
        existing = ReviewContext(repo="local/pasted", language="python", ruleset_id="python-strict")
    return existing


@cl.on_message
async def on_message(message: cl.Message) -> None:
    chunks = split_diff(message.content)
    if not chunks:
        await cl.Message(content=NO_REVIEWABLE_FILES).send()
        return

    context = _context_for(message.content)
    # A second diff in the same session keeps the context and takes the new chunks.
    context.chunks = {chunk.path: chunk.text for chunk in chunks}
    cl.user_session.set(CONTEXT_KEY, context)

    await cl.Message(
        content=f"Reviewing {len(chunks)} file(s): {', '.join(chunk.path for chunk in chunks)}"
    ).send()

    diff_text = "\n".join(chunk.text for chunk in chunks)

    async for event in stream_review(context, diff_text):
        if event["event"] == "reviewer":
            findings = event["findings"]
            body = "\n".join(
                f"  {f.severity:<8} {f.file}:{f.line}  {f.message}" for f in findings
            )
            await cl.Message(
                content=f"**{event['agent']}** — {len(findings)} finding(s)\n{body}".rstrip()
            ).send()
        elif event["event"] == "reviewer_failed":
            await cl.Message(content=f"**{event['agent']}** stopped: {event['error']}").send()
        elif event["event"] == "report":
            report = event["report"]
            cl.user_session.set(LAST_REPORT_KEY, report)
            if report.refused:
                await cl.Message(content=f"**REFUSED** — {report.refusal_message}").send()
                continue
            summary = [
                f"**Report** — {len(report.findings)} finding(s), {report.criticals()} critical"
            ]
            if report.partial and report.refusal_message:
                summary.append(f"_{report.refusal_message}_")
            summary.append(render_footer(report.footer))
            await cl.Message(content="\n".join(summary)).send()
