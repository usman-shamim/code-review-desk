# Phase 1 Data Model: Code Review Desk

**Feature**: `001-code-review-desk` | **Date**: 2026-09-25
**Source**: entities extracted from `spec.md` (Key Entities), with validation rules traced to the
requirement that demands them.

---

## Entity: ReviewContext

The per-run facts every reviewer works under. Travels in the run context; never appears in prompt
text (FR-2).

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `repo` | `str` | yes | Non-empty. MUST NOT appear in any prompt string (SC-010). |
| `language` | `str` | yes | Non-empty; used to assemble per-run instructions (FR-4). |
| `ruleset_id` | `str` | yes | Non-empty; MUST resolve to a readable ruleset, and a missing one must degrade to a sentence rather than an exception (FR-9, SC-006). |
| `strictness` | `str` | no (default `"normal"`) | Exactly one of `"normal"` or `"strict"`. Any other value is a programming error, not user input. `"strict"` yields terser instructions (FR-4). |

**Relationships**: Passed to every reviewer run and read by `read_ruleset` and `read_diff_chunk`.
Held in interface session state so a second diff reuses it (FR-12).

**Lifecycle**: Constructed once per review by the operator/interface → carried through every run
in that review → retained in session state after the report is produced.

---

## Entity: DiffChunk

One file's worth of a unified diff. Produced by the split, consumed by exactly one reviewer pass
(FR-1).

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `path` | `str` | yes | The file path the chunk touches, taken from the diff header. |
| `text` | `str` | yes | The hunks for that file. A deletion with no added lines is still a valid chunk. |

**Relationships**: Belongs to exactly one review; may be read by all three reviewers.

**Invariants**:
- The number of chunks equals the number of distinct file headers in the diff — a two-file diff
  produces exactly two chunks (SC-001).
- Binary content MUST NOT be presented as reviewable text.
- The split completes before any model call is made (FR-1).

**Failure behaviour**: An empty or malformed diff produces no chunks and one readable message; the
malformed input is not passed downstream (FR-1).

---

## Entity: Finding

One review observation. The unit reviewers return and the report is built from (FR-3).

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `file` | `str` | yes | The path the finding refers to. |
| `line` | `int` | yes | A line number. |
| `severity` | `Literal["critical","major","minor"]` | yes | Constrained to these three values by the type, which is what makes the generated schema strict. |
| `message` | `str` | yes | Human-readable. MUST NOT contain credential-shaped text — enforced downstream by the guardrail (FR-8). |

**Relationships**: Produced by one of the three reviewers → collected into a list → deduplicated
and ordered by the Merge specialist → included in the Report.

**Collection shape**: A reviewer's declared output type is `list[Finding]`. Strict schemas require
an object at the root, so the generated schema wraps the list in an object with a single
`response` key; `final_output` is nevertheless a plain Python list, iterable and countable
(SC-003).

**Deduplication rule**: Findings from different reviewers describing the same `file` and `line`
collapse to one, keeping the highest severity of the group (spec Edge Cases).

---

## Entity: ReviewerStat

One reviewer's measured cost, for the report footer (FR-10).

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `agent` | `str` | yes | The reviewer's name. |
| `ms` | `int` | yes | Wall-clock duration in milliseconds, measured by the run hooks — not estimated. |
| `tokens` | `int` | yes | Token count read from the run context's usage, not estimated (FR-10). |

**Relationships**: One per reviewer → collected into `Report.footer`. Exactly three rows for a
complete review; fewer when a review is partial.

---

## Entity: Report

The artifact the guardrail inspects and the interface displays (FR-8, FR-12).

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `findings` | `list[Finding]` | yes | Ordered by severity. MAY be empty — zero findings is a valid result, not a failure (spec Edge Cases). |
| `footer` | `list[ReviewerStat]` | yes | One row per reviewer that ran. |
| `partial` | `bool` | yes | `true` when a turn ceiling terminated the review; the ceiling is named in the accompanying message (FR-9). |

**State transitions**:

```text
assembled ──> guardrail passes ──> delivered to interface
          └─> guardrail trips ────> refused; operator told; no report emitted
```

**Invariants**:
- A report MUST NOT reach the operator while containing credential-shaped text (FR-8).
- The report carries no secret and nothing shaped like one (NFR-1, SC-004).

---

## Entity: LedgerEntry

One line per completed run, appended to `ledger.jsonl` (FR-11).

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `ts` | ISO-8601 `str` | yes | Timestamp of the run. |
| `request_id` | `str` | yes | Identifier correlating runs belonging to one review. |
| `agent` | `str` | yes | The agent whose run completed. |
| `ms` | `int` | yes | Duration in milliseconds. |
| `findings` | `int` | yes | Count of findings produced, `0` where the run produces none. |

**Explicitly excluded**: diff content, finding text, any credential. The ledger carries metadata
only (NFR-1, SC-009, spec non-goal 3).

**Cardinality**: One line per completed run. A three-file review therefore produces **more** than
three lines — three reviewers plus the merge specialist, any remediation handoff, and the
guardrail's own check. This is expected behaviour and is documented in `plan.md`.

---

## Entity: Agent configuration (base reviewer and specialists)

Not persisted; described here because the shared/own split is a graded question.

| Agent | Shares with base | Its own |
|-------|------------------|---------|
| Base reviewer | — | Instructions, `gpt-5-nano`, tools, model settings |
| Security reviewer | Tools, structure, model | Instructions tuned to credential handling and unsafe input; strict model settings |
| Tests reviewer | Tools, structure, model | Instructions tuned to untested paths and assertions that cannot fail; strict model settings |
| Style reviewer | Tools, structure, model | Instructions tuned to readability and consistency; `normal` strictness |
| Merge specialist | Structure | Instructions for dedup and severity ordering; reached as a tool |
| Remediation specialist | Structure | Instructions for proposing a patch; reached by handoff |

---

## Validation summary (requirement traceability)

| Rule | Requirement |
|------|-------------|
| Context never in prompt text | FR-2, SC-010 |
| Two-file diff → two chunks, before any model call | FR-1, SC-001 |
| Findings typed, list returned as a plain list | FR-3, SC-003 |
| Missing ruleset degrades to a sentence | FR-9, SC-006 |
| Report refused when credential-shaped text is present | FR-8, SC-004 |
| Footer token counts read, not estimated | FR-10 |
| Ledger holds metadata only | FR-11, SC-009 |
| Missing key fails at startup with one sentence | NFR-1, SC-005 |
