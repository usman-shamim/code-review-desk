---
description: "Task list for Code Review Desk implementation"
---

# Tasks: Code Review Desk

**Input**: Design documents from `/specs/001-code-review-desk/`
**Prerequisites**: `plan.md`, `spec.md` (both present), `research.md`, `data-model.md`, `contracts/`

**Tests**: Included for the requirement pairs the brief grades (concurrency and the guardrail), plus the
split and the ceiling. Every other requirement is verified by the "done when" clause recorded in
`spec.md` and the commands in `quickstart.md`.

**Organization**: Tasks are grouped by user story so each story is independently implementable,
testable and demonstrable. Every task names the requirement it serves.

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
- [ ] T011 [US1] Implement the base reviewer in `src/desk/agents.py` with `model="gpt-5-nano"` set on the agent and `instructions=` given a callable that assembles the prompt from context (FR-1, FR-4)
- [ ] T012 [US1] Set the reviewer's `output_type` to `list[Finding]` and print the generated schema to confirm the list root is wrapped in an object with a `response` key (FR-3)
- [ ] T013 [US1] Implement `src/desk/pipeline.py` `run_reviewer()` for a single reviewer, returning a plain list in `final_output` (FR-1, FR-2, FR-3, FR-4)
- [ ] T014 [US1] Implement `src/desk/cli.py` as an async entry point — `require_env("OPENAI_API_KEY")` first, then split the diff, then run; expose `--dry-run-split`, `--print-prompt`, `--print-schema`, `--count-criticals` (FR-1, NFR-1)
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
- [ ] T017 [US2] Launch the three reviewers with `asyncio.gather` in `src/desk/pipeline.py` and record the concurrent wall clock (FR-5)
- [ ] T018 [US2] Add a `--timing sequential` variant that awaits the same reviewers in a loop, so the two numbers are directly comparable (FR-5)
- [ ] T019 [P] [US2] Implement the Merge specialist in `src/desk/agents.py` and expose it with `as_tool` in `src/desk/tools.py`; deduplicate on `(file, line)` keeping the highest severity (FR-6)
- [ ] T020 [P] [US2] Implement the Remediation specialist in `src/desk/agents.py` with a typed handoff input naming the finding that triggered it (FR-6)
- [ ] T021 [US2] Apply the cheaper re-run through `RunConfig(model=...)` in `src/desk/pipeline.py`, leaving every agent definition untouched, exposed as `--cheap` (FR-7)
- [ ] T022 [US2] Write tests in `tests/test_concurrency.py` asserting concurrent time is below the sum of the three individual times, and in `tests/test_routing.py` asserting merge fires as a tool call and remediation as a handoff (FR-5, FR-6, FR-7)

**Checkpoint**: The centrepiece works and both wall-clock numbers can be shown.

---

## Phase 5: User Story 3 — A report that cannot leak and cannot hang (Priority: P3)

**Goal**: The guardrail refuses credential-shaped reports, tools fail into sentences, and every
review is bounded by a ceiling.

**Independent Test**: `samples/planted-key.diff` produces a refusal; `samples/two-file.diff` passes
untouched; deleting the ruleset still completes; the ceiling produces a partial review.

### Implementation for User Story 3

- [ ] T023 [US3] Implement the credential-shape detector and the `@output_guardrail` in `src/desk/guardrails.py`, returning `GuardrailFunctionOutput` with `tripwire_triggered` set (FR-8)
- [ ] T024 [US3] Catch `OutputGuardrailTripwireTriggered` in `src/desk/pipeline.py` and report the refusal instead of crashing (FR-8)
- [ ] T025 [P] [US3] Force the ruleset call with `ModelSettings(tool_choice=...)` on the reviewer in `src/desk/agents.py` (FR-9)
- [ ] T026 [US3] Set `max_turns=8` on review runs and catch `MaxTurnsExceeded` in `src/desk/pipeline.py`, reporting a partial review that names the ceiling (FR-9, NFR-2)
- [ ] T027 [US3] Write tests in `tests/test_guardrail.py` (planted key → refusal; clean diff → passes; no credential in any emitted line) and `tests/test_ceiling.py` (missing ruleset still completes) (FR-8, FR-9, NFR-1, NFR-4)

**Checkpoint**: Nothing leaks and nothing hangs.

---

## Phase 6: User Story 4 — Watching the review happen (Priority: P4)

**Goal**: Measured latency and tokens in a footer, a ledger of one line per run, findings streamed to
the interface, and one trace per review.

**Independent Test**: Footer shows three rows from the run context; `ledger.jsonl` grows by one line
per run for a three-file diff; findings appear before completion; the trace shows overlapping spans.

### Implementation for User Story 4

- [ ] T028 [P] [US4] Implement `RunHooks` in `src/desk/hooks.py` recording start and end times and reading token counts from the run context (FR-10)
- [ ] T029 [P] [US4] Implement `AgentHooks` in `src/desk/hooks.py` and attach them to exactly one reviewer (FR-10)
- [ ] T030 [US4] Assemble the `footer` of `ReviewerStat` rows in `src/desk/pipeline.py` and render it under the report (FR-10)
- [ ] T031 [US4] Implement the ledger trace processor in `src/desk/ledger.py` appending one `LedgerEntry` per run to `ledger.jsonl`, registered once in `src/desk/cli.py` (FR-11, NFR-1)
- [ ] T032 [US4] Implement `app.py` — the Chainlit page accepting a pasted diff, streaming findings as they arrive, holding context and the last report in session state, and awaiting its run (FR-12)
- [ ] T033 [US4] Enable tracing and export it under the project's own key so one review is one trace (FR-13, NFR-3)
- [ ] T034 [US4] Write tests in `tests/test_footer.py` (three rows, counts read from context) and `tests/test_ledger.py` (one line per run; no diff text and no credential in any line) (FR-10, FR-11, FR-13)

**Checkpoint**: The review is observable end to end.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Close the loop on the requirements that are verified rather than built.

- [ ] T035 [P] Run every command in `specs/001-code-review-desk/quickstart.md` and correct any that do not behave as documented (all FRs)
- [ ] T036 [P] Run `uv run ruff check .` and `uv run pytest` to green (NFR-2)
- [ ] T037 Record the measured concurrent-versus-sequential wall clock, the ceiling in force, and the refusal message in a short `REPORT.md` (FR-5, FR-8, FR-9)
- [ ] T038 Verify the provenance gate from `git log` — the four Phase 0 artifacts appear before any source file (NFR-5)

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
- T023, T025 and T028, T029 are separate modules: run together
- T035 and T036 are independent: run together

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

If the clock runs short, cut from the bottom of the brief's list — `FR-11` (T031), then `FR-7`
(T021), then the agent-level hooks in `FR-10` (T029) — and **never** `FR-5` (T016–T018) or `FR-8`
(T023–T024).

---

## Notes

- `[P]` means a different file with no dependency on incomplete work
- Every task names its requirement, so a story's coverage can be read straight off this list
- Commit after each logical group; keep the Phase 0 commit free of source files (NFR-5)
- Stop at any checkpoint to validate a story on its own
