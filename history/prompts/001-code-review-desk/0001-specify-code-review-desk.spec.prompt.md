---
id: 0001
title: Specify Code Review Desk
stage: spec
date: 2026-09-25
surface: opencode
model: unspecified
feature: 001-code-review-desk
branch: 001-code-review-desk
user: usman
command: sp.specify
labels: [spec, phase-0, requirements]
links:
  spec: specs/001-code-review-desk/spec.md
  ticket: none
  adr: none
  pr: none
files:
  - specs/001-code-review-desk/spec.md
  - specs/001-code-review-desk/checklists/requirements.md
tests:
  - "checklist validation: all 16 items pass, one recorded exception on tech-agnosticism"
---

## Prompt

```
/goal complete the specs using speckit plus
```

Executed as `/sp.specify` with the feature description derived from the assignment brief: a
spec-first review pipeline that splits a unified diff by file, runs security, tests and style
reviewers concurrently, merges their findings into one typed report, hands off to a remediation
agent on critical security findings, streams findings to a Chainlit interface, and refuses to
emit any report that quotes a credential.

## Response snapshot

Ran the real `create-new-feature.sh` rather than hand-rolling files: it created and checked out
`001-code-review-desk`, copied `spec-template.md` into `specs/001-code-review-desk/spec.md`, and
created the matching `history/prompts/001-code-review-desk/` directory.

Filled the spec with four prioritised user stories, each independently testable — US1 intake and
typed findings (P1, the MVP), US2 three concurrent reviewers with one merged report (P2), US3 a
report that cannot leak and cannot hang (P3), US4 watching the review happen (P4). All 13
functional requirements are restated as behaviour with the brief's "done when" clause attached as
its acceptance criteria, plus five non-functional requirements, twelve edge cases, ten measurable
success criteria, the key entities, and an Assumptions section.

Two content decisions the brief mandates that a purely behavioural spec would not carry: the three
explicit non-goals (never modifies the reviewed repository, never executes the reviewed code, never
stores review content), and the two-sentence argument for why merging is a tool call while
remediation is a transfer — which lives in Assumptions so FR-6's "done when" clause has something
to point at.

`FR-1` names OpenAI `gpt-5-nano` and the repository-root `.env`, and `NFR-1` spells out the
dotenv requirement: credentials loaded from a gitignored `.env` at startup, a missing key failing
with one sentence and a non-zero exit rather than a traceback, a committed `.env.example`, and no
secret ever reaching the ledger, report, trace or interface.

## Outcome

- ✅ Impact: Phase 0 artifact 2 of 4. Every requirement is now numbered, testable and traceable to a user story
- 🧪 Tests: `checklists/requirements.md` — all content-quality, completeness and readiness items pass
- 📁 Files: `specs/001-code-review-desk/spec.md`; `specs/001-code-review-desk/checklists/requirements.md`; plus the branch and `history/prompts/001-code-review-desk/` created by the script
- 🔁 Next prompts: `/sp.clarify` if any requirement were ambiguous (none were); `/sp.plan` to fix the architecture
- 🧠 Reflection: The brief's requirement that the spec justify its own tool-versus-handoff choice is easy to satisfy dishonestly — a sentence that describes the choice rather than defending it. Writing the argument as "what would break if you swapped them" produced a genuinely checkable claim, and it later became the Justification the plan's routing table depends on.

## Evaluation notes (flywheel)

- Failure modes observed: Two. First, the spec template's tech-agnosticism rule conflicts with the brief, which mandates naming the provider, the model, the credential file and the ledger filename. Resolved by ticking the item with a recorded exception listing exactly the four brief-quoted specifics, rather than either failing the checklist or silently violating it. Second, the toolchain forbids editing the spec without reading it first, and the script had already created the file from the template — reading it before writing avoided an overwrite rejection.
- Graders run and results (PASS/FAIL): Customary spec-template validation PASS with one documented exception. Requirement count against the brief (13 FR, 5 NFR) PASS. Non-goal count (exactly three) PASS. Numbering kept in the brief's `FR-1` form rather than the template's illustrative `FR-001`, so "FR-5 works" is checkable as written.
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Front-load the provider question. It was asked once here and the answer propagated cleanly into FR-1, FR-7 and NFR-1; asking after the spec was drafted would have meant three coordinated edits.
