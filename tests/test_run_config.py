"""FR-7 and FR-13 — the run-level override, and a trace that records no sensitive data."""

from __future__ import annotations

import inspect

from desk import config, pipeline


def test_run_config_disables_sensitive_tracing() -> None:
    """The C1 fix. The SDK default is True, which records prompts and tool I/O — and the
    diff is both, so the trace would carry the credential FR-8 exists to refuse."""
    assert pipeline.build_run_config().trace_include_sensitive_data is False


def test_the_default_run_config_carries_no_model_override() -> None:
    """FR-7's contrast: without --cheap, nothing overrides the agents' own models."""
    assert pipeline.build_run_config(cheap=False).model is None


def test_cheap_run_config_sets_the_model_at_run_level() -> None:
    assert pipeline.build_run_config(cheap=True).model == config.cheap_model_name()


def test_cheap_model_differs_from_the_agent_level_model() -> None:
    assert config.cheap_model_name() != config.model_name()


def test_trace_is_named_for_the_review() -> None:
    assert pipeline.build_run_config().workflow_name == "code-review-desk"


def test_no_agent_definition_uses_run_config() -> None:
    """FR-7 requires the override to happen on the run, leaving every agent untouched.

    Checked against the parsed syntax tree rather than the raw text, so the module docstring
    may name RunConfig while no agent definition actually uses it.
    """
    import ast

    from desk import agents

    used = {
        node.id
        for node in ast.walk(ast.parse(inspect.getsource(agents)))
        if isinstance(node, ast.Name)
    }
    assert "RunConfig" not in used


def test_run_config_is_applied_to_every_runner_call() -> None:
    source = inspect.getsource(pipeline)
    assert source.count("run_config=run_config") >= 2


def test_turn_ceiling_is_configured() -> None:
    assert config.max_turns() == config.DEFAULT_MAX_TURNS == 8


def test_turn_ceiling_is_passed_to_every_run() -> None:
    source = inspect.getsource(pipeline)
    assert "max_turns=signals.ceiling" in source
    assert source.count("max_turns=signals.ceiling") >= 2


def test_error_handlers_are_registered_for_the_ceiling() -> None:
    """Without a handler the SDK raises MaxTurnsExceeded; with one it recovers to a partial."""
    source = inspect.getsource(pipeline)
    assert '"max_turns"' in source
    assert "RunErrorHandlerResult" in source


def test_gather_does_not_abort_the_group() -> None:
    """The C2 fix: with the default return_exceptions=False, one ceiling failure would
    cancel the other two reviewers and discard their completed work."""
    source = inspect.getsource(pipeline)
    assert "return_exceptions=True" in source


def test_guardrail_tripwire_is_caught_rather_than_propagated() -> None:
    """FR-8: the refusal is reported, not crashed."""
    source = inspect.getsource(pipeline)
    assert "except OutputGuardrailTripwireTriggered" in source
