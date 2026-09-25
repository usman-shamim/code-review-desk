"""FR-2 and FR-3 — the structures that cross a boundary.

ReviewContext travels in the run context and is read by tools; it never appears in prompt
text. Finding is the reviewer's structured output; a list of them is what a reviewer returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "major", "minor"]

SEVERITY_ORDER: dict[str, int] = {"critical": 0, "major": 1, "minor": 2}

NO_REVIEWABLE_FILES = "No reviewable files found in that diff."


@dataclass
class ReviewContext:
    """Per-run facts. Read through RunContextWrapper, never pasted into a prompt (FR-2)."""

    repo: str
    language: str
    ruleset_id: str
    strictness: str = "normal"
    # The split diff, keyed by path, so read_diff_chunk can serve it through the context
    # rather than through a module-level global (which would race under concurrency).
    chunks: dict[str, str] = field(default_factory=dict)

    @property
    def is_strict(self) -> bool:
        return self.strictness == "strict"

    def describe(self) -> str:
        """The only form of this context allowed anywhere near a model.

        Deliberately carries no repository name and no ruleset identifier.
        """
        return f"Reviewing {self.language} code at {self.strictness} strictness."


@dataclass
class DiffChunk:
    """One file's worth of the diff. Produced by the split, before any model call (FR-1)."""

    path: str
    text: str


class Finding(BaseModel):
    """One review observation. A reviewer's output_type is list[Finding] (FR-3)."""

    file: str = Field(description="Path of the file the finding refers to")
    line: int = Field(description="Line number within that file")
    severity: Severity = Field(description="One of: critical, major, minor")
    message: str = Field(
        description=(
            "What is wrong and why it matters. Describe any credential; never reproduce it."
        )
    )


class ReviewerStat(BaseModel):
    """One reviewer's measured cost, for the report footer (FR-10)."""

    agent: str
    ms: int
    tokens: int


class Report(BaseModel):
    """The artifact the output guardrail inspects (FR-8) and the interface displays (FR-12)."""

    findings: list[Finding] = Field(default_factory=list)
    footer: list[ReviewerStat] = Field(default_factory=list)
    partial: bool = False
    refused: bool = False
    refusal_message: str = ""

    def criticals(self) -> int:
        """FR-3's acceptance: criticals countable with one expression."""
        return sum(1 for finding in self.findings if finding.severity == "critical")


class MergeInput(BaseModel):
    """Structured input for the merge tool (FR-6).

    A nested `as_tool` run does not inherit the parent's state, so the findings are handed
    to the specialist explicitly rather than being read from shared context.
    """

    findings: list[Finding] = Field(default_factory=list)


class RemediationInput(BaseModel):
    """Typed handoff input, so the Desk must state which finding caused the transfer (FR-6)."""

    finding: Finding
    context_summary: str = ""


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Severity first, then file and line, so the order is deterministic (FR-6)."""
    return sorted(
        findings,
        key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.file, f.line),
    )


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    """Collapse findings on the same (file, line), keeping the highest severity (FR-6).

    Messages from the collapsed findings are merged so no reviewer's reasoning is lost.
    """
    grouped: dict[tuple[str, int], list[Finding]] = {}
    for finding in findings:
        grouped.setdefault((finding.file, finding.line), []).append(finding)

    merged: list[Finding] = []
    for group in grouped.values():
        best = min(group, key=lambda f: SEVERITY_ORDER.get(f.severity, 9))
        messages: list[str] = []
        for finding in group:
            if finding.message not in messages:
                messages.append(finding.message)
        merged.append(
            Finding(
                file=best.file,
                line=best.line,
                severity=best.severity,
                message=" ".join(messages),
            )
        )
    return sort_findings(merged)
