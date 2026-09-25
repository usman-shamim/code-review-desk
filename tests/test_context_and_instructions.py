"""FR-2 and FR-4, SC-010 — context travels beside the prompt, never inside it."""

from __future__ import annotations

from agents import RunContextWrapper

from desk import agents
from desk.models import ReviewContext
from desk.tools import read_diff_chunk, read_ruleset


def _tool_schema(tool) -> dict:
    schema = getattr(tool, "params_json_schema", None)
    assert schema is not None, "the SDK did not expose a generated schema for this tool"
    return schema


def test_read_ruleset_schema_excludes_the_context_wrapper() -> None:
    """FR-2's mechanism: ctx is injected, and absent from what the model is shown."""
    properties = _tool_schema(read_ruleset).get("properties", {})
    assert "ctx" not in properties
    assert "ruleset_id" in properties


def test_read_diff_chunk_schema_excludes_the_context_wrapper() -> None:
    properties = _tool_schema(read_diff_chunk).get("properties", {})
    assert "ctx" not in properties
    assert "path" in properties


def test_repository_name_never_reaches_the_prompt(context: ReviewContext) -> None:
    """SC-010. The fixture's repo name is deliberately unmistakable."""
    reviewer = agents.base_reviewer()
    prompt = reviewer.instructions(RunContextWrapper(context=context), reviewer)
    assert "acme" not in prompt
    assert "secret-internal-project" not in prompt
    assert context.ruleset_id not in prompt


def test_prompt_is_resolved_per_run(context: ReviewContext, strict_context: ReviewContext) -> None:
    reviewer = agents.base_reviewer()
    normal = reviewer.instructions(RunContextWrapper(context=context), reviewer)
    strict = reviewer.instructions(RunContextWrapper(context=strict_context), reviewer)
    assert normal != strict


def test_strict_prompt_is_terser(context: ReviewContext, strict_context: ReviewContext) -> None:
    reviewer = agents.base_reviewer()
    normal = reviewer.instructions(RunContextWrapper(context=context), reviewer)
    strict = reviewer.instructions(RunContextWrapper(context=strict_context), reviewer)
    assert len(strict) < len(normal)
    assert "Strict mode" in strict
    assert "Normal mode" in normal


def test_strictness_is_carried_in_context() -> None:
    assert ReviewContext("r", "python", "s").is_strict is False
    assert ReviewContext("r", "python", "s", strictness="strict").is_strict is True


def test_every_reviewer_prompt_names_its_own_focus() -> None:
    prompts = {}
    for reviewer in agents.reviewers():
        wrapper = RunContextWrapper(
            context=ReviewContext(repo="x", language="go", ruleset_id="r")
        )
        prompts[reviewer.name] = reviewer.instructions(wrapper, reviewer)
    assert len(set(prompts.values())) == 3
    for name, text in prompts.items():
        assert "go" in text, f"{name} lost the language"
