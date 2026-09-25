---
id: 0002
title: Plan Code Review Desk architecture
stage: plan
date: 2026-09-25
surface: opencode
model: unspecified
feature: 001-code-review-desk
branch: 001-code-review-desk
user: usman
command: sp.plan
labels: [plan, phase-0, architecture, sdk]
links:
  spec: specs/001-code-review-desk/spec.md
  ticket: none
  adr: none
  pr: none
files:
  - specs/001-code-review-desk/plan.md
  - specs/001-code-review-desk/research.md
  - specs/001-code-review-desk/data-model.md
  - specs/001-code-review-desk/contracts/tools.md
  - specs/001-code-review-desk/contracts/structures.md
  - specs/001-code-review-desk/quickstart.md
  - AGENTS.md
tests:
  - "no NEEDS CLARIFICATION markers left in plan.md: grep -> no matches"
  - "constitution placement scan: all six gates stated PASS, Complexity Tracking empty"
---

## Prompt

```
/goal complete the specs using speckit plus
```

Executed as `/sp.plan` against `specs/001-code-review-desk/spec.md`, with the SDK surfaces already
documented in the installed `openai-agents-sdk` skill and cross-checked against the Context7
OpenAI Agents Python library.

## Response snapshot

Ran `setup-plan.sh --json` to copy `plan-template.md` into `plan.md`, then filled it and produced
every Phase 0 and Phase 1 output the workflow requires.

`plan.md` carries the Technical Context, a six-row Constitution Check in which every principle is
stated PASS with the mechanism that discharges it, the agent and concurrency design, a tool
contracts table, a boundary-structures table, and a requirement-to-mechanism traceability table
covering FR-1 through FR-13. Two decisions are recorded with their reasoning because the brief
demands the reasoning, not just the number: the turn ceiling is 8, justified as three turns of
necessary work plus headroom for one re-read and one retry while still bounding a tool-calling
loop; and the ledger is expected to hold more lines than there are reviewers, because the merge
run and the guardrail check also complete.

`research.md` resolves twelve decisions in Decision / Rationale / Alternatives form, including the
provider deviation, the concurrency primitive, clone-versus-redeclare, guardrail placement, the
ledger mechanism, and credential loading via `python-dotenv`. `data-model.md` gives every entity
with field-level validation traced to its requirement. `contracts/` holds the tool signatures —
noting explicitly that the `ctx` parameter is excluded from the model-visible schema, which is
FR-2's mechanism — and the boundary structures including the `response` wrapper a strict list root
requires. `quickstart.md` is an operator runbook plus a fourteen-step viva walkthrough in which
each block names a requirement, the command that demonstrates it, and the expected output.

Also ran `update-agent-context.sh opencode`, which created `AGENTS.md`. The script's placeholder
substitution for the Commands block misfires (it duplicates the placeholder rather than replacing
it), so the generated `Commands` and `Project Structure` sections were corrected by hand to the
real `uv` commands and the real `src/desk/` layout.

## Outcome

- ✅ Impact: Phase 0 artifact 3 of 4. Every requirement now has a named mechanism, and the two vice requirements (FR-5 concurrency, FR-8 guardrail) have no fallback path
- 🧪 Tests: No `NEEDS CLARIFICATION` markers remain; all six Constitution Check gates PASS; Complexity Tracking empty because nothing needed justifying
- 📁 Files: `plan.md`, `research.md`, `data-model.md`, `contracts/tools.md`, `contracts/structures.md`, `quickstart.md`, `AGENTS.md`
- 🔁 Next prompts: `/sp.tasks` to order the work; then `/sp.analyze` for cross-artifact consistency
- 🧠 Reflection: Pinning the exact structures crossing each boundary — down to the `response` wrapper the SDK generates for a list root — is what stops FR-3 from becoming a debugging session later. Verifying the SDK's actual behaviour for guardrail timing and hook usage before writing the plan meant the plan states consequences (the tripwire fires after the spend) rather than intentions.

## Evaluation notes (flywheel)

- Failure modes observed: Three. First, the `update-agent-context.sh` template leaves
  `[ONLY COMMANDS FOR ACTIVE TECHNOLOGIES]` duplicated in the Commands line and substitutes
  `cd src` for a single-project layout; hand-corrected. Second, the plan file had been created by
  the script from the template, and a partially-read file cannot be overwritten — the whole file
  had to be read in one window before writing. Third, one earlier grep raced a concurrent edit and
  reported stale content; re-run sequentially it was clean.
- Graders run and results (PASS/FAIL): Constitution Check PASS (6/6). Traceability coverage PASS (13/13 FR). No-clarification scan PASS. Requirement that FR-7's override touch no agent definition PASS by construction — only `RunConfig` carries it.
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Have the plan template pin the boundary-structures table as a mandatory section. It was the single highest-value addition here and is absent from the stock template, so it had to be added by hand.
