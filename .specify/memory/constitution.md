<!--
Sync Impact Report
==================
Version change: uninitialised template → 1.0.0
Bump rationale: initial ratification. The file shipped as the raw Spec Kit
template containing only placeholder tokens, so there is no prior version to
increment; the first concrete ratification is 1.0.0.

Modified principles (template placeholder → title):
  - Template slot 1 (was PRINCIPLE_1_NAME) → I. Specification Before Implementation
  - Template slot 2 (was PRINCIPLE_2_NAME) → II. Model Configured On The Agent
  - Template slot 3 (was PRINCIPLE_3_NAME) → III. Secrets Stay In .env
  - Template slot 4 (was PRINCIPLE_4_NAME) → IV. Tools Return Sentences, Never Raise
  - Template slot 5 (was PRINCIPLE_5_NAME) → V. A Review Is Reproducible From The Diff
  - Template slot 6 (was PRINCIPLE_6_NAME) → VI. Concurrency And Guardrails Are Load-Bearing

Added sections:
  - Additional Constraints (provider and level, cost, observability)
  - Development Workflow (requirement discipline, cut order, quality gates)
  - Governance (amendment procedure, versioning policy, compliance review)

Removed sections: none

Templates requiring updates:
  ✅ .specify/templates/plan-template.md   — Constitution Check section maps
     directly onto these six principles; no edit required.
  ✅ .specify/templates/spec-template.md   — mandatory sections already cover
     requirements, success criteria and assumptions; no edit required.
  ✅ .specify/templates/tasks-template.md  — test tasks remain OPTIONAL, which
     matches the Development Workflow section; no edit required.
  ✅ .specify/templates/phr-template.prompt.md — contains no agent-specific
     names; no edit required.
  ⚠  .specify/templates/commands/*.md — this path does not exist in this
     checkout. The slash commands live in .opencode/command/ instead, which is
     gitignored by project choice. Recorded here so the gap is not mistaken for
     a missed update.

Follow-up TODOs: none
-->

# Code Review Desk Constitution

## Core Principles

### I. Specification Before Implementation (NON-NEGOTIABLE)

Four artifacts — `constitution.md`, `spec.md`, `plan.md`, `tasks.md` — MUST be committed
before the first line of source code. The Phase 0 commit MUST contain specification only: a
single commit mixing a spec artifact with implementation fails the phase even if the code
runs correctly. Any later change of intent MUST amend the spec artifact first and the code
second.

**Rationale**: the git history is graded evidence. A specification written after the code
records what was built, not what was required, and cannot be used to hold the build to
account.

### II. Model Configured On The Agent

Every agent MUST declare its own model and its own model settings. No agent may inherit an
SDK default, and no builder may leave `model=` unset on the assumption that something
upstream will supply it. Reviewers run OpenAI `gpt-5-nano`, configured on the agent itself.
An alternate or lower-cost model for a single execution MUST be applied at run level and
MUST NOT be written into any agent definition.

**Rationale**: FR-1 and FR-7 are graded as a contrast — agent-level model identity versus
run-level override. An unset model also risks an upstream default changing tier silently,
which would move the build's cost and behaviour without any diff to review.

### III. Secrets Stay In .env

Every credential lives in a gitignored `.env` and nowhere else. A missing credential MUST
stop the program at startup with one sentence on stderr and a non-zero exit status, never a
traceback. No credential — and nothing shaped like one — may be written to the ledger, the
report, the trace, or the interface.

**Rationale**: NFR-1 and FR-8. A review report that quotes the very secret it found in the
diff is precisely the failure this project exists to prevent, and it is checked for.

### IV. Tools Return Sentences, Never Raise

A tool that meets bad input MUST return a sentence the model can act on. A tool that raises
into the runner is a defect, not an error path. Tool failures MUST be routed to a dedicated
error handler rather than allowed to propagate, and every review MUST run under a turn
ceiling that is caught and reported to the user as a partial review.

**Rationale**: NFR-4 and FR-9. An escaping exception aborts the entire review, discarding
the other reviewers' completed work and destroying the concurrency the pipeline depends on.

### V. A Review Is Reproducible From The Diff

The same diff and the same run context MUST produce the same review. Parameters that vary
between runs — repository, language, ruleset, strictness — MUST travel in the run context
and be read by tools; they MUST NOT be pasted into prompt text. Reviewer instructions MUST
be assembled at request time from that context rather than hard-coded.

**Rationale**: FR-2 and FR-4. Prompt text is invisible to the type system and leaks
repository detail into the trace, where it cannot be validated. A review that cannot be
re-derived from its diff is not evidence of anything.

### VI. Concurrency And Guardrails Are Load-Bearing (NON-NEGOTIABLE)

The three reviewers MUST run concurrently over a single split diff, and the output guardrail
MUST inspect the finished report before that report reaches the user. Neither is ever cut.
When the schedule slips, cuts come from the documented cut order and from nowhere else.

**Rationale**: FR-5 and FR-8 are the two capabilities this project is built to demonstrate
and the two the viva interrogates. A working sequential version does not satisfy FR-5, and
an unguarded report does not satisfy FR-8.

## Additional Constraints

- **Provider and level**: OpenAI. Reviewers run `gpt-5-nano` at agent level (Principle II).
  The only sanctioned deviation is a run-level override for FR-7.
- **Credentials**: `OPENAI_API_KEY`, read from `.env` only (Principle III).
- **Cost**: no unbounded generation. Turn ceilings and explicit model settings bound every
  execution (NFR-2).
- **Observability**: every review MUST appear as one trace exported under the project's own
  key, and every individual run MUST append one line to the ledger (NFR-3, FR-11, FR-13).
- **Runtime**: Python with uv-managed dependencies; the entry point is asynchronous (FR-1).
  The split of a diff happens before any model call.

## Development Workflow

- Requirements are numbered `FR-1`…`FR-13` and `NFR-1`…`NFR-5`, and each MUST be
  demonstrable on demand. "FR-5 works" means two wall-clock numbers can be shown side by
  side; "FR-8 works" means a planted key produces a refusal.
- **Cut order when behind**: `FR-11`, then `FR-7`, then the agent-level hooks in `FR-10`.
  `FR-5` and `FR-8` are never cut (Principle VI).
- Every task in `tasks.md` MUST name the requirement it serves.
- Tests are OPTIONAL, per the task template. Where a requirement carries a checkable
  "done when" clause, that clause is its acceptance test and MUST be exercised before the
  requirement is called complete.
- No source file is written before the Phase 0 commit (Principle I).

## Governance

This constitution supersedes other practices where they conflict. Where the assignment brief
and this document disagree, the disagreement MUST be recorded in the spec's Assumptions
section rather than resolved silently.

**Amendment procedure**: an amendment is proposed as a change to this file; it states which
principle it alters and why; it updates the Sync Impact Report at the top; and it is
committed separately from implementation work. Amendments affecting FR-5 or FR-8 MUST be
justified against the viva, not merely against the clock.

**Versioning policy**: MAJOR for removing or redefining a principle, MINOR for adding a
principle or materially expanding guidance, PATCH for clarifications that change no
behaviour.

**Compliance review**: before each phase closes, the current state MUST be checked against
these principles. A known violation is either fixed or recorded in the plan's Complexity
Tracking table together with the simpler alternative that was rejected. Provenance
(Principle I) is verified from `git log` order, never from memory.

**Version**: 1.0.0 | **Ratified**: 2026-09-25 | **Last Amended**: 2026-09-25
