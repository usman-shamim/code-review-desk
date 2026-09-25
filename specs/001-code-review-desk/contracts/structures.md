# Contract: Boundary Structures

**Feature**: `001-code-review-desk` | **Date**: 2026-09-25

The exact shape of every structure crossing a boundary. Companion to `data-model.md`, which
describes the same entities semantically; this file is the interface-level view.

---

## `Finding` — reviewer output boundary

Declared as the reviewer's structured output type. Mirrored from `spec.md` FR-3.

```python
from typing import Literal
from pydantic import BaseModel

class Finding(BaseModel):
    file: str
    line: int
    severity: Literal["critical", "major", "minor"]
    message: str
```

**Generated schema** — what the model actually emits:

```json
{
  "type": "object",
  "properties": {
    "response": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "file": { "type": "string" },
          "line": { "type": "integer" },
          "severity": { "type": "string", "enum": ["critical", "major", "minor"] },
          "message": { "type": "string" }
        },
        "required": ["file", "line", "severity", "message"],
        "additionalProperties": false
      }
    }
  },
  "required": ["response"],
  "additionalProperties": false
}
```

**The `response` wrapper is required, not incidental.** A list cannot be a root of a strict
schema, so a list root is wrapped in an object with a single `response` key. What arrives in
`final_output` is nevertheless a plain Python list, which is why criticals are countable with one
Python expression:

```python
sum(1 for f in result.final_output if f.severity == "critical")
```

This is the answer to the viva question about the shape the model actually emits and why it is not
a bare list.

---

## `ReviewContext` — operator-to-run boundary

```python
from dataclasses import dataclass

@dataclass
class ReviewContext:
    repo: str
    language: str
    ruleset_id: str
    strictness: str = "normal"   # "normal" or "strict"
```

Crosses into every run as the run context. Read by tools through the wrapper; MUST NOT be
serialised into any prompt. `strictness` selects the terser instruction variant (FR-4).

---

## `ReviewerStat` — hook-to-report boundary

```python
class ReviewerStat(BaseModel):
    agent: str
    ms: int
    tokens: int
```

Produced by the run hooks from the run context's usage, so both numbers are measured rather than
estimated (FR-10).

---

## `Report` — pipeline to guardrail to interface

```python
class Report(BaseModel):
    findings: list[Finding]
    footer: list[ReviewerStat]
    partial: bool
```

This is the object the output guardrail inspects. It crosses the guardrail boundary exactly once,
and a refusal means it does not cross at all.

**Rendered form** (what the operator sees):

```text
3 findings — 1 critical, 1 major, 1 minor

  critical  src/auth.py:42   Hardcoded API key in the diff
  major     src/auth.py:57   Password compared without a constant-time function
  minor     src/util.py:12   Function name does not describe its return value

──────────
security  2140 ms   1841 tokens
tests     1180 ms    902 tokens
style      640 ms    511 tokens
```

---

## `LedgerEntry` — trace processor to `ledger.jsonl`

One JSON object per line:

```json
{"ts": "2026-09-25T19:04:11Z", "request_id": "rev_8f21", "agent": "SecurityReviewer", "ms": 2140, "findings": 3}
```

**MUST NOT contain**: diff content, finding text, or any credential. It is metadata only (FR-11,
NFR-1, SC-009).

**Cardinality**: one line per completed run. A three-file review yields more than three lines —
the three reviewers, the merge specialist, any remediation handoff, and the guardrail check. See
`plan.md`.

---

## Handoff input (remediation boundary)

When remediation is triggered, the Desk states which finding caused it, so the transfer is not
anonymous:

```python
class RemediationInput(BaseModel):
    finding: Finding
    context_summary: str
```

This satisfies the brief's "handoff must state which finding triggered it" and keeps the
`handoff` distinct from a `tool call`, which would have to return a value and would leave the
Desk holding the conversation.

---

## Error sentence contract

Every user-facing or model-facing failure is a single sentence, never a traceback (NFR-1, NFR-4):

| Condition | Message shape |
|-----------|---------------|
| Missing API key at startup | `"Missing env var(s): OPENAI_API_KEY. Copy .env.example to .env and fill it in."` — then exit non-zero. |
| Empty or malformed diff | `"No reviewable files found in that diff."` |
| Unreadable ruleset | `"No ruleset is available for this identifier. Review without it and say so."` |
| Unreadable diff chunk | `"That file could not be read from the diff. Try another path, or continue without it."` |
| Guardrail refusal | `"The report was refused: it contained something shaped like a credential."` |
| Turn ceiling reached | `"Review stopped at the 8-turn ceiling. Findings so far are shown as partial."` |
