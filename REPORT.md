# Code Review Desk — build report

**Date**: 2026-09-25 · **Branch**: `001-code-review-desk`

This file records what is actually verified, how, and what is not — so the viva asks about
behaviour rather than about claims.

---

## Status

```
uv run pytest -q     →  126 passed
uv run ruff check .  →  All checks passed
```

| Metric | Value |
|---|---|
| Pipeline source | 1,403 lines across `src/desk/` |
| Tests | 1,154 lines across `tests/` |
| Tests passing | 126 / 126 |
| Lint | clean (`ruff`, `E F I UP B`) |
| Python | 3.12.14 (uv-managed), `requires-python >= 3.11` |
| SDK | `openai-agents` 0.22.3 |

---

## The provenance gate (NFR-5)

```
c880614  Initial commit from Specify template
57b8704  chore: stop tracking agent tooling and the assignment brief
ee8a8a2  spec: add the four Phase 0 artifacts for the Code Review Desk
a9994ef  spec: name the API key variable and complete NFR traceability
911d3a6  spec: remediation pass from /sp.analyze
e514d62  docs: record the /sp.analyze pass as a prompt history record
         ← all implementation commits come after this line
```

`.py` files in the Phase 0 commit `ee8a8a2`: **0**. The four artifacts were committed before
any source file existed, which is what the gate checks.

---

## What is verified without an API key

Everything below was run on this machine with `OPENAI_API_KEY` unset.

| Requirement | Command | Observed |
|---|---|---|
| FR-1 | `desk-review samples/two-file.diff --dry-run-split` | `2 chunk(s)`, one per file, before any model call |
| FR-1 | `desk-review samples/three-file.diff --dry-run-split` | `3 chunk(s)` |
| FR-1 | `desk-review samples/empty.diff --dry-run-split` | `No reviewable files found in that diff.` exit 2, no traceback |
| FR-1 | `desk-review samples/malformed.diff --dry-run-split` | same message, exit 2 |
| FR-2 | `desk-review … --print-schema` / `--print-prompt` | `ctx` absent from the tool schema; no repository name in the prompt |
| FR-3 | `desk-review … --print-schema` | list root wrapped in an object with a single `response` key |
| FR-4 | `--print-prompt` and `--print-prompt --strictness strict` | two visibly different prompts; strict is shorter |
| FR-5 | `tests/test_run_config.py::test_gather_does_not_abort_the_group` | `return_exceptions=True` present |
| FR-6 | `tests/test_agent_wiring.py` | merge exposed as a tool; remediation only as a handoff when a critical exists |
| FR-8 | `tests/test_guardrail.py` | planted key refused; clean report passes; **the refusal never echoes the credential** |
| FR-9 | `tests/test_agent_wiring.py` | missing ruleset → sentence; unreadable chunk → sentence via the error handler |
| FR-10 | `tests/test_hooks.py` | one footer row per reviewer that ran; tokens read, not estimated |
| FR-11 | `tests/test_ledger.py` | one line per run; line keys are exactly the metadata set; no diff or finding text |
| FR-13 | `tests/test_run_config.py` | `trace_include_sensitive_data is False` |
| NFR-1 | `env -u OPENAI_API_KEY desk-review samples/two-file.diff` | one sentence, exit 1, no traceback |
| NFR-2 | `tests/test_agent_wiring.py` | every agent, including both specialists, declares `model` and `model_settings` |

---

## What requires an API key, and is therefore NOT yet proven live

This is stated plainly because an unchecked claim is worse than a known gap.

Every reviewer test above is **structural or unit-level**. The following require live model
calls and have not been exercised on this machine, because no key is present:

1. **FR-5's two wall clocks.** Both paths exist and run (`--timing concurrent` uses
   `asyncio.gather`; `--timing sequential` awaits in a loop; `--timing both` prints the pair
   and the ratio), but the actual milliseconds have not been measured. The SC-002 thresholds —
   concurrent within **1.5x** the slowest reviewer, below **60%** of the sequential total — are
   written into the spec and asserted by `tests/test_concurrency.py`'s expectations, and will
   be checked by:

   ```bash
   uv run desk-review samples/three-file.diff --timing both --show-footer
   ```

2. **FR-7's precedence.** Whether `RunConfig(model=...)` beats the agent's own `model` is
   genuinely undetermined — the SDK's documentation contradicts itself, and the safe strategy
   (leave `model` unset) is what FR-1 and Principle II forbid. `tests/test_run_config.py` checks
   the wiring, not the outcome. Settle it with an empirical run before claiming FR-7.

3. **FR-8's live trip.** The guardrail logic is fully tested, but that the tripwire fires
   *inside a real run* and is caught by `pipeline.py` has not been observed. The predicate is
   `except OutputGuardrailTripwireTriggered` in `pipeline._assemble`.

4. **FR-10's footer, FR-11's live ledger, FR-13's trace.** The mechanisms are tested in
   isolation. The live run has not produced a footer, a `ledger.jsonl` line, or a trace,
   because tracing is inert without a key.

**The single command that closes all four**: create `.env` from `.env.example`, add a key, then

```bash
uv run desk-review samples/planted-key.diff --timing both --show-footer
uv run desk-review samples/two-file.diff --show-footer
cat ledger.jsonl
```

---

## Decisions recorded

**Turn ceiling: 8 turns per reviewer.** The necessary work is three turns — one forced tool
call, at least one chunk read, one structured finding pass — so 8 leaves room for one re-read
and one retry without ever approaching the ceiling in normal operation, while still terminating
a reviewer that loops on a tool. `tool_choice` resets to `"auto"` after the first call, so the
forced call cannot itself *cause* a loop.

**`tool_choice` is `"required"`, not the ruleset tool's name.** `ModelSettings` rejects a
tool-choice object, and a bare tool-name string is not a documented Responses value. `"required"`
forces a tool call on the turn it applies to, and the security reviewer's instructions name
`read_ruleset` as the tool to call. This is weaker than "the model can only call this one tool"
and is recorded here rather than glossed over.

**The ledger holds more lines than there are reviewers.** One line per completed run: three
reviewers, the Desk, and any handoff. That is the answer to the question about unexpected
ledger lines.

**Sensitive tracing is off, deliberately.** The SDK's `trace_include_sensitive_data` defaults to
`True`, recording prompts and tool I/O. The diff is both. Left at the default, the trace would
carry the very credential FR-8 refuses. This was one of two findings from the `/sp.analyze` pass
that would otherwise have shipped a broken MUST.

**`asyncio.gather(..., return_exceptions=True)`.** With the default `False`, one reviewer hitting
its ceiling would abort the group and cancel the other two, discarding completed work — the
outcome constitution Principle IV exists to prevent.

---

## Viva answers, grounded in the code

1. **What made the concurrency difference?** `asyncio.gather` schedules all three reviewer
   coroutines before awaiting any; the sequential variant awaits each in turn. Same agents, same
   work, one difference in scheduling — `pipeline.review(parallel=...)`.
2. **What shape does the model emit, and why not a list?** `{"response": [ … ]}`. A strict schema
   needs an object at the root, so the SDK wraps the list; `final_output` is still a plain list.
   `--print-schema` shows the wrapper.
3. **Shared vs own across the three reviewers?** Shared: the tools (the same list object, because
   `clone()` is a shallow copy) and the structure. Own: instructions and model settings.
   `tests/test_agent_wiring.py::test_reviewers_are_clones_sharing_the_same_tool_objects`.
4. **Why merge as a tool and remediation as a handoff?** Merging returns a value the Desk keeps
   working with, so the conversation must stay put; remediation hands the operator a different
   job. Swapping them leaves the Desk unable to assemble its own report. `spec.md` Assumptions.
5. **When the guardrail fired, what had been paid for?** Everything. Output guardrails run on the
   finished output, so the model spend had already happened — the refusal prevents disclosure,
   not cost.
6. **Where do the footer's token numbers come from?** `context.usage.total_tokens` in
   `TimingHooks.on_agent_end` — measured, never estimated (`tests/test_hooks.py`).
7. **Why does the ledger have extra lines?** One per completed run, and a review runs the three
   reviewers *and* the Desk (and any handoff) — see `plan.md`.
8. **What stops a reviewer looping on a tool?** The 8-turn ceiling, caught by an error handler
   and reported as a partial review; plus `tool_choice` resetting to `"auto"` after the first
   call, so the forced call cannot start a loop.
