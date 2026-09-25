# Quickstart & Viva Walkthrough: Code Review Desk

**Feature**: `001-code-review-desk` | **Date**: 2026-09-25

Two audiences: the operator who wants to run a review, and the reviewer who wants to see each
numbered requirement demonstrated. The second is the point — every requirement below is
reproducible on demand.

---

## Prerequisites

- Python 3.11+
- `uv` for environment management
- An OpenAI API key

## Setup

```bash
uv sync                                   # create the environment, install dependencies
cp .env.example .env                      # then put your key in .env
```

`.env` is gitignored. It holds exactly:

```bash
OPENAI_API_KEY=sk-...
```

**Demonstrating NFR-1 / SC-005 — a missing key fails cleanly.** Run the entry point with the
variable absent:

```bash
env -u OPENAI_API_KEY uv run desk-review samples/two-file.diff
```

Expected: one sentence on stderr and a non-zero exit status, with no traceback:

```text
Missing env var(s): OPENAI_API_KEY. Copy .env.example to .env and fill it in.
```

---

## Running a review

```bash
uv run desk-review samples/two-file.diff \
    --repo acme/checkout --language python --ruleset python-strict --strictness normal
```

Then start the interface:

```bash
uv run chainlit run app.py
```

---

## Viva walkthrough

Each block names the requirement, the command, and what to look for. These are the same checks the
brief's definition-of-done table lists.

### 1. Spec preceded code — NFR-5, SC-001 (provenance)

```bash
git log --oneline --reverse
```

The four Phase 0 artifacts appear before any `src/` file. The Phase 0 commit contains no source
file; adding code to it would fail the phase.

### 2. A diff is split before any model call — FR-1

```bash
uv run desk-review samples/two-file.diff --dry-run-split
```

Two files in, two chunks out — printed before any model call is made. Feed an empty file and the
result is one readable message, not a traceback.

### 3. Context never reaches the prompt — FR-2, SC-010

```bash
uv run -m desk.tools --print-schema read_ruleset
grep -r "acme/checkout" src/                 # no hits
```

The printed schema has a `ruleset_id` property and **no `ctx` property**. The repository name
appears nowhere in the prompts.

### 4. Findings are typed and countable — FR-3, SC-003

```bash
uv run desk-review samples/two-file.diff --count-criticals
```

Criticals are counted with a single Python expression over `final_output`. The generated schema
shows the `response` wrapper that a strict object root requires; the returned value is still a
plain list.

### 5. Reviewers differ per run — FR-4

```bash
uv run desk-review samples/two-file.diff --print-prompt
```

Print the resolved prompt for two different contexts and compare: different rulesets and languages
produce visibly different prompts, and `--strictness strict` produces a terser one.

### 6. Concurrency — FR-5, SC-002 (the centrepiece)

```bash
uv run desk-review samples/two-file.diff --timing concurrent
uv run desk-review samples/two-file.diff --timing sequential
```

Two wall-clock numbers, side by side. Concurrent should be close to the **slowest single review**;
sequential should be close to the **sum**. That difference is the requirement.

### 7. Merge is a tool, remediation is a handoff — FR-6

```bash
uv run desk-review samples/duplicate-findings.diff    # merge path fires
uv run desk-review samples/planted-critical.diff      # remediation path fires
```

The two-sentence justification for the asymmetry is in `spec.md` Assumptions.

### 8. A cheaper re-run without edits — FR-7

```bash
uv run desk-review samples/two-file.diff --cheap
git diff --stat src/desk/agents.py             # empty
```

Same reviewer object, two models, and no agent definition changed between runs.

### 9. A planted key is refused — FR-8, SC-004 (the other centrepiece)

```bash
uv run desk-review samples/planted-key.diff
```

Expected: a refusal, not a report.

```text
The report was refused: it contained something shaped like a credential.
```

The catching line is in `src/desk/pipeline.py`. Then run the clean diff and confirm it passes
untouched. Note for the viva: the guardrail runs on the **finished report**, so the model spend has
already happened when the tripwire fires — the guardrail prevents disclosure, not cost.

### 10. Failing tools and the ceiling — FR-9, SC-006

```bash
mv rulesets/python-strict.md /tmp/ && uv run desk-review samples/two-file.diff
mv /tmp/python-strict.md rulesets/
```

The review still finishes with a sensible message. The ceiling is **8 turns**; the reasoning is in
`plan.md` under Decided Numbers, and the answer to "what would stop a tool-calling loop?" is the
ceiling plus `tool_choice` resetting to `"auto"` after the first call.

### 11. Measured tokens, not guessed — FR-10

```bash
uv run desk-review samples/two-file.diff --show-footer
```

Three rows, each with latency and a token count read from the run context.

### 12. The ledger — FR-11, SC-009

```bash
rm -f ledger.jsonl && uv run desk-review samples/three-file.diff
wc -l ledger.jsonl && cat ledger.jsonl
```

More lines than three reviewers — the merge run and the guardrail check also completed. That extra
count is the answer to the viva question about unexpected ledger lines. No line contains diff
content or a credential. Removing the single registration in the entry point switches the ledger
off entirely.

### 13. Streaming — FR-12, SC-008

```bash
uv run chainlit run app.py
```

Paste a diff. Findings appear progressively rather than in one lump. Paste a second diff in the
same session and the context is reused rather than rebuilt. The handler awaits its run.

### 14. One review, one trace — FR-13, SC-007

Open the trace for the review just run. All three reviewers, the merge and any handoff appear as
**one** trace, with the three reviewer spans overlapping in time rather than stacked end to end.
Name the slowest reviewer from the trace.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| One sentence about a missing env var, exit 1 | No key in `.env` | Copy `.env.example` to `.env` and fill it in. This is the intended NFR-1 behaviour, not a bug. |
| Report refused | The diff contained credential-shaped text | Intended (FR-8). Remove the credential from the diff to see the pass path. |
| `Review stopped at the 8-turn ceiling` | A reviewer looped | Intended (FR-9). The partial findings are shown deliberately. |
| Sequential and concurrent timings look the same | Reviews are cached or too fast to distinguish | Use a larger diff, or verify the sequential variant really awaits in a loop. |
| Ledger has more lines than reviewers | The merge and guardrail runs also complete | Expected; see `plan.md`. |
| `No reviewable files found in that diff` | Empty or malformed input | Intended (FR-1). The malformed input is not passed downstream. |
