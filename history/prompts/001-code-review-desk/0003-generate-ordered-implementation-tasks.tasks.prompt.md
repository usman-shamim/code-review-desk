---
id: 0003
title: Generate ordered implementation tasks
stage: tasks
date: 2026-09-25
surface: opencode
model: unspecified
feature: 001-code-review-desk
branch: 001-code-review-desk
user: usman
command: sp.tasks
labels: [tasks, phase-0, sequencing]
links:
  spec: specs/001-code-review-desk/spec.md
  ticket: none
  adr: none
  pr: none
files:
  - specs/001-code-review-desk/tasks.md
tests:
  - "format check: every task matches '- [ ] T0NN [P?] [USn?] description (FR-x)'"
  - "requirement coverage: all 13 FR and 5 NFR named by at least one task"
---

## Prompt

```
/goal complete the specs using speckit plus
```

Executed as `/sp.tasks` against `plan.md`, `spec.md`, `research.md`, `data-model.md` and
`contracts/`, after confirming with `check-prerequisites.sh --json` that the feature directory and
all four optional documents were discoverable.

## Response snapshot

Generated `tasks.md` organised by user story so each story is an independently implementable,
testable and demonstrable increment: Phase 1 Setup (T001–T005), Phase 2 Foundational
(T006–T008, blocking all stories), then one phase per user story — US1 intake and typed findings
(T009–T015), US2 concurrent reviewers and the merged report (T016–T022), US3 the leak-proof and
bounded report (T023–T027), US4 observability and interface (T028–T034) — and a final polish phase
(T035–T038).

Each task follows the required checklist format and, because the brief requires it, ends with the
requirement it serves in parentheses. Dependencies, per-story checkpoints, parallel opportunities
and an MVP-first strategy are all included, and the brief's cut order is restated against the
specific task IDs it would remove: `FR-11` is T031, `FR-7` is T021, and the agent-level hooks in
`FR-10` are T029 — while `FR-5` (T016–T018) and `FR-8` (T023–T024) are marked as never-cut.

Tests are included only for the requirement pairs the brief actually grades: the concurrency
wall-clock comparison, the guardrail refusal, the diff split and the ceiling.

## Outcome

- ✅ Impact: Phase 0 artifact 4 of 4 complete. The four artifacts now exist and agree with each other, so the gate can be satisfied
- 🧪 Tests: Format validation PASS (38 tasks, all with checkbox, ID, optional `[P]`, story label where required, file path, and requirement tag); requirement coverage PASS (13 FR and 5 NFR each named)
- 📁 Files: `specs/001-code-review-desk/tasks.md`
- 🔁 Next prompts: `/sp.analyze` for cross-artifact consistency, then `/sp.implement` to begin at T001 — after the Phase 0 commit
- 🧠 Reflection: Numbering the cut order against task IDs rather than requirement IDs is what makes the cut order usable under time pressure; "cut FR-11" means locating a decision, whereas "cut T031" means deleting one task. Naming a requirement on every task also makes the coverage check mechanical rather than a judgement call.

## Evaluation notes (flywheel)

- Failure modes observed: The stock task template embeds sample tasks and instructs that they be replaced; leaving any of them in place would have produced a task list that reads as complete while describing a different project. Every template task was replaced, and the template's "Tests are OPTIONAL" note was resolved explicitly rather than left as a policy statement — tests are carried for the graded requirement pairs and the "done when" clauses cover the rest.
- Graders run and results (PASS/FAIL): Checklist-format validation PASS (38/38). Requirement-tag coverage PASS (FR-1…FR-13, NFR-1…NFR-5). Cut-order consistency with the brief PASS (FR-11 → FR-7 → agent-level FR-10, never FR-5 or FR-8). Story independence PASS — US3 guards the report and needs only US1, so it does not silently depend on US2.
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Add an explicit "requirement not covered by any task" assertion to the tasks command. Coverage was verified by hand here; it is exactly the kind of check that should be mechanical, because a missing requirement is invisible in a long task list.
