"""FR-11, SC-009 — one line per run, metadata only.

Spans are fed to the processor directly rather than through a live trace, so this is
deterministic and needs no API key. The processor's write path is the same either way.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from agents.tracing.span_data import AgentSpanData

from desk.ledger import LedgerProcessor

START = datetime(2026, 9, 25, 19, 4, 11, tzinfo=UTC)


class FakeSpan:
    """Stands in for a real AgentSpan; only the attributes the ledger reads are needed."""

    def __init__(self, name: str, seconds: float = 1.0, span_type: str = "agent") -> None:
        if span_type == "agent":
            self.span_data = AgentSpanData(name=name)
        else:
            self.span_data = type("FunctionSpanData", (), {"name": name})()
        self.started_at = START
        self.ended_at = START + timedelta(seconds=seconds)
        self.trace_id = "tr_test"


def _processor(tmp_path) -> LedgerProcessor:
    return LedgerProcessor(tmp_path / "ledger.jsonl")


def test_one_line_per_run(tmp_path) -> None:
    """FR-11's 'done when': a three-file review yields one line per run."""
    ledger = _processor(tmp_path)
    for name in ("SecurityReviewer", "TestsReviewer", "StyleReviewer", "Desk"):
        ledger.on_span_end(FakeSpan(name))
    assert ledger.flush() == 4

    lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4
    assert [json.loads(line)["agent"] for line in lines] == [
        "SecurityReviewer",
        "TestsReviewer",
        "StyleReviewer",
        "Desk",
    ]


def test_line_matches_the_documented_shape(tmp_path) -> None:
    ledger = _processor(tmp_path)
    ledger.on_span_end(FakeSpan("SecurityReviewer", seconds=2.14))
    ledger.flush()

    entry = json.loads((tmp_path / "ledger.jsonl").read_text(encoding="utf-8"))
    assert set(entry) == {"ts", "request_id", "agent", "ms", "findings"}
    assert entry["agent"] == "SecurityReviewer"
    assert entry["ms"] == 2140
    assert entry["ts"].startswith("2026-09-25T19:04:11")
    assert entry["request_id"] == "tr_test"


def test_finding_counts_are_filled_in_at_flush(tmp_path) -> None:
    """The count is known to the pipeline slightly after the span ends, hence the buffer."""
    ledger = _processor(tmp_path)
    ledger.on_span_end(FakeSpan("SecurityReviewer"))
    ledger.note_findings("SecurityReviewer", 3)
    ledger.flush()

    entry = json.loads((tmp_path / "ledger.jsonl").read_text(encoding="utf-8"))
    assert entry["findings"] == 3


def test_non_agent_spans_are_ignored(tmp_path) -> None:
    ledger = _processor(tmp_path)
    ledger.on_span_end(FakeSpan("read_ruleset", span_type="function"))
    assert ledger.flush() == 0


def test_no_line_carries_diff_or_finding_text(tmp_path) -> None:
    """NFR-1, SC-009: the entry shape has nowhere to put review content."""
    ledger = _processor(tmp_path)
    ledger.note_findings("SecurityReviewer", 2)
    ledger.on_span_end(FakeSpan("SecurityReviewer"))
    ledger.flush()

    raw = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
    for forbidden in ("sk-", "password", "+++", "---", "def ", "import "):
        assert forbidden not in raw


def test_flushing_twice_does_not_duplicate(tmp_path) -> None:
    ledger = _processor(tmp_path)
    ledger.on_span_end(FakeSpan("SecurityReviewer"))
    assert ledger.flush() == 1
    assert ledger.flush() == 0
    lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_appends_across_reviews(tmp_path) -> None:
    ledger = _processor(tmp_path)
    for _ in range(2):
        ledger.on_span_end(FakeSpan("SecurityReviewer"))
        ledger.flush()
    lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_missing_timestamps_do_not_break_a_line(tmp_path) -> None:
    """Tracing is inert without a key, so a span may carry no timings at all."""
    ledger = _processor(tmp_path)
    span = FakeSpan("SecurityReviewer")
    span.started_at = None
    span.ended_at = None
    ledger.on_span_end(span)
    ledger.flush()

    entry = json.loads((tmp_path / "ledger.jsonl").read_text(encoding="utf-8"))
    assert entry["ms"] == 0
    assert entry["ts"]


def test_register_is_the_single_switch(tmp_path, monkeypatch) -> None:
    """FR-11: removing one registration is the only change needed to disable the ledger."""
    import desk.ledger as module

    added = []
    monkeypatch.setattr(module, "add_trace_processor", lambda p: added.append(p))
    module.reset()

    processor = module.register(tmp_path / "ledger.jsonl")
    assert added == [processor]
    assert module.current() is processor

    module.reset()
    assert module.current() is None
