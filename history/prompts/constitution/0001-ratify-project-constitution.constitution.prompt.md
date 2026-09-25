---
id: 0001
title: Ratify project constitution
stage: constitution
date: 2026-09-25
surface: opencode
model: unspecified
feature: none
branch: master
user: usman
command: sp.constitution
labels: [constitution, governance, phase-0]
links:
  spec: .specify/memory/constitution.md
  ticket: none
  adr: none
  pr: none
files:
  - .specify/memory/constitution.md
tests:
  - "placeholder-token scan: grep -nE '\\[[A-Z_0-9]{3,}\\]' -> no matches"
---

## Prompt

```
/goal complete the specs using speckit plus
```

Follow-up in the same turn, after the framing question about which provider the specs should
target:

```
also make sure to use dot_env for giving agent the api key for openai
```

And the provider decision, given the assignment brief names `gemini-2.5-flash` while the operator
holds only an OpenAI credential:

```
OpenAI gpt-5-nano
```

## Response snapshot

Replaced the raw Spec Kit constitution template with a ratified 1.0.0 document. Six principles:
I. Specification Before Implementation (NON-NEGOTIABLE), II. Model Configured On The Agent,
III. Secrets Stay In .env, IV. Tools Return Sentences Never Raise, V. A Review Is Reproducible From
The Diff, VI. Concurrency And Guardrails Are Load-Bearing (NON-NEGOTIABLE). Added Additional
Constraints (provider and the level configured, cost, observability, runtime), Development Workflow
(requirement discipline, the cut order, quality gates) and Governance (amendment procedure,
semver policy, compliance review). Prepended a Sync Impact Report recording the version change,
the six placeholder-to-title mappings, the added sections and the template-consistency checklist.

Two deviations worth recording: the brief's `gemini-2.5-flash` is superseded by OpenAI
`gpt-5-nano` by explicit operator decision, and the constitution's stated provider therefore
differs from the brief. That disagreement is carried forward into `spec.md` Assumptions rather
than resolved silently, per Principle I's governance rules. Also recorded: the constitution
command instructs reading `.specify/templates/commands/*.md`, which does not exist in this
checkout — the slash commands live in `.opencode/command/` and are gitignored by project choice.
The Sync Impact Report flags that gap so it is not mistaken for a missed update.

## Outcome

- ✅ Impact: Phase 0 artifact 1 of 4 ratified; every later decision now has a written rule to be checked against
- 🧪 Tests: Placeholder-token scan returns no matches; heading hierarchy matches the template exactly (`# X Constitution`, `## Core Principles`, six `###` principles, `## Additional Constraints`, `## Development Workflow`, `## Governance`)
- 📁 Files: `.specify/memory/constitution.md` (template → ratified 1.0.0)
- 🔁 Next prompts: `/sp.specify` to turn the brief's requirements into behaviour; `/sp.plan` for the architecture
- 🧠 Reflection: The brief's Phase 0 gate names four artifacts, so the constitution is not free-standing documentation — it is the source the plan's Constitution Check is graded against. Writing the six principles as testable gates, rather than as aspirations, is what made the plan's check table fillable without invention.

## Evaluation notes (flywheel)

- Failure modes observed: The first pass left six bracketed placeholder names inside the Sync Impact Report while documenting the rename, which a literal token scan flags as unfilled. Rewritten as "Template slot N (was X)" so the change history is preserved without tripping the validator.
- Graders run and results (PASS/FAIL): Placeholder scan PASS. Heading-level match PASS. Section coverage against the brief's "at minimum" list (provider and level, secrets only in .env, no tool raises into the runner, reproducible from the diff) PASS.
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Have the constitution command emit its Sync Impact Report with the previous values quoted in backticks rather than brackets by default, so the author does not have to remember to de-bracket them.
