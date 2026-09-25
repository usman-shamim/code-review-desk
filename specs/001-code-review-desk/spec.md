# Feature Specification: Code Review Desk

**Feature Branch**: `001-code-review-desk`
**Created**: 2026-09-25
**Status**: Approved (Phase 0 baseline — committed before any source file)
**Input**: User description: "A spec-first review pipeline that splits a unified diff by file, runs security, tests and style reviewers concurrently, merges their findings into one typed report, hands off to a remediation agent on critical security findings, streams findings to a Chainlit interface, and refuses to emit any report that quotes a credential."

---

## Overview

The Desk is a review pipeline, not a conversation. A unified diff goes in; the diff is split by
file before any model sees it; three reviewers read the same change at the same time, each tuned
differently; their findings fan back in to one typed report. A critical security finding
transfers the conversation to a remediation specialist that proposes a patch to the operator.
Nothing leaves the Desk quoting a secret it found in the diff.

The distinction that shapes the whole design: this is a **fan-out, fan-in pipeline**. The value
is in the concurrency, and in the guardrail that stands between the report and the operator.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Intake and a typed review of one change (Priority: P1)

An operator points the Desk at a unified diff. The Desk splits it into one chunk per file before
any model is called, hands each chunk the repository rules that apply to it, and returns findings
as typed objects that can be counted and sorted — not as prose.

**Why this priority**: Nothing else can exist without intake and a typed finding. This is the MVP:
a diff goes in, structured findings come out, and the operator can programmatically ask "how many
criticals?". It also establishes the two conventions the rest of the build inherits — context
travels beside the prompt rather than inside it, and instructions are assembled per run.

**Independent Test**: Run the Desk over a two-file diff and assert two chunks were produced
before any model call, that a tool read `ruleset_id` through the run context with no wrapper
parameter in its generated schema, that a repository name appears nowhere in the resolved prompt,
and that critical findings can be counted with one Python expression over the result.

**Acceptance Scenarios**:

1. **Given** a well-formed two-file unified diff, **When** the Desk ingests it, **Then** exactly
   two per-file chunks are produced, and this happens before any model call.
2. **Given** an empty or malformed diff, **When** the Desk ingests it, **Then** the operator sees
   a single readable message and the process exits cleanly, with no traceback.
3. **Given** a review run with a `ReviewContext`, **When** a tool reads `ruleset_id` through the
   run context wrapper, **Then** the tool's generated schema contains no wrapper parameter.
4. **Given** two different run contexts, **When** instructions are resolved, **Then** two visibly
   different prompts are produced, and the resolved prompt can be printed before any model call.

---

### User Story 2 - Three reviewers at once, one merged report (Priority: P2)

Security, tests and style reviewers are configured from one shared base and then run
**concurrently** over the same split diff. A Merge specialist deduplicates and orders their
findings; when a critical security finding exists, a Remediation specialist takes over and
proposes the fix.

**Why this priority**: This is the requirement the project exists to demonstrate. The graded
property is that three reviews complete in roughly the time of the slowest one, not the sum — a
sequential version that merely works does not satisfy it.

**Independent Test**: Time three concurrent reviews and the same three reviews run sequentially,
and show both numbers side by side. Separately, confirm both specialist paths fire on the right
kind of diff, and that the same reviewer object yields one review on its own model and one on a
run-level override with no agent definition edited between them.

**Acceptance Scenarios**:

1. **Given** a diff, **When** the three reviewers are launched, **Then** they are started together
   and awaited as a group, and the concurrent wall clock is close to the slowest single review
   rather than the sum of all three.
2. **Given** findings from three reviewers describing the same underlying problem, **When** the
   Merge specialist runs as a tool call, **Then** duplicates are collapsed, the result is ordered
   by severity, and the Desk retains the conversation.
3. **Given** a diff containing a critical security finding, **When** remediation is triggered,
   **Then** control transfers by handoff and the specialist proposes the patch directly to the
   operator.
4. **Given** an unchanged reviewer object, **When** a review is re-run with a run-level model
   override, **Then** the review uses the override while no agent's own model setting changed.

---

### User Story 3 - A report that cannot leak and cannot hang (Priority: P3)

An output guardrail inspects the finished report and refuses it if it contains anything shaped
like a credential copied out of the diff. The operator is told about the refusal; the program does
not crash. Separately, tools that meet bad input return a sentence the model can use, and every
review runs under a turn ceiling that is caught and reported as a partial review.

**Why this priority**: This is the safety requirement the viva asks about directly. A report that
quotes the secret it found is the specific failure this project exists to prevent, and it is
checked for.

**Independent Test**: Feed a diff containing a fake key and confirm a refusal rather than a
report, with the catching line identifiable; feed a clean diff and confirm it passes untouched.
Then delete the ruleset file and confirm the review still completes with a sensible message.

**Acceptance Scenarios**:

1. **Given** a diff containing a planted credential, **When** the report is finished, **Then** the
   guardrail trips, the operator is told the report was refused, and no report or ledger line
   contains the credential.
2. **Given** a clean diff, **When** the report is finished, **Then** the guardrail passes and the
   report is delivered unchanged.
3. **Given** a tool that cannot read its input, **When** it is called, **Then** it returns a
   sentence the model can act on, and no exception escapes into the runner.
4. **Given** a review that exceeds its turn ceiling, **When** the ceiling is reached, **Then** the
   condition is caught and reported to the operator as a partial review.

---

### User Story 4 - Watching the review happen (Priority: P4)

The operator watches findings appear as they land rather than in one lump at the end. The report
carries a footer with each reviewer's latency and measured token count. Every run appends one line
to a ledger, and the whole review appears as a single trace in which the slowest reviewer can be
named.

**Why this priority**: This is delivery and observability — valuable, and the first place to cut
from when the clock runs short. It changes nothing about the correctness of the review itself.

**Independent Test**: Paste a diff into the interface and observe text appear progressively
before completion; inspect the footer for three rows of token counts read from the run context;
confirm one ledger line per run for a three-file diff; open the trace and confirm the three
reviewer spans overlap in time and the slowest can be named.

**Acceptance Scenarios**:

1. **Given** a review in progress, **When** findings arrive, **Then** they appear in the interface
   progressively rather than only on completion.
2. **Given** a second diff pasted into the same session, **When** it is reviewed, **Then** the
   existing context is reused rather than rebuilt.
3. **Given** a completed review, **When** the footer is read, **Then** it shows one row per
   reviewer with latency and token counts taken from the run context, not estimated.
4. **Given** a completed review, **When** the trace is opened, **Then** all three reviewers, the
   merge and any handoff appear as one trace with overlapping reviewer spans.
5. **Given** a three-file diff review, **When** the ledger is read, **Then** it contains one line
   per run — and removing the registration is the only change needed to switch the ledger off.

---

### Edge Cases

- **Empty diff** — reported as a single readable message; no model call, no traceback.
- **Malformed diff** — same treatment; the malformed input is not passed downstream.
- **Binary or deleted files in the diff** — the split must not attempt to treat binary content as
  reviewable text, and a deletion with no added lines must still produce a valid chunk.
- **A diff whose only change is whitespace** — may legitimately yield zero findings; this is not
  an error and must not be reported as a failure.
- **All three reviewers flag the same line** — the Merge specialist collapses it to one finding,
  and the surviving severity is the highest of the group.
- **A chunk that yields no findings** — treated as a valid result, not a missing result.
- **Missing ruleset file at review time** — the review still completes with a sensible message.
- **Missing API key at startup** — one sentence on stderr and a non-zero exit; no traceback, and
  no partially started interface.
- **Credential-shaped text in the diff** — refused by the guardrail; the credential must not
  appear in the report, the ledger, the trace, or the interface.
- **Turn ceiling reached mid-review** — reported as a partial review naming the ceiling, rather
  than surfacing as an unhandled error.
- **A reviewer that loops on a tool** — bounded by the turn ceiling; the review terminates.
- **Interface handler invoked while a review is already running in the same session** — session
  state must remain coherent and the in-flight review must not be corrupted.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-1 — A diff goes in, split by file.** The Desk MUST read a unified diff from a path given on
  the command line and split it into per-file chunks **before any model sees it**. The reviewer
  model MUST be OpenAI `gpt-5-nano`, configured on the agent itself. The entry point MUST be
  asynchronous. Credentials MUST be read from the repository-root `.env` file.
  **Done when**: a two-file diff produces two chunks; an empty or malformed diff is reported as a
  message, not a traceback; nothing in the code sets a global default client.

- **FR-2 — Repository rules live in context.** A `ReviewContext` MUST be passed to every run and
  read by tools through the run context wrapper. It MUST NOT appear in prompt text. The context
  carries at least `repo`, `language`, `ruleset_id`, and a `strictness` of `normal` or `strict`.
  **Done when**: a tool reads `ruleset_id` through the wrapper; the generated schema for that tool
  has no wrapper parameter; grepping the prompts finds no repository name.

- **FR-3 — Findings come back as a list of typed objects.** A reviewer MUST return a list of typed
  findings, not prose. Each finding carries `file`, `line`, a `severity` of `critical`, `major` or
  `minor`, and a `message`. The agent's declared output type MUST be a list of that model, and the
  returned value MUST be a plain Python list.
  **Done when**: the returned value can be iterated and its criticals counted with a single Python
  expression, and the wrapper object that the generated schema needs can be pointed at and
  explained.

- **FR-4 — Reviewer instructions are built per run.** The reviewer's system prompt MUST be
  assembled at request time from the ruleset and the language held in context, and MUST become
  terser when strictness is `strict`.
  **Done when**: two contexts produce two visibly different prompts, and the resolved prompt can
  be printed before any model call.

- **FR-5 — Three reviewers, cloned, running concurrently (never cut).** Security, tests and style
  reviewers MUST be configured from one shared base reviewer, differing in instructions and model
  settings, and MUST run concurrently over the same diff — started together and awaited as a group.
  **Done when**: the concurrent wall clock for the three reviews is close to the slowest single
  review rather than the sum of the three, and both numbers can be shown. A sequential version
  that merely works does not satisfy this requirement.

- **FR-6 — Merge as a tool, remediation by handoff.** A Merge specialist MUST be exposed to the
  Desk as a tool call: it deduplicates overlapping findings and orders them by severity, and the
  Desk retains the conversation. A Remediation specialist MUST be reached by handoff: it takes
  over when a critical security finding exists and proposes the patch directly to the operator.
  **Done when**: both paths fire on the right kind of diff, and this specification's Assumptions
  section argues in two sentences why merging is a tool call and remediation is a transfer.

- **FR-7 — A cheaper second opinion, configured at the run level.** The Desk MUST be able to
  re-run a review on an alternate model without touching any agent definition; the override
  happens on the run.
  **Done when**: the same reviewer object produces one review on its own model and one on the
  override, and no agent's own model setting changed between them.

- **FR-8 — Nothing leaks: an output guardrail (never cut).** An output guardrail MUST inspect the
  finished report and refuse it if it contains anything shaped like a credential — an API key,
  token or password copied out of the diff. The program MUST catch the refusal and report it, and
  MUST NOT crash.
  **Done when**: a diff containing a fake key produces a refusal rather than a report, a clean
  diff passes untouched, and the line that caught the refusal can be pointed at.

- **FR-9 — Required tools, failing tools, and a ceiling.** All three controls MUST be present: the
  reviewer that must consult the ruleset is configured so the model has no choice but to call it;
  diff-reading tools hand their failures to a dedicated error handler rather than raising; and
  every review runs under a turn ceiling that is caught and reported as a partial review.
  **Done when**: deleting the ruleset file produces a review that still finishes with a sensible
  message, and the chosen ceiling can be stated along with the reasoning behind the number.

- **FR-10 — Latency and tokens per reviewer.** Run-level hooks MUST record, for each reviewer, how
  long it took and how many tokens it used, and the report MUST carry those numbers in a footer.
  Agent-level hooks MUST be attached to exactly one reviewer.
  **Done when**: the footer shows three rows with token counts read from the run context rather
  than estimated, and the difference between what agent-level hooks see and what run-level hooks
  see can be explained.

- **FR-11 — Every run lands in a ledger.** A custom runner MUST append one line per run to
  `ledger.jsonl`, registered once at startup. No agent definition may mention the ledger. Each
  line carries a timestamp, a request identifier, the agent name, a duration in milliseconds, and
  a finding count — and no diff content, finding text, or credential.
  **Done when**: one review of a three-file diff produces one ledger line per run, and removing
  the registration is the only change needed to switch the ledger off.

- **FR-12 — Findings stream into the interface.** An interface page MUST accept a pasted diff and
  show findings as they arrive rather than after everything finishes. Session state MUST hold the
  run context and the last report. The handler MUST await its run rather than calling a synchronous
  variant.
  **Done when**: text appears progressively during a review, a second diff in the same session
  reuses the existing context, and the handler awaits rather than blocks.

- **FR-13 — One review, one trace.** Tracing MUST be enabled and exported under the project's own
  key. A whole review — all three reviewers, the merge, and any handoff — MUST appear as one trace.
  **Done when**: the trace can be opened, the three reviewers are seen overlapping in time rather
  than stacked end to end, and the slowest one can be named.

### Explicit Non-Goals (the three things this Desk will not do)

1. **It will not modify the repository under review.** Remediation *proposes* a patch to the
   operator; nothing applies it, and no file in the reviewed repository is written. The Desk is
   read-only with respect to the code it reviews.
2. **It will not execute, build, or test the code being reviewed.** The diff is treated as text to
   be read. No sandbox, no subprocess, and no test runner is invoked against the reviewed code,
   which is also why no finding may claim that a test passed or failed.
3. **It will not store review content.** There is no review history, no cross-session report
   persistence, and no comparison against a previous review. The ledger is an append-only
   operational log of run metadata only, and session state lives only as long as the session.

### Non-Functional Requirements

- **NFR-1 — Secrets.** The OpenAI API key MUST be read from a `.env` file at the repository root
  that is gitignored, loaded at startup before anything else runs. A missing key MUST fail at
  startup with one sentence on stderr and a non-zero exit status, never a traceback. No secret —
  and nothing shaped like one — may ever be written to the ledger, the report, the trace, or the
  interface. A committed `.env.example` MUST name every required variable without carrying values.
- **NFR-2 — Cost.** Every agent MUST declare its own model settings. There MUST be no unbounded
  generation anywhere: turn ceilings and explicit settings bound every execution.
- **NFR-3 — Observability.** Every review MUST be traceable and every run MUST be recorded in the
  ledger.
- **NFR-4 — Failure.** A tool that meets bad input MUST return a sentence the model can use. A
  tool that raises into the runner is a defect.
- **NFR-5 — Provenance.** `git log` MUST show the four Phase 0 artifacts committed before the
  first code commit. This is checked.

### Key Entities

- **ReviewContext** — the per-run facts the reviewers work under: the repository name, the
  language, the identifier of the ruleset to apply, and a strictness of `normal` or `strict`. It
  travels beside the prompt and is read by tools, never pasted into prompt text.
- **DiffChunk** — one file's worth of a unified diff: the path it touches and that file's hunks.
  Produced by the split, consumed by exactly one reviewer pass.
- **Finding** — one review observation: the file, the line, a severity of `critical`, `major` or
  `minor`, and a human-readable message. The unit reviewers return and the report is built from.
- **Report** — the merged, severity-ordered, deduplicated set of findings for a diff, plus the
  per-reviewer footer of latency and measured tokens. The artifact the guardrail inspects.
- **LedgerEntry** — one line per run: timestamp, request identifier, agent name, duration in
  milliseconds, finding count. Contains no review content.
- **Base reviewer and derived reviewers** — one shared base definition of instructions, tools and
  settings, from which the security, tests and style reviewers are derived by differing in
  instructions and model settings. The clone, not the base, is what runs.
- **Merge specialist** — a specialist the Desk calls as a tool to reconcile three sets of findings
  into one ordered set.
- **Remediation specialist** — a specialist that the Desk hands control to when a critical
  security finding exists, and which proposes a patch to the operator.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A two-file diff yields exactly two chunks, and this is observable before any model
  call.
- **SC-002**: Three concurrent reviews complete in wall-clock time close to the slowest single
  review, demonstrably not the sum of the three, with both numbers available on demand.
- **SC-003**: Critical findings are countable with a single Python expression over the review
  result.
- **SC-004**: A diff containing a planted credential yields a refusal, and that credential appears
  in no report, ledger line, trace, or interface text.
- **SC-005**: With the API key absent, the program exits non-zero with exactly one explanatory
  sentence and no traceback.
- **SC-006**: With the ruleset file deleted, a review still completes and reports a sensible
  message rather than failing.
- **SC-007**: One review appears as exactly one trace, with the three reviewer spans overlapping in
  time, and the slowest reviewer identifiable from it.
- **SC-008**: Findings become visible in the interface before the review completes, rather than all
  at the end.
- **SC-009**: A review of a three-file diff appends exactly one ledger line per run, and no ledger
  line contains any part of the diff or any credential.
- **SC-010**: Zero repository names, ruleset identifiers or other run context values appear in any
  prompt sent to a model.

---

## Assumptions

- **Provider deviation from the brief.** The assignment brief names `gemini-2.5-flash` for FR-1.
  This build targets OpenAI `gpt-5-nano` by explicit operator decision, because that is the
  credential available. The property actually being graded in FR-1 is *where* the model is
  configured — on the agent itself — and the contrasting property in FR-7 is configuration at the
  run level. Both are preserved exactly; only the vendor name differs. This is the one recorded
  disagreement between the brief and this specification, per the constitution's governance rule.
- **Merge is a tool call, remediation is a handoff.** Merging is a sub-task that returns a value
  the Desk must keep working with — merged findings feed the report and the footer — so it must be
  a call the Desk makes and returns from, with the conversation staying put. Remediation is a
  change of ownership: a critical security finding means the operator now needs a patch proposed to
  them, which is a different job with a different voice, so control transfers. Swapping them would
  leave the Desk unable to assemble its own report and would strand remediation as a call that can
  never propose anything.
- **Turn ceiling.** Reviews run under a bounded number of turns, chosen small enough that a
  reviewer looping on a tool cannot run away with the budget, and large enough to allow a ruleset
  lookup followed by a finding pass. The specific number and its reasoning are recorded in the
  plan.
- **Ledger placement.** The ledger is written to the repository root as `ledger.jsonl` and is
  gitignored, so run history never becomes a committed artifact.
- **Credential detection is shape-based.** The guardrail recognises credential-shaped strings
  rather than verifying them against any provider, so a planted fake key is refused exactly as a
  real one would be, and no network call is made to decide.
- **Interface is a local single-operator page.** There is no authentication, no multi-tenancy, and
  no notion of who the operator is; intake is a pasted diff or a path, and the run context is
  supplied with it.
- **The reviewed repository need not exist locally.** Because the Desk treats the diff as text and
  never executes the reviewed code, a diff alone is sufficient input.
