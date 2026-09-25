"""Code Review Desk — a fan-out, fan-in diff review pipeline.

Requirement map (see specs/001-code-review-desk/plan.md):

    config       NFR-1        dotenv loading and fail-fast credential checks
    diff         FR-1         split a unified diff by file before any model call
    models       FR-2, FR-3   ReviewContext, DiffChunk, Finding, ReviewerStat, Report
    tools        FR-2, FR-6, FR-9   read_ruleset, read_diff_chunk, merge-as-tool
    agents       FR-1, FR-4, FR-5, FR-6   base reviewer, three clones, specialists
    guardrails   FR-8         output guardrail: refuse credential-shaped reports
    hooks        FR-10        per-reviewer latency and measured tokens
    ledger       FR-11        one line per run
    pipeline     FR-5, FR-6, FR-7, FR-9   gather, merge, hand off, assemble
    cli          FR-1, NFR-1  async entry point
"""

__version__ = "0.1.0"
