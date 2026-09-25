# Contract: Tools

**Feature**: `001-code-review-desk` | **Date**: 2026-09-25

Every tool a reviewer or the Desk can call, with the exact signature, the argument schema the model
sees, the return shape, and the failure behaviour. These are function-tool contracts, not HTTP
endpoints — the pipeline has no network boundary.

**The `ctx` parameter never appears in the model-visible schema.** Declaring
`ctx: RunContextWrapper[ReviewContext]` as the first parameter injects the run context and excludes
it from the generated schema. That exclusion is FR-2's mechanism, and asserting it is part of
FR-2's acceptance.

---

## `read_ruleset`

Reads the repository rules a reviewer must apply. This is the tool the model is forced to call.

**Signature**

```python
@function_tool(tool_input_guardrails=None)
def read_ruleset(
    ctx: RunContextWrapper[ReviewContext],
    ruleset_id: Annotated[str, "Identifier of the ruleset to read"],
) -> str: ...
```

**Model-visible argument schema**

```json
{
  "type": "object",
  "properties": {
    "ruleset_id": { "type": "string", "description": "Identifier of the ruleset to read" }
  },
  "required": ["ruleset_id"],
  "additionalProperties": false
}
```

Note the absence of `ctx`. This is the artifact the FR-2 check points at.

**Returns**: the ruleset text as a string on success.

**Failure behaviour (FR-9, NFR-4)**: a missing or unreadable ruleset returns a sentence the model
can act on — for example `"No ruleset is available for this identifier. Review without it and say
so."` It does **not** raise. The review therefore still completes (SC-006).

**Interaction with the context**: the tool reads `ruleset_id` through `ctx.context`, confirming
the value arrived via the run context rather than through prompt text.

---

## `read_diff_chunk`

Reads one chunk of the split diff.

**Signature**

```python
def chunk_error_handler(ctx: RunContextWrapper[ReviewContext], error: Exception) -> str:
    return "That file could not be read from the diff. Try another path, or continue without it."

@function_tool(failure_error_function=chunk_error_handler)
def read_diff_chunk(
    ctx: RunContextWrapper[ReviewContext],
    path: Annotated[str, "Path of the file within the diff to read"],
) -> str: ...
```

**Model-visible argument schema**

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "Path of the file within the diff to read" }
  },
  "required": ["path"],
  "additionalProperties": false
}
```

**Returns**: the chunk's text.

**Failure behaviour (NFR-4)**: `failure_error_function=` is set, so a failure produces a sentence
sent back to the model instead of an exception entering the runner. Setting this argument to
`None` would re-raise and is explicitly a defect — a raise into the runner is forbidden by
constitution Principle IV.

---

## `merge_findings` (Merge specialist, exposed as a tool)

The Merge specialist is not called as a plain function; it is an agent exposed to the Desk as a
tool so the Desk retains the conversation (FR-6).

**Signature**

```python
merge_tool = merge_specialist.as_tool(
    tool_name="merge_findings",
    tool_description="Deduplicate overlapping findings and order them by severity.",
)
```

**Input**: the collected findings from the three reviewers.
**Returns**: a deduplicated, severity-ordered list of findings, which the Desk uses to build the
report and its footer.

**Distinction from remediation**: this call returns a *value* the Desk continues with. The
remediation specialist is reached through a handoff and takes ownership of the conversation
instead — see `contracts/structures.md` and `plan.md` for the argument.

---

## Controls summary

| Control | Where | Requirement |
|---------|-------|-------------|
| Forced call | `ModelSettings(tool_choice=...)` names the ruleset tool, so the model has no choice but to call it | FR-9 |
| Failing tool | `failure_error_function=` on `read_diff_chunk` returns a sentence | FR-9, NFR-4 |
| Schema exclusion | `ctx: RunContextWrapper[...]` first parameter, absent from the schema | FR-2 |
| Turn ceiling | Applies to every review run, evaluated by the run's own ceiling setting | FR-9 |

**Note on the forced call and loops**: `tool_choice` is reset to `"auto"` after a tool call, so
forcing the ruleset call does not itself create a loop. The loop risk is answered by the turn
ceiling, which is the control that terminates a reviewer that keeps calling tools (8 turns — see
`plan.md`).
