---
id: 0004
title: Analyze spec plan tasks consistency
stage: misc
date: 2026-09-25
surface: opencode
model: unspecified
feature: 001-code-review-desk
branch: 001-code-review-desk
user: usman
command: sp.analyze
labels: [analysis, consistency, quality-gate, remediation]
links:
  spec: specs/001-code-review-desk/spec.md
  ticket: none
  adr: none
  pr: none
files:
  - specs/001-code-review-desk/spec.md
  - specs/001-code-review-desk/plan.md
  - specs/001-code-review-desk/tasks.md
tests:
  - "all 21 findings re-checked by grep after remediation: 21/21 FIXED"
  - "task format: 41/41 well-formed"
  - "unresolved placeholders: none"
---

## Prompt

```
/sp.analyze spec clearly
```

User input read as a directive to weight the ambiguity and underspecification passes, since "spec
clearly" asks about clarity rather than coverage alone.

## Response snapshot

Ran the cross-artifact analysis under the bundled `openai-agents-sdk` skill, which is what made the
pass substantive rather than structural: two of the findings are behaviours of the SDK that the plan
asserted confidently and got wrong, and neither is visible from comparing the three artefacts to
each other. The skill is not in `activate_skill`'s enum — that list is snapshotted at session start,
before it was installed — so it was loaded by reading it directly, which is equivalent.

21 findings: 2 CRITICAL, 5 HIGH, 8 MEDIUM, 5 LOW. Coverage was already 100% (18/18 requirements had
at least one task), so the value lay almost entirely in correctness and clarity rather than gaps.

Both CRITICAL findings were SDK defaults the plan had silently inherited:

- `trace_include_sensitive_data` defaults to **True**, recording prompts and tool I/O. The diff is
  both. Left alone, the trace would carry the credential FR-8 exists to refuse, breaking NFR-1 and
  Principle III — a MUST. Now set to `False`, with the reason recorded in the plan.
- `asyncio.gather` defaults to `return_exceptions=False`, so a reviewer exhausting its per-reviewer
  turn ceiling aborted the group and cancelled the other two, discarding completed work — exactly
  the outcome Principle IV's rationale says must not happen. Now `return_exceptions=True`, with
  per-run `error_handlers` as the first line of defence.

Three structural findings the skill forced out: the ledger's mechanism contradicted the spec's own
vocabulary ("custom runner" versus trace processor); FR-7's run-level override may not work at all
given FR-1 sets the model on the agent, a precedence the SDK docs contradict themselves about; and
the output guardrail had **no host agent**, because a `Report` assembled in Python is not an agent
output and output guardrails only run for the last agent. That last one meant FR-8 was
unimplementable as drawn. Added the Report agent.

Then applied the remediation: rewrote `tasks.md` rather than patching it, so new tasks land in the
correct phases and the cut-order references (T033 / T021+T023 / T031) stay valid. Verified all 21
findings closed by grep, 41/41 tasks well-formed, no unresolved placeholders, zero `.py` files
tracked so the Phase 0 gate still holds. Committed as `911d3a6`, pushed to both `master` and
`001-code-review-desk`.

## Outcome

- ✅ Impact: FR-8 went from unimplementable to implementable, one MUST-principle violation closed, and FR-7 marked specified-but-undemonstrated rather than assumed working
- 🧪 Tests: 21/21 findings verified fixed by grep; 41/41 tasks match the required format; no unresolved placeholders; Phase 0 gate intact
- 📁 Files: `spec.md` (clarity, vocabulary, two recorded disagreements), `plan.md` (guardrail host agent, trace sensitivity, gather isolation, FR-7 risk), `tasks.md` (rewritten, 41 tasks)
- 🔁 Next prompts: `/sp.implement` to begin at T001, or `/sp.checklist` for a domain-specific requirements checklist
- 🧠 Reflection: Running the analysis with the SDK reference loaded changed its character. Comparing three documents against each other finds vocabulary drift and coverage holes; it cannot find a wrong claim about a library — and both CRITICAL findings were exactly that. Checking a mechanism against its documentation, not only against the spec, is what turned this from a tidy report into a useful one.

## Evaluation notes (flywheel)

- Failure modes observed: Two. First, shell quoting — backticks inside grep patterns terminated the
  command and produced a spurious verification failure; re-run without backticks, 21/21 passed.
  Second, a real false negative: the M4 check searched for wording ("one row per reviewer that ran")
  that exists only in the plan and tasks, where the spec's equivalent fix reads "one row per
  reviewer — three on the normal path". A verification grep is only as good as its pattern, so a
  MISSING verdict should be confirmed by searching for the fix rather than reported as a failure.
- Graders run and results (PASS/FAIL): Constitution alignment PASS after remediation (C1/C2 closed). Coverage PASS (18/18, unchanged). Ambiguity PASS (numeric bound now in FR-5 and SC-002). Duplication PASS (L1/L2 resolved). Task-format validation PASS 41/41. Provenance PASS.
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Load the relevant domain skill *before* the analysis pass
  rather than after. Both CRITICAL findings came from the SDK reference and would have surfaced
  earlier had the skill been opened when `plan.md` was written — the cheaper fix is to cite the
  mechanism's documentation in the plan, at the point of the claim.
