"""FR-8 — the output guardrail refuses credential-shaped reports.

The planted strings are deliberately fake. Detection is shape-based, so a fake key is
refused exactly as a real one would be, and nothing here makes a network call.
"""

from __future__ import annotations

import pytest
from agents import RunContextWrapper

from desk.guardrails import REFUSAL_MESSAGE, contains_credential, no_credentials
from desk.models import Finding, Report, ReviewContext

FAKE_OPENAI_KEY = "sk-proj-NOTAREALKEY0000000000000000000000000000000000"
FAKE_GITHUB_TOKEN = "ghp_NOTAREALTOKEN000000000000000000"
FAKE_AWS_ID = "AKIANOTAREALKEY000000"

CREDENTIAL_SHAPES = [
    FAKE_OPENAI_KEY,
    FAKE_GITHUB_TOKEN,
    FAKE_AWS_ID,
    "-----BEGIN RSA PRIVATE KEY-----",
    'api_key = "abcdefghijklmnop1234"',
    "password: hunter2hunter2hunter2",
    "Authorization: Bearer abcdefghijklmnopqrst",
]

ORDINARY_PROSE = [
    "The password is compared without a constant-time function.",
    "This API key should be moved into .env.",
    "No credential appears in this message.",
    "Token refresh is not retried on failure.",
    "The function reads a secret from the environment.",
]


def _report(*messages: str) -> Report:
    return Report(
        findings=[
            Finding(file="src/x.py", line=1, severity="critical", message=message)
            for message in messages
        ]
    )


@pytest.mark.parametrize("text", CREDENTIAL_SHAPES)
def test_credential_shapes_are_detected(text: str) -> None:
    assert contains_credential(text) is True


@pytest.mark.parametrize("text", ORDINARY_PROSE)
def test_prose_that_merely_mentions_credentials_is_not_flagged(text: str) -> None:
    """Naming the problem must stay possible; only reproducing the value is refused."""
    assert contains_credential(text) is False


def test_clean_report_text_is_not_flagged() -> None:
    described = ReviewContext(repo="a", language="b", ruleset_id="c").describe()
    assert contains_credential(described) is False


async def test_guardrail_trips_on_a_planted_key(context: ReviewContext) -> None:
    result = await no_credentials.guardrail_function(
        RunContextWrapper(context=context), None, _report(f"Hardcoded key {FAKE_OPENAI_KEY}")
    )
    assert result.tripwire_triggered is True
    assert result.output_info == REFUSAL_MESSAGE


async def test_guardrail_passes_a_clean_report(context: ReviewContext) -> None:
    result = await no_credentials.guardrail_function(
        RunContextWrapper(context=context),
        None,
        _report("Password is compared without a constant-time function."),
    )
    assert result.tripwire_triggered is False
    assert result.output_info is None


async def test_refusal_never_echoes_the_credential(context: ReviewContext) -> None:
    """NFR-1 applies to the refusal too: the fixed sentence carries no secret material."""
    result = await no_credentials.guardrail_function(
        RunContextWrapper(context=context), None, _report(f"key {FAKE_OPENAI_KEY}")
    )
    assert FAKE_OPENAI_KEY not in (result.output_info or "")
    assert FAKE_OPENAI_KEY not in REFUSAL_MESSAGE


async def test_guardrail_accepts_a_plain_string_output(context: ReviewContext) -> None:
    """The guardrail is also correct if it is ever attached to a string-returning agent."""
    result = await no_credentials.guardrail_function(
        RunContextWrapper(context=context), None, f"leaked {FAKE_AWS_ID}"
    )
    assert result.tripwire_triggered is True


async def test_guardrail_accepts_an_empty_report(context: ReviewContext) -> None:
    result = await no_credentials.guardrail_function(
        RunContextWrapper(context=context), None, Report()
    )
    assert result.tripwire_triggered is False


def test_planted_key_sample_file_is_what_the_guardrail_would_catch(samples) -> None:
    """The fixture used for the live demo really does contain a credential shape."""
    diff = (samples / "planted-key.diff").read_text(encoding="utf-8")
    assert contains_credential(diff) is True


def test_clean_sample_files_are_not_flagged(samples) -> None:
    for name in ("two-file.diff", "three-file.diff"):
        assert contains_credential((samples / name).read_text(encoding="utf-8")) is False
