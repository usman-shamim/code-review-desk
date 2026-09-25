"""FR-1, NFR-1 — the async entry point.

`require_env` is the first statement of main(), before argument parsing, so a missing key
produces one sentence and a non-zero exit rather than a traceback (NFR-1, SC-005).

Three flags do their work without a model call at all — --dry-run-split, --print-prompt and
--print-schema — which is what lets FR-1, FR-2, FR-3 and FR-4 be demonstrated on a machine
with no API key.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from agents import AgentOutputSchema, RunContextWrapper

from . import agents, config, ledger
from .config import require_env
from .diff import render_chunks, split_diff
from .models import NO_REVIEWABLE_FILES, Finding, ReviewContext
from .pipeline import ReviewOutcome, render_footer, review


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="desk-review",
        description="Review a unified diff. Spec: specs/001-code-review-desk/spec.md",
    )
    parser.add_argument("diff", type=Path, help="Path to a unified diff")
    parser.add_argument("--repo", default="local/unknown", help="Repository name (FR-2)")
    parser.add_argument("--language", default="python", help="Language under review (FR-2)")
    parser.add_argument("--ruleset", default="python-strict", help="Ruleset id (FR-2, FR-9)")
    parser.add_argument(
        "--strictness", choices=("normal", "strict"), default="normal", help="Prompt terseness"
    )
    parser.add_argument(
        "--timing",
        choices=("concurrent", "sequential", "both"),
        default="concurrent",
        help="Run the reviewers at once (FR-5), one after another, or both for comparison",
    )
    parser.add_argument("--cheap", action="store_true", help="Run-level model override (FR-7)")
    parser.add_argument("--dry-run-split", action="store_true", help="Split only, no model call")
    parser.add_argument("--print-prompt", action="store_true", help="Print resolved prompt")
    parser.add_argument("--print-schema", action="store_true", help="Print the output schema")
    parser.add_argument("--count-criticals", action="store_true", help="Count criticals only")
    parser.add_argument("--show-footer", action="store_true", help="Show per-reviewer cost")
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON")
    return parser


def _resolved_prompt(context: ReviewContext) -> str:
    """FR-4: resolve the same callable the SDK would, and print it before any model call."""
    reviewer = agents.base_reviewer()
    wrapper = RunContextWrapper(context=context)
    return reviewer.instructions(wrapper, reviewer)


def _output_schema() -> str:
    """FR-3: the generated schema, so the list-root wrapper can be pointed at."""
    schema = AgentOutputSchema(list[Finding]).json_schema()
    return json.dumps(schema, indent=2)


def _render(outcome: ReviewOutcome, show_footer: bool, as_json: bool) -> str:
    report = outcome.report
    if as_json:
        return json.dumps(report.model_dump(), indent=2)

    lines: list[str] = []
    if report.refused:
        lines.append(f"REFUSED — {report.refusal_message}")
    else:
        criticals = report.criticals()
        lines.append(
            f"{len(report.findings)} finding(s) — {criticals} critical"
        )
        for finding in report.findings:
            lines.append(
                f"  {finding.severity:<8} {finding.file}:{finding.line}  {finding.message}"
            )

    if report.partial and report.refusal_message and not report.refused:
        lines.append(f"PARTIAL — {report.refusal_message}")

    if show_footer:
        lines.append(render_footer(report.footer))
        lines.append(f"reviewer hooks — {outcome.agent_hook_summary}")

    lines.append(
        f"({('concurrent' if outcome.parallel else 'sequential')} wall clock: "
        f"{outcome.elapsed_ms} ms)"
    )
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> int:
    try:
        raw = args.diff.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Could not read that diff: {exc.strerror or exc}.", file=sys.stderr)
        return 2

    chunks = split_diff(raw)
    if not chunks:
        print(NO_REVIEWABLE_FILES, file=sys.stderr)
        return 2

    context = ReviewContext(
        repo=args.repo,
        language=args.language,
        ruleset_id=args.ruleset,
        strictness=args.strictness,
        chunks={chunk.path: chunk.text for chunk in chunks},
    )

    if args.dry_run_split:
        print(render_chunks(chunks))
        return 0

    if args.print_prompt:
        print(_resolved_prompt(context))
        return 0

    if args.print_schema:
        print(_output_schema())
        return 0

    # FR-11: registered exactly once, here, and nowhere near an agent definition.
    ledger.register(config.REPO_ROOT / ledger.LEDGER_FILENAME)

    diff_text = "\n".join(chunk.text for chunk in chunks)

    if args.timing == "both":
        concurrent = await review(context, diff_text, cheap=args.cheap, parallel=True)
        sequential = await review(context, diff_text, cheap=args.cheap, parallel=False)
        print(_render(concurrent, args.show_footer, args.json))
        print()
        print(f"concurrent: {concurrent.elapsed_ms} ms   sequential: {sequential.elapsed_ms} ms")
        if concurrent.elapsed_ms:
            ratio = sequential.elapsed_ms / concurrent.elapsed_ms
            print(f"speed-up: {ratio:.2f}x  (SC-002 wants concurrent within 1.5x the slowest)")
        return 0 if not concurrent.report.refused else 1

    outcome = await review(
        context, diff_text, cheap=args.cheap, parallel=args.timing == "concurrent"
    )
    print(_render(outcome, args.show_footer, args.json))

    if args.count_criticals:
        print(f"criticals: {outcome.report.criticals()}")
    return 1 if outcome.report.refused else 0


def main() -> None:
    args = build_parser().parse_args()
    # NFR-1: no model call happens without a key, and the failure is one sentence rather than
    # a traceback. The three introspection flags touch no client, so they deliberately run
    # without one — which keeps FR-1 to FR-4 demonstrable offline.
    if not (args.dry_run_split or args.print_prompt or args.print_schema):
        require_env(*config.REQUIRED_ENV)
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
