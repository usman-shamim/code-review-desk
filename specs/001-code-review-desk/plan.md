# Implementation Plan: Code Review Desk

**Branch**: `001-code-review-desk` | **Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-code-review-desk/spec.md`

## Summary

Build a fan-out, fan-in review pipeline on the **OpenAI Agents SDK**. A unified diff is split by
file before any model call; three reviewers derived from one base definition run **concurrently**
over the same chunks under a shared `ReviewContext`; a Merge specialist is exposed as a tool and a
Remediation specialist as a handoff; an output guardrail refuses any report containing
credential-shaped text; run-level hooks measure latency and tokens; a custom trace processor
appends one ledger line per run; a Chainlit page streams findings as they land; and the whole
review is one trace exported under the project's own key.

Model configuration is the deliberate contrast the brief asks for: reviewers carry `gpt-5-nano`
**on the agent itself** (FR-1), and the cheaper re-run is applied **at the run level** with
`RunConfig(model=...)`, touching no agent definition (FR-7).

## Technical Context

**Language/Version**: Python 3.11+ (targets the `openai-agents` SDK's async surface)
**Primary Dependencies**: `openai-agents` (OpenAI Agents SDK), `pydantic`, `python-dotenv`,
`chainlit`; `pytest` for tests; `uv` for environment and dependency management
**Storage**: Files only. `.env` (gitignored) for credentials; `ledger.jsonl` (gitignored) for run
metadata; `rulesets/*.md` on disk for the rules a reviewer must consult. No database, and no
review content is persisted.
**Testing**: `pytest`, run via `uv run pytest`
**Target Platform**: Local developer machine, Linux. No server deployment.
**Project Type**: Single project — one Python package plus one Chainlit page
**Performance Goals**: Three concurrent reviews complete in wall-clock time close to the slowest
single review, and demonstrably not the sum of the three (FR-5, SC-002)
**Constraints**: Bounded generation everywhere — every agent declares its own model settings and
every review runs under a turn ceiling (NFR-2, FR-9). Credentials only in `.env` (NFR-1). No
global default client is ever set (FR-1). The reviewed code is never executed (spec non-goal 2).
**Scale/Scope**: One operator, one diff per review, three reviewers, two specialists; 13
functional requirements across three phases.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Gate for this plan | Status |
|---|-----------|--------------------|--------|
| I | Specification Before Implementation | The four Phase 0 artifacts are committed before `src/desk/` is created; the Phase 0 commit contains no source file | **PASS** — this plan is committed before any implementation task starts |
| II | Model Configured On The Agent | Every agent sets `model=` and `model_settings=` explicitly; `RunConfig(model=...)` appears only on the FR-7 override path | **PASS** — `agents.py` declares `gpt-5-nano` on the base reviewer; no agent inherits a default |
| III | Secrets Stay In `.env` | `config.require_env("OPENAI_API_KEY")` is the first statement of the entry point; the guardrail scans every outbound report; the ledger writer never receives diff or finding text | **PASS** — see `config.py` and `guardrails.py` below |
| IV | Tools Return Sentences, Never Raise | Every diff-reading tool sets `failure_error_function`; the ruleset tool is forced via `tool_choice`; `max_turns` is set and `MaxTurnsExceeded` is caught | **PASS** — see the tool contracts table |
| V | A Review Is Reproducible From The Diff | `ReviewContext` travels in the run context and is read through `RunContextWrapper`; instructions are callables resolved per run; no repository string appears in prompt text | **PASS** — FR-2's schema-exclusion mechanism and FR-4's callable instructions |
| VI | Concurrency And Guardrails Are Load-Bearing | `asyncio.gather` over cloned reviewers; `@output_guardrail` on the report path with the tripwire caught | **PASS** — neither has a fallback path in this plan |

No violations, so no principle was relaxed to fit the clock.

## Agent and Concurrency Design

| Agent | Role | Model configuration | How it is reached |
|-------|------|--------------------|-------------------|
| **Base reviewer** | Template carrying shared instructions, tools and settings. Never run directly. | `gpt-5-nano` at agent level | `clone()` produces the three reviewers |
| **Security reviewer** | Finds credential handling, injection and unsafe-input defects | Clone; strict-tuned instructions and settings | Launched by `asyncio.gather` |
| **Tests reviewer** | Finds untested paths and assertions that cannot fail | Clone; strict-tuned instructions and settings | Launched by `asyncio.gather` |
| **Style reviewer** | Finds readability and consistency defects | Clone; `normal` strictness | Launched by `asyncio.gather` |
| **Merge specialist** | Deduplicates and severity-orders the three finding sets | Own declaration | **Tool call** via `as_tool` — the Desk keeps the conversation |
| **Remediation specialist** | Proposes the patch for a critical security finding, to the operator | Own declaration | **Handoff** — control transfers when a critical security finding exists |

**Why the two specialists are wired differently** (the brief requires this be argued; `spec.md`
Assumptions carries the two-sentence version): merging *returns a value the Desk still needs* —
the merged set is what the report and the footer are built from — so it must be a call the Desk
makes and resumes from. Remediation *hands the operator a different job*: a patch proposal in
another voice. Swapping them would leave the Desk unable to assemble its own report, and would
strand remediation as a call that can never propose anything.

**Concurrency (FR-5).** The three reviewers are cloned from the base, then started together and
awaited as a group:

```python
async def review(chunks, context):
    reviewers = [security.clone(), tests.clone(), style.clone()]
    started = time.perf_counter()
    results = await asyncio.gather(*(run_one(r, chunks, context) for r in reviewers))
    return results, time.perf_counter() - started
```

The sequential comparison needed for the viva is the same call with `gather` replaced by an
`await` inside a loop. Nothing else changes, which is what makes the two wall-clock numbers
comparable: identical work, identical agents, one difference in scheduling.

## Tool Contracts

Every tool's signature, and the control that governs it. The `ctx` parameter is **injected and
excluded from the generated schema** — this is FR-2's mechanism, and verifying it is part of
FR-2's "done when".

| Tool | Signature | Returns | Control |
|------|-----------|---------|---------|
| `read_ruleset` | `(ctx: RunContextWrapper[ReviewContext], ruleset_id: str) -> str` | The ruleset text, or a sentence if it cannot be read | Forced with `ModelSettings(tool_choice=...)` so the model has no choice but to call it (FR-9). Reads `ruleset_id` through the wrapper; `ctx` never appears in the schema |
| `read_diff_chunk` | `(ctx: RunContextWrapper[ReviewContext], path: str) -> str` | One chunk's text, or a sentence the model can act on | `failure_error_function=` returns a sentence; a raise into the runner is a defect (NFR-4) |
| `merge_findings` | Merge agent exposed via `as_tool(...)` | A deduplicated, severity-ordered finding list | Tool call — the conversation stays with the Desk (FR-6) |

## Boundary Structures

| Structure | Shape | Crosses which boundary | Notes |
|-----------|-------|------------------------|-------|
| `ReviewContext` (dataclass) | `repo: str`, `language: str`, `ruleset_id: str`, `strictness: str = "normal"` | Operator → every run | Travels in the run context, never in prompt text (FR-2) |
| `DiffChunk` | `path: str`, `text: str` | Splitter → reviewers | Produced before any model call (FR-1) |
| `Finding` (pydantic) | `file: str`, `line: int`, `severity: Literal["critical","major","minor"]`, `message: str` | Reviewer → merge → report | Reviewer `output_type` is `list[Finding]`; the SDK wraps a list root in an object with a `response` key because strict schemas must be objects, while `final_output` is still a plain Python list (FR-3) |
| `ReviewerStat` | `agent: str`, `ms: int`, `tokens: int` | Hooks → report footer | Token counts read from the run context, not estimated (FR-10) |
| `Report` | `findings: list[Finding]`, `footer: list[ReviewerStat]`, `partial: bool` | Pipeline → guardrail → interface | The artifact the output guardrail inspects (FR-8) |
| `LedgerEntry` | `ts`, `request_id`, `agent`, `ms`, `findings` | Trace processor → `ledger.jsonl` | No diff content, no finding text, no credential (FR-11, NFR-1) |

## Decided Numbers and Their Reasoning

- **Turn ceiling: 8 turns per reviewer.** FR-9 requires the ceiling and the reasoning behind the
  number to be stated. The floor is the work a reviewer must do — one forced `read_ruleset` call,
  at least one diff-chunk read, and the final structured finding pass — which is three turns, so
  the ceiling sits comfortably above the SDK's own default and the default is never the thing that
  fires. The headroom to eight lets a reviewer re-read a chunk and retry a failed tool call
  without dying, while still terminating a reviewer that starts calling a tool in a loop well
  inside the phase budget. Note also that `tool_choice` resets to `"auto"` after the first call,
  so the forced-call setting cannot itself *cause* a loop.
- **`ledger.jsonl` will contain more lines than there are reviewers.** It records one line per
  completed run, and a single review produces more runs than three: the three reviewers, the merge
  specialist, the remediation handoff when it fires, and the guardrail's own check. This is
  expected, and it is the answer to the viva question about extra ledger lines.
- **Ledger registration point.** The processor is registered once at startup by the entry point.
  No agent definition imports or mentions it, so removing that one registration is the whole
  switch — which is FR-11's "done when".

## Project Structure

### Documentation (this feature)

```text
specs/001-code-review-desk/
├── plan.md              # This file (/sp.plan command output)
├── research.md          # Phase 0 output — decisions and rejected alternatives
├── data-model.md        # Phase 1 output — entities and validation rules
├── quickstart.md        # Phase 1 output — operator runbook and viva walkthrough
├── contracts/           # Phase 1 output — tool and structure contracts
├── checklists/
│   └── requirements.md  # Spec quality validation
└── tasks.md             # Phase 2 output (/sp.tasks command — NOT created by /sp.plan)
```

### Source Code (repository root)

```text
src/desk/
├── __init__.py
├── config.py         # dotenv load + require_env(): fail-fast on a missing key (NFR-1)
├── diff.py           # split a unified diff into DiffChunks before any model call (FR-1)
├── models.py         # ReviewContext, DiffChunk, Finding, ReviewerStat, Report (FR-2, FR-3)
├── agents.py         # base reviewer + three clones + both specialists (FR-1, FR-5, FR-6)
├── tools.py          # read_ruleset, read_diff_chunk, merge-as-tool wiring (FR-2, FR-6, FR-9)
├── guardrails.py     # output guardrail: credential-shape refusal (FR-8)
├── hooks.py          # RunHooks (all reviewers) + AgentHooks (exactly one) (FR-10)
├── ledger.py         # trace processor appending one line per run (FR-11)
├── pipeline.py       # gather the clones, merge, hand off, assemble the report (FR-5, FR-6)
└── cli.py            # async entry point: require_env first, then run (FR-1, NFR-1)

app.py                # Chainlit page: paste a diff, stream findings, hold session state (FR-12)
rulesets/             # ruleset files a reviewer must consult (FR-9)
tests/                # pytest: wall-clock comparison, guardrail refusal, split, ceiling
.env.example          # variable names without values (NFR-1)
```

**Structure Decision**: Single project, chosen because there is one deliverable surface (a CLI
plus one local page) and one deploy target (the operator's machine). A web/mobile split would
create directories with nothing in them, and a backend/frontend split would imply a network
boundary that does not exist here — the interface imports the pipeline directly. The layering
inside `src/desk/` is by responsibility, and each module maps onto named requirements so a reader
can trace a file back to the requirement it serves.

## Traceability

| Requirement | Mechanism |
|---|---|
| FR-1 split before any model call | `diff.py`, called from `cli.py` before the first run |
| FR-1 async entry point | `async def main()`; the asynchronous run is awaited, never the sync variant |
| FR-2 context not in prompt | `RunContextWrapper[ReviewContext]`; `ctx` excluded from the tool schema |
| FR-3 typed findings | `output_type=list[Finding]`; `final_output` is a plain list |
| FR-4 per-run instructions | `instructions=` given a callable resolved at request time |
| FR-5 concurrency | `asyncio.gather` over clones of one base reviewer |
| FR-6 tool vs handoff | `as_tool()` for merge; `handoffs=[...]` for remediation |
| FR-7 run-level override | `RunConfig(model=...)` passed to the run only |
| FR-8 credential refusal | `@output_guardrail`; the tripwire exception is caught in `pipeline.py` |
| FR-9 required tool / failing tool / ceiling | `tool_choice`; `failure_error_function`; `max_turns` with `MaxTurnsExceeded` caught |
| FR-10 latency and tokens | `RunHooks` for all reviewers; `AgentHooks` on exactly one; usage from the run context |
| FR-11 ledger | trace processor registered once at startup |
| FR-12 streaming | streamed run plus event iteration, awaited from the page |
| FR-13 one trace | tracing enabled and exported under the project's own key |
| NFR-1 secrets | `config.require_env("OPENAI_API_KEY")` loads the repository-root `.env` through `python-dotenv`; the guardrail covers the outbound path; the ledger writer is passed metadata only, never diff or finding text |
| NFR-2 cost | every agent declares its own `model_settings`; `max_turns` bounds every review |
| NFR-3 observability | tracing enabled for every review, plus the ledger processor recording every run |
| NFR-4 failure | `failure_error_function` on the reading tools; no tool raises into the runner |
| NFR-5 provenance | the Phase 0 commit precedes any source file, verified from `git log` order in T038 |

*Re-checked after Phase 1 design: no principle moved from PASS.*

## Complexity Tracking

No Constitution Check violations. Nothing in this plan required a simpler alternative to be
rejected, so this table is intentionally empty.
