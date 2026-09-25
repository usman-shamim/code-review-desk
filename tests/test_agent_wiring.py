"""FR-5, FR-6, FR-9, NFR-2 — how the agents are wired.

Structural assertions here, behavioural ones below: the two tools are actually invoked so
their failure paths are exercised rather than inspected.
"""

from __future__ import annotations

from agents import Agent, RunContextWrapper
from agents.tool_context import ToolContext

from desk import agents
from desk.models import RemediationInput, ReviewContext
from desk.tools import MISSING_RULESET, UNREADABLE_CHUNK, read_diff_chunk, read_ruleset


def _tool_context(context: ReviewContext, name: str, arguments: str = "{}") -> ToolContext:
    return ToolContext(
        context=context,
        tool_name=name,
        tool_call_id="call_test",
        tool_arguments=arguments,
    )


# -- FR-5: three reviewers, cloned ---------------------------------------------------------


def test_there_are_three_reviewers_with_distinct_names() -> None:
    crew = agents.reviewers()
    assert len(crew) == 3
    assert [r.name for r in crew] == ["SecurityReviewer", "TestsReviewer", "StyleReviewer"]


def test_reviewers_are_clones_sharing_the_same_tool_objects() -> None:
    """The shared-vs-own split the viva asks about.

    clone() is a shallow copy, so the tools list is the same list object in all three:
    the reviewers share their tools and differ only in instructions and settings.
    """
    crew = agents.reviewers()
    base_tools = crew[0].tools
    for reviewer in crew[1:]:
        assert reviewer.tools is base_tools
    assert [tool.name for tool in base_tools] == ["read_ruleset", "read_diff_chunk"]


def test_reviewers_differ_in_instructions_and_settings() -> None:
    crew = agents.reviewers()
    assert len({id(reviewer.instructions) for reviewer in crew}) == 3

    wrapper = RunContextWrapper(context=ReviewContext(repo="x", language="python", ruleset_id="r"))
    rendered = {reviewer.instructions(wrapper, reviewer) for reviewer in crew}
    assert len(rendered) == 3, "each reviewer resolves a distinct prompt"

    settings = {repr(reviewer.model_settings) for reviewer in crew}
    assert len(settings) == 3, "the security and style reviewers differ in model settings"


def test_reviewers_request_reasoning_settings_without_temperature() -> None:
    """The gpt-5-nano regression: temperature is rejected with a 400, so the request the model
    receives must carry reasoning effort and verbosity instead.

    Built through the SDK's own request builder, so this asserts the parameters that would go on
    the wire rather than the shape of our ModelSettings objects.
    """
    from agents.models.openai_responses import OpenAIResponsesModel
    from openai import AsyncOpenAI, omit

    model = OpenAIResponsesModel("gpt-5-nano", AsyncOpenAI(api_key="sk-not-used"))
    expected_effort = {
        "SecurityReviewer": "medium",
        "TestsReviewer": "medium",
        "StyleReviewer": "low",
    }
    for reviewer in agents.reviewers():
        request = model._build_response_create_kwargs(
            system_instructions="sys",
            input="diff",
            model_settings=reviewer.model_settings,
            tools=reviewer.tools,
            output_schema=None,
            handoffs=reviewer.handoffs,
        )
        assert request["temperature"] is omit, f"{reviewer.name} would send a temperature"
        assert request["reasoning"].effort == expected_effort[reviewer.name]
        assert request["text"]["verbosity"] == "low"


def test_every_agent_declares_its_own_model_and_settings() -> None:
    """NFR-2 and constitution Principle II — no agent inherits an SDK default."""
    every_agent = [
        *agents.reviewers(),
        agents.merge_specialist(),
        agents.remediation_specialist(),
        agents.desk_agent(with_remediation=False),
        agents.desk_agent(with_remediation=True),
    ]
    for agent in every_agent:
        assert agent.model, f"{agent.name} has no model"
        assert agent.model_settings is not None, f"{agent.name} has no model_settings"


def test_no_agent_uses_the_run_level_override_path() -> None:
    """FR-7 lives in the pipeline: no agent definition carries a run-level model change."""
    import ast
    import inspect

    from desk import pipeline

    used = {
        node.id
        for node in ast.walk(ast.parse(inspect.getsource(agents)))
        if isinstance(node, ast.Name)
    }
    assert "RunConfig" not in used
    assert "cheap_model_name" in inspect.getsource(pipeline)


# -- FR-9: the three controls --------------------------------------------------------------


def test_security_reviewer_forces_a_tool_call() -> None:
    security = next(r for r in agents.reviewers() if r.name == "SecurityReviewer")
    assert security.model_settings.tool_choice == "required"


def test_tool_choice_is_reset_after_the_first_call_by_default() -> None:
    """Why 'required' cannot cause an endless tool loop on its own."""
    assert Agent.__dataclass_fields__["reset_tool_choice"].default is True


async def test_missing_ruleset_returns_a_sentence_not_a_traceback(
    context: ReviewContext,
) -> None:
    """FR-9's 'done when': deleting the ruleset still finishes with a sensible message."""
    result = await read_ruleset.on_invoke_tool(
        _tool_context(context, "read_ruleset"), '{"ruleset_id": "no-such-ruleset"}'
    )
    assert result == MISSING_RULESET
    assert result.endswith(".")


async def test_unreadable_chunk_goes_through_the_error_handler(context: ReviewContext) -> None:
    """FR-9's second control: the failure becomes a sentence, not an exception."""
    result = await read_diff_chunk.on_invoke_tool(
        _tool_context(context, "read_diff_chunk"), '{"path": "not/in/this/diff.py"}'
    )
    assert result == UNREADABLE_CHUNK


async def test_readable_chunk_is_returned(context: ReviewContext) -> None:
    context.chunks = {"src/auth.py": "--- a/src/auth.py\n+++ b/src/auth.py\n"}
    result = await read_diff_chunk.on_invoke_tool(
        _tool_context(context, "read_diff_chunk"), '{"path": "src/auth.py"}'
    )
    assert "auth.py" in result


# -- FR-6: the two specialists, wired two different ways -----------------------------------


def test_merge_is_exposed_as_a_tool() -> None:
    tool = agents.merge_tool()
    assert tool.name == "merge_findings"
    assert "Deduplicate" in tool.description


def test_merge_tool_takes_structured_input() -> None:
    schema = agents.merge_tool().params_json_schema
    assert "findings" in schema.get("properties", {})
    assert "ctx" not in schema.get("properties", {})


def test_remediation_is_a_handoff_and_only_when_a_critical_exists() -> None:
    without = agents.desk_agent(with_remediation=False)
    with_critical = agents.desk_agent(with_remediation=True)
    assert without.handoffs == []
    assert len(with_critical.handoffs) == 1
    assert with_critical.handoffs[0].agent_name == "RemediationSpecialist"


def test_remediation_handoff_has_a_typed_input() -> None:
    item = agents.remediation_handoff()
    assert item.input_json_schema is not None
    assert "finding" in item.input_json_schema.get("properties", {})


def test_the_desk_carries_the_output_guardrail() -> None:
    """FR-8: the guardrail needs an agent whose output is the report."""
    desk = agents.desk_agent(with_remediation=False)
    assert len(desk.output_guardrails) == 1


def test_remediation_input_model_is_the_declared_one() -> None:
    assert RemediationInput.model_fields["finding"].is_required()
