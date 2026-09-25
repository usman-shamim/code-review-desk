"""FR-12 — the interface streams, holds session state, and awaits its run.

Chainlit cannot be driven headlessly here, so these assertions are structural: they check the
properties the requirement actually names, and the generator the page consumes is checked
behaviourally in test_pipeline_streaming.py.
"""

from __future__ import annotations

import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app.py"


def _source() -> str:
    return APP.read_text(encoding="utf-8")


def test_app_exists() -> None:
    assert APP.exists()


def test_stream_review_is_an_async_generator() -> None:
    from desk.pipeline import stream_review

    assert inspect.isasyncgenfunction(stream_review)


def test_the_page_consumes_the_stream_with_async_for() -> None:
    """FR-12: the handler awaits its run rather than calling a synchronous variant."""
    source = _source()
    assert "async for event in stream_review(" in source


def test_the_page_never_uses_a_synchronous_run_variant() -> None:
    source = _source()
    for forbidden in ("run_sync", "asyncio.run(", "Runner.run("):
        assert forbidden not in source, f"the page should not contain {forbidden}"


def test_session_state_holds_the_context_and_the_last_report() -> None:
    source = _source()
    assert "cl.user_session.set(CONTEXT_KEY" in source
    assert "cl.user_session.set(LAST_REPORT_KEY" in source


def test_context_is_reused_for_a_second_diff_in_the_same_session() -> None:
    source = _source()
    assert "cl.user_session.get(CONTEXT_KEY)" in source
    assert "_context_for" in source


def test_findings_are_sent_as_each_reviewer_finishes() -> None:
    """Progressive delivery: a message per reviewer event, not one message at the end."""
    source = _source()
    assert 'event["event"] == "reviewer"' in source
    assert "await cl.Message(" in source


def test_the_page_reports_a_refusal_instead_of_a_report() -> None:
    source = _source()
    assert "REFUSED" in source
    assert "refusal_message" in source


def test_the_page_registers_the_ledger_once_at_startup() -> None:
    source = _source()
    assert "ledger.register(" in source
    assert "@cl.on_chat_start" in source


def test_the_page_requires_a_key_before_anything_else() -> None:
    source = _source()
    assert "require_env(*config.REQUIRED_ENV)" in source


def test_the_page_shows_the_footer() -> None:
    assert "render_footer(" in _source()


def test_the_page_splits_before_reviewing() -> None:
    """FR-1 applies to the interface too, not only the CLI."""
    source = _source()
    assert "split_diff(message.content)" in source
    assert "NO_REVIEWABLE_FILES" in source
