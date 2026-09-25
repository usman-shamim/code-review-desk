"""FR-2, FR-6, FR-9 — the tools a reviewer can call.

``ctx`` is declared first on both tools. The SDK injects the run context and excludes it
from the generated schema, which is FR-2's mechanism: the ruleset identifier is readable
by the tool and absent from everything the model is shown.
"""

from __future__ import annotations

from typing import Annotated, Any

from agents import RunContextWrapper, function_tool

from .config import rulesets_dir
from .models import ReviewContext

MISSING_RULESET = "No ruleset is available for this identifier. Review without it and say so."
UNREADABLE_CHUNK = (
    "That file could not be read from the diff. Try another path, or continue without it."
)


@function_tool
def read_ruleset(
    ctx: RunContextWrapper[ReviewContext],
    ruleset_id: Annotated[str, "Identifier of the ruleset to read"],
) -> str:
    """Read the repository rules that apply to this review."""
    identifier = ruleset_id or ctx.context.ruleset_id
    try:
        return (rulesets_dir() / f"{identifier}.md").read_text(encoding="utf-8")
    except OSError:
        # FR-9 and NFR-4: a sentence the model can act on, never a raise into the runner.
        return MISSING_RULESET


def chunk_error_handler(ctx: RunContextWrapper[ReviewContext], error: Exception) -> str:
    """Satisfies FR-9's dedicated error handler. The exception never reaches the runner."""
    return UNREADABLE_CHUNK


@function_tool(failure_error_function=chunk_error_handler)
def read_diff_chunk(
    ctx: RunContextWrapper[ReviewContext],
    path: Annotated[str, "Path of the file within the diff to read"],
) -> str:
    """Read one file's chunk of the diff."""
    try:
        return ctx.context.chunks[path]
    except KeyError:
        # Deliberately raised: the SDK routes it to failure_error_function above, which
        # returns a sentence. This exercises FR-9's second control rather than pretending
        # bad input cannot happen.
        raise ValueError(f"no such path in this diff: {path}") from None


def reviewer_tools() -> list[Any]:
    """The tool set shared by the base reviewer and, through clone(), by all three."""
    return [read_ruleset, read_diff_chunk]
