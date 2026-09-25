---
description: "Task list for Code Review Desk implementation"
---

# Tasks: Code Review Desk

**Input**: Design documents from `/specs/001-code-review-desk/`
**Prerequisites**: `plan.md`, `spec.md` (both present), `research.md`, `data-model.md`, `contracts/`

**Tests**: Included for the requirement pairs the brief grades (concurrency and the guardrail), plus the
split, the ceiling, the footer, the ledger and the streaming path. Every remaining requirement is
verified by the "done when" clause recorded in `spec.md`.

**Organization**: Tasks are grouped by user story so each story is independently implementable,
testable and demonstrable. Every task names the requirement it serves.

**ID stability**: task IDs are append-only. The cut-order references below depend on them, so a task
is never renumbered — new work takes the next free ID and is placed in its phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1…US4)
- Every description ends with the requirement it serves, in parentheses

## Path Conventions

Single project: `src/desk/`, `app.py`, `tests/`, `rulesets/`, `samples/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and the fixtures every story needs.

- [ ] T001 Create the `uv` project with dependencies — `openai-agents`, `pydantic`, `python-dotenv`, `chainlit`, and `pytest`/`ruff` as dev dependencies — in `pyproject.toml` (NFR-2)
- [ ] T002 [P] Create `.env.example` naming `OPENAI_API_KEY` with no value in it (NFR-1)
- [ ] T003 [P] Extend `.gitignore` with `.env`, `ledger.jsonl`, `.venv/`, `__pycache__/` (NFR-1, FR-11)
- [ ] T004 [P] Create `rulesets/python-strict.md` — the ruleset a reviewer must consult (FR-9)
- [ ] T005 [P] Create sample diffs in `samples/`: `two-file.diff`, `three-file.diff`, `planted-key.diff`, `planted-critical.diff`, `duplicate-findings.diff`, plus an empty and a malformed diff (FR-1, FR-5, FR-6, FR-8)

**Checkpoint**: Environment installs, fixtures exist.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pieces every user story depends on. **No user story can start until this phase is done.**

- [ ] T006 Implement `src/desk/config.py` — load the repository-root `.env` with `python-dotenv` at import, and `require_env()` that prints one sentence to stderr and exits non-zero rather than raising (NFR-1)
- [ ] T007 Implement `src/desk/models.py` — the `ReviewContext` dataclass and the `Finding`, `ReviewerStat` and `Report` models, per `contracts/structures.md` (FR-2, FR-3)
- [ ] T008 Implement `src/desk/diff.py` — split a unified diff into one `DiffChunk` per file, with empty and malformed input producing a readable message instead of raising (FR-1)

**Checkpoint**: Context, models and the splitter exist — user stories can now begin.

---

## Phase 3: User Story 1 — Intake and a typed review (Priority: P1) 🎯 MVP

**Goal**: A diff path in, typed findings out, with repository rules arriving through the run context
and instructions assembled per run.

**Independent Test**: Run the CLI over `samples/two-file.diff` and confirm two chunks are produced
before any model call, the `read_ruleset` schema contains no `ctx` property, the resolved prompt
contains no repository name, and criticals can be counted with one Python expression.

### Implementation for User Story 1

- [ ] T009 [US1] Implement `read_ruleset` in `src/desk/tools.py` taking `ctx: RunContextWrapper[ReviewContext]` as its first parameter and reading `ruleset_id` through it (FR-2)
- [ ] T010 [US1] Implement `read_diff_chunk` in `src/desk/tools.py` with `failure_error_function` returning a sentence rather than raising (FR-2, NFR-4)
- [ ] T011 [US1] Implement the base reviewer in `src/desk/agents.py` with `model="gpt-5-nano"` and explicit `model_settings` on the agent, and `instructions=` given a callable that assembles the prompt from context (FR-1, FR-4, NFR-2)
- [ ] T012 [US1] Set the reviewer's `output_type` to `list[Finding]` and print the generated schema to confirm the list root is wrapped in an object with a `response` key (FR-3)
- [ ] T013 [US1] Implement `src/desk/pipeline.py` `run_reviewer()` for a single reviewer, returning a directly iterable list in `final_output` (FR-1, FR-2, FR-3, FR-4)
- [ ] T014 [US1] Implement `src/desk/cli.py` as an async entry point — `require_env("OPENAI_API_KEY")` first, then split the diff, then run. Full flag surface: `--repo`, `--language`, `--ruleset`, `--strictness`, `--dry-run-split`, `--print-prompt`, `--print-schema`, `--count-criticals`, `--timing`, `--cheap`, `--show-footer` (FR-1, NFR-1)
- [ ] T015 [US1] Write tests in `tests/test_diff_split.py` (two files → two chunks; empty and malformed → message) and `tests/test_context_schema.py` (no `ctx` in schema; no repo name in prompt) (FR-1, FR-2, FR-4)

**Checkpoint**: MVP — a diff goes in, typed findings come out, and the context/schema invariants hold.

---

## Phase 4: User Story 2 — Concurrent reviewers, one merged report (Priority: P2)

**Goal**: Three reviewers derived from the base, running at once, with the two specialists wired two
different ways, plus the run-level model override.

**Independent Test**: Show concurrent and sequential wall-clock numbers side by side; fire both
specialist paths; re-run on the override model with `git diff --stat src/desk/agents.py` empty.

### Implementation for User Story 2

- [ ] T016 [P] [US2] Derive the security, tests and style reviewers in `src/desk/agents.py` by cloning the base and overriding only instructions and model settings (FR-5)
- [ ] T017 [US2] Launch the three reviewers with `asyncio.gather(..., return_exceptions=True)` in `src/desk/pipeline.py` and record the concurrent wall clock. The flag is load-bearing: with the default `False`, one reviewer exhausting its ceiling aborts the group and discards the other two (FR-5, FR-9)
- [ ] T018 [US2] Add a `--timing sequential` variant that awaits the same reviewers in a loop, so the two numbers are directly comparable (FR-5)
- [ ] T019 [P] [US2] Implement the Merge specialist in `src/desk/agents.py` with its own `model` and `model_settings`, and expose it in `src/desk/tools.py` with `as_tool(..., parameters=...)` so the findings arrive as structured input — a nested `as_tool` run does not inherit the parent's state (FR-6, NFR-2)
- [ ] T020 [P] [US2] Implement the Remediation specialist in `src/desk/agents.py` with its own `model` and `model_settings`, and a typed handoff input naming the finding that triggered it (FR-6, NFR-2)
- [ ] T021 [US2] Apply the cheaper re-run through `RunConfig(model=...)` in `src/desk/pipeline.py`, leaving every agent definition untouched, exposed as `--cheap` (FR-7)
- [ ] T022 [US2] Write tests in `tests/test_concurrency.py` asserting the concurrent wall clock is at most 1.5x the slowest single reviewer and below 60% of the sequential total, and in `tests/test_routing.py` asserting merge fires as a tool call and remediation as a handoff (FR-5, FR-6)
- [ ] T023 [US2] Verify `RunConfig(model=...)` precedence empirically: run the same reviewer object on its own model and on an override, print the model actually used on each path, and assert the override took effect. FR-7 and Principle II conflict if it did not — record the result in `spec.md` Assumptions either way (FR-7)

**Checkpoint**: The centrepiece works and both wall-clock numbers can be shown.

---

## Phase 5: User Story 3 — A report that cannot leak and cannot hang (Priority: P3)

**Goal**: The guardrail refuses credential-shaped reports, tools fail into sentences, and every
review is bounded by a ceiling.

**Independent Test**: `samples/planted-key.diff` produces a refusal; `samples/two-file.diff` passes
untouched; deleting the ruleset still completes; the ceiling produces a partial review.

### Implementation for User Story 3

- [ ] T024 [US3] Implement the credential-shape detector in `src/desk/guardrails.py`, returning `GuardrailFunctionOutput` with `tripwire_triggered` set (FR-8)
- [ ] T025 [US3] Implement the Report agent in `src/desk/agents.py` — the last agent to run, emitting the `Report` and carrying the `@output_guardrail`. A `Report` assembled in Python is not an agent output, so no guardrail would ever see it (FR-8)
- [ ] T026 [US3] Catch `OutputGuardrailTripwireTriggered` from the Report agent's run in `src/desk/pipeline.py` and report the refusal instead of crashing (FR-8)
- [ ] T027 [P] [US3] Name the ruleset tool in `ModelSettings(tool_choice=...)` on the **security reviewer** in `src/desk/agents.py`, so its first turn calls the ruleset before producing findings (FR-9)
- [ ] T028 [US3] Set `max_turns=8` and `error_handlers={"max_turns": ...}` on review runs in `src/desk/pipeline.py`, so an exhausted ceiling recovers to a partial review naming the ceiling rather than raising (FR-9, NFR-2)
- [ ] T029 [US3] Write tests in `tests/test_guardrail.py` (planted key → refusal; clean diff → passes; no credential in the report, the ledger, or the trace) and `tests/test_ceiling.py` (missing ruleset still completes with the message from the plan's error-sentence contract; a looping reviewer terminates as partial) (FR-8, FR-9, NFR-1, NFR-4)

**Checkpoint**: Nothing leaks and nothing hangs.

---

## Phase 6: User Story 4 — Watching the review happen (Priority: P4)

**Goal**: Measured latency and tokens in a footer, a ledger of one line per run, findings streamed to
the interface, and one trace per review.

**Independent Test**: Footer shows one row per reviewer that ran, read from the run context;
`ledger.jsonl` grows by one line per run for a three-file diff; findings appear before completion; the
trace shows overlapping spans.

### Implementation for User Story 4

- [ ] T030 [P] [US4] Implement `RunHooks` in `src/desk/hooks.py` recording start and end times and reading token counts from the run context via `on_agent_end` (FR-10)
- [ ] T031 [P] [US4] Implement `AgentHooks` in `src/desk/hooks.py` and attach them to exactly one reviewer. Note the naming asymmetry: `AgentHooks` uses `on_start`/`on_end`, unlike `RunHooks`' `on_agent_start`/`on_agent_end` (FR-10)
- [ ] T032 [US4] Assemble the `footer` of `ReviewerStat` rows in `src/desk/pipeline.py` — one row per reviewer that ran, three on the normal path and fewer when partial — and render it under the report (FR-10)
- [ ] T033 [US4] Implement the ledger trace processor in `src/desk/ledger.py` appending one `LedgerEntry` per run to `ledger.jsonl`, registered once in `src/desk/cli.py`. The brief calls this concept a "custom runner"; the substitution is recorded in `spec.md` Assumptions (FR-11, NFR-1)
- [ ] T034 [US4] Implement `app.py` — the Chainlit page accepting a pasted diff, streaming findings as they arrive, holding context and the last report in session state, and awaiting its run (FR-12)
- [ ] T035 [US4] Enable tracing, export it under the project's own key, and set `trace_include_sensitive_data=False` so the diff and any credential in it are not recorded. The SDK default is `True` (FR-13, NFR-1, NFR-3)
- [ ] T036 [US4] Write tests in `tests/test_footer.py` (one row per reviewer that ran, counts read from context) and `tests/test_ledger.py` (one line per run; no diff text and no credential in any line) (FR-10, FR-11, FR-13)
- [ ] T037 [US4] Write `tests/test_streaming.py` asserting findings become visible before the review completes, and that a second diff in the same session reuses the existing context (FR-12)

**Checkpoint**: The review is observable end to end.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Close the loop on the requirements that are verified rather than built.

- [ ] T038 [P] Run every command in `specs/001-code-review-desk/quickstart.md` and correct any that do not behave as documented (all FRs)
- [ ] T039 [P] Run `uv run ruff check .` and `uv run pytest` to green (NFR-2)
- [ ] T040 Record the measured concurrent-versus-sequential wall clock, the ceiling in force, and the refusal message in a short `REPORT.md` (FR-5, FR-8, FR-9)
- [ ] T041 Verify the provenance gate from `git log` — the four Phase 0 artifacts appear before any source file (NFR-5)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **User Story 1 (Phase 3)**: Depends on Foundational. The MVP.
- **User Story 2 (Phase 4)**: Depends on US1 — it clones the base reviewer US1 creates
- **User Story 3 (Phase 5)**: Depends on US1 only. It guards the report, so it does not need US2.
- **User Story 4 (Phase 6)**: Depends on US1; its footer (FR-10) is most meaningful once US2 produces three reviewers.
- **Polish (Phase 7)**: Depends on all stories selected for delivery.

### Within Each User Story

- Context and models before tools; tools before agents; agents before the pipeline; pipeline before the CLI
- Tests for the graded pairs are written to fail before their implementation lands
- Story complete before moving to the next priority

### Parallel Opportunities

- T002–T005 are independent files: run together
- T016, T019 and T020 touch different specialists: run together
- T024 and T027, and T030, T031 and T035, are separate modules: run together
- T038 and T039 are independent: run together

---

## Parallel Example: User Story 2

```bash
# The three specialist definitions are separate concerns in one file:
Task: "Derive the three reviewers by cloning the base (FR-5)"
Task: "Implement the Merge specialist and expose it with as_tool (FR-6)"
Task: "Implement the Remediation specialist with a typed handoff input (FR-6)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 User Story 1 → **STOP and VALIDATE** with
`samples/two-file.diff` → demo a diff going in and typed findings coming out.

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. **US1** → validate → MVP (FR-1…FR-4)
3. **US2** → validate → the concurrency centrepiece (FR-5, FR-6, FR-7)
4. **US3** → validate → the guardrail centrepiece (FR-8, FR-9)
5. **US4** → validate → observability and interface (FR-10…FR-13)

### Cut Order

If the clock runs short, cut from the bottom of the brief's list — `FR-11` (**T033**), then `FR-7`
(**T021** and its verification **T023**), then the agent-level hooks in `FR-10` (**T031**) — and
**never** `FR-5` (**T016–T018**) or `FR-8` (**T024–T026**).

T023 is a *verification* of FR-7, not FR-7 itself: cutting FR-7 means dropping both, and the plan
records that FR-7 is specified but not demonstrated until T023 passes.

---

## Notes

- `[P]` means a different file with no dependency on incomplete work
- Every task names its requirement, so a story's coverage can be read straight off this list
- Commit after each logical group; keep the Phase 0 commit free of source files (NFR-5)
- Stop at any checkpoint to validate a story on its own
