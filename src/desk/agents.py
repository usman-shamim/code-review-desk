"""FR-1, FR-4, FR-5, FR-6, FR-8 — the reviewers, the specialists and the Desk.

Every agent declares its own model and its own model settings. Nothing here inherits an SDK
default (NFR-2, constitution Principle II), and the only run-level override in the project is
applied by the pipeline through RunConfig (FR-7) — never here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agents import Agent, ModelSettings, RunContextWrapper, handoff

from . import config
from .guardrails import no_credentials
from .models import Finding, MergeInput, RemediationInput, Report, ReviewContext
from .tools import reviewer_tools

REVIEWER_ROLES: tuple[tuple[str, str], ...] = (
    ("SecurityReviewer", "credential handling, injection paths and unsafe input"),
    ("TestsReviewer", "untested paths and assertions that cannot fail"),
    ("StyleReviewer", "readability and consistency"),
)

# FR-9's first control. "required" forces a tool call on the turn it applies to, and the
# reviewer's instructions name read_ruleset as the tool to call. Naming the tool outright
# would be stronger, but ModelSettings rejects a tool-choice object and a bare tool-name
# string is not a documented Responses value — so "required" is the strongest form that is
# certain to be accepted. The caveat is recorded in REPORT.md rather than glossed over.
FORCED_TOOL_CALL = "required"


def _instructions_for(role: str, focus: str) -> Callable[..., str]:
    """FR-4: instructions assembled at request time from the ruleset and the language.

    Returns a callable, not a string, so the prompt is resolved per run and becomes terser
    under strictness=strict. The repository name is deliberately never included: FR-2 requires
    it to reach tools through the run context and nothing else.
    """

    def build(ctx: RunContextWrapper[ReviewContext], agent: Agent[ReviewContext]) -> str:
        context = ctx.context
        lines = [
            f"You are the {role} on a code review desk.",
            f"You are reviewing {context.language} code at {context.strictness} strictness.",
            f"Your focus is {focus}.",
            "",
            "Call read_ruleset before producing any finding, and call read_diff_chunk when you",
            "need a file's text. Then return your findings as a list.",
            "",
            "Each finding needs a file, a line, a severity (critical, major or minor) and a",
            "message that says what is wrong and why it matters.",
            "Describe any credential you find. Never reproduce it in a message — the report is",
            "refused if a credential appears in it.",
        ]
        if context.is_strict:
            # FR-4: strict mode is TERSER, so it drops guidance rather than adding it.
            lines += ["", "Strict mode: only defects with a line number, nothing else."]
        else:
            lines += [
                "",
                "Normal mode: report defects, and notable readability problems too.",
                "Explain each finding fully rather than briefly, and cite the smallest useful",
                "range so the operator can locate it.",
                "If something is only a style preference, say so explicitly rather than implying",
                "a defect.",
            ]
        return "\n".join(lines)

    return build


def base_reviewer() -> Agent[ReviewContext]:
    """The shared base. Never run directly — the three reviewers are clones of it (FR-5)."""
    return Agent[ReviewContext](
        name="BaseReviewer",
        instructions=_instructions_for("reviewer", "the change as a whole"),
        model=config.model_name(),
        model_settings=ModelSettings(temperature=0.0),
        tools=reviewer_tools(),
        output_type=list[Finding],
    )


def reviewers() -> list[Agent[ReviewContext]]:
    """FR-5: three clones of one base, differing in instructions and model settings only."""
    base = base_reviewer()
    clones: list[Agent[ReviewContext]] = []

    for name, focus in REVIEWER_ROLES:
        settings = ModelSettings(temperature=0.0)
        if name == "SecurityReviewer":
            # FR-9, first control: no choice but to read the ruleset on the first turn.
            settings = ModelSettings(temperature=0.0, tool_choice=FORCED_TOOL_CALL)
        elif name == "StyleReviewer":
            settings = ModelSettings(temperature=0.2)
        clones.append(
            base.clone(
                name=name,
                instructions=_instructions_for(name, focus),
                model_settings=settings,
            )
        )
    return clones


def security_reviewer_name() -> str:
    return REVIEWER_ROLES[0][0]


# --------------------------------------------------------------------------------------
# Specialists
# --------------------------------------------------------------------------------------

MERGE_INSTRUCTIONS = """You reconcile findings from three reviewers.

You receive JSON with a "findings" list. Two findings that share a file and a line are the same
problem seen by different reviewers: collapse them into one, keeping the highest severity and
keeping every distinct explanation in the message.

Return the reconciled list, ordered most severe first: critical, then major, then minor."""

REMEDIATION_INSTRUCTIONS = """You propose a fix for a critical security finding.

You have been handed a review because a critical security finding exists. State plainly which
finding brought you here, then propose the smallest patch that removes the risk. Show the change
as a diff. Do not apply it — the operator applies it.

Never reproduce a credential. Refer to it by position, never by value."""

REPORT_INSTRUCTIONS = """You assemble the final review report.

You receive the reconciled findings as JSON. Produce the report exactly as given: do not add
findings, do not drop findings, do not reword messages. Preserve the order.

Set partial to false. Set refused to false and refusal_message to an empty string."""


def merge_specialist() -> Agent[ReviewContext]:
    return Agent[ReviewContext](
        name="MergeSpecialist",
        instructions=MERGE_INSTRUCTIONS,
        model=config.model_name(),
        model_settings=ModelSettings(temperature=0.0),
        output_type=list[Finding],
    )


def merge_tool() -> Any:
    """FR-6: the Merge specialist exposed as a tool, so the Desk keeps the conversation."""
    return merge_specialist().as_tool(
        tool_name="merge_findings",
        tool_description="Deduplicate overlapping findings and order them by severity.",
        parameters=MergeInput,
    )


def remediation_specialist() -> Agent[ReviewContext]:
    return Agent[ReviewContext](
        name="RemediationSpecialist",
        instructions=REMEDIATION_INSTRUCTIONS,
        model=config.model_name(),
        model_settings=ModelSettings(temperature=0.0),
    )


def remediation_handoff() -> Any:
    """FR-6: remediation reached by handoff, with a typed input naming the finding."""
    return handoff(
        remediation_specialist(),
        input_type=RemediationInput,
        on_handoff=_on_remediation_handoff,
    )


async def _on_remediation_handoff(ctx: RunContextWrapper[ReviewContext], input_data: Any) -> None:
    """Records the transfer. Deliberately silent about the credential in the finding."""
    return None


def desk_agent(with_remediation: bool) -> Agent[ReviewContext]:
    """The Desk itself: calls Merge as a tool, optionally hands off to Remediation.

    The handoff is attached only when a critical security finding exists, which is what makes
    FR-6's trigger deterministic rather than a matter of the model's judgement.

    The Desk is the last agent to run and therefore the one that carries the output guardrail:
    a Report assembled in Python would never be seen by one (FR-8).
    """
    return Agent[ReviewContext](
        name="Desk",
        instructions=(
            "You assemble a code review from findings produced by three reviewers.\n"
            "Call merge_findings once, with the findings you were given, then produce the "
            "report from the result.\n"
            "Preserve every finding the merge returns. Do not invent findings."
        ),
        model=config.model_name(),
        model_settings=ModelSettings(temperature=0.0),
        tools=[merge_tool()],
        handoffs=[remediation_handoff()] if with_remediation else [],
        output_type=Report,
        output_guardrails=[no_credentials],
    )
