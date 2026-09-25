"""FR-11, NFR-3 — one line per run in ledger.jsonl, registered once at startup.

A trace processor rather than a Runner subclass. FR-11 requires that no agent definition
mentions the ledger, and a Runner subclass would have to be threaded through every call
site — which is exactly what that requirement forbids. Removing the single `register()`
call in the entry point is the whole switch.

Lines carry metadata only. No diff content, no finding text, and no credential ever reaches
this file: the entry shape below has nowhere to put them.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agents import add_trace_processor
from agents.tracing import TracingProcessor

LEDGER_FILENAME = "ledger.jsonl"


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _iso(value: Any) -> str:
    moment = _as_datetime(value) or datetime.now(UTC)
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _duration_ms(started: Any, ended: Any) -> int:
    begin, finish = _as_datetime(started), _as_datetime(ended)
    if begin is None or finish is None:
        return 0
    return max(0, int((finish - begin).total_seconds() * 1000))


class LedgerProcessor(TracingProcessor):
    """Buffers one entry per completed agent run, then writes them on flush().

    Buffering exists for one reason: the finding count is known to the pipeline slightly
    after the span ends, so entries are held until the caller can supply it. Without that,
    every line would claim zero findings.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._pending: list[dict[str, Any]] = []
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    # -- ledger API -----------------------------------------------------------

    def note_findings(self, agent: str, count: int) -> None:
        """Record how many findings a run produced, keyed by agent name."""
        with self._lock:
            self._counts[agent] = int(count)

    def record_run(
        self,
        agent: str,
        request_id: str,
        started: Any,
        ended: Any,
        findings: int = 0,
    ) -> dict[str, Any]:
        """Append a pending entry. Exposed so tests and callers can record explicitly."""
        entry = {
            "ts": _iso(started),
            "request_id": request_id,
            "agent": agent,
            "ms": _duration_ms(started, ended),
            "findings": int(findings),
        }
        with self._lock:
            self._pending.append(entry)
        return entry

    def flush(self) -> int:
        """Write every pending entry, filling in finding counts. Returns lines written."""
        with self._lock:
            pending, self._pending = self._pending, []
            counts = dict(self._counts)
        if not pending:
            return 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            for entry in pending:
                if entry["agent"] in counts:
                    entry["findings"] = counts[entry["agent"]]
                handle.write(json.dumps(entry, sort_keys=True) + "\n")
        return len(pending)

    # -- TracingProcessor interface -------------------------------------------

    def on_trace_start(self, trace: Any) -> None:  # noqa: D102 - interface method
        return None

    def on_trace_end(self, trace: Any) -> None:  # noqa: D102 - interface method
        return None

    def on_span_start(self, span: Any) -> None:  # noqa: D102 - interface method
        return None

    def on_span_end(self, span: Any) -> None:
        """One entry per completed agent run. Other span kinds are ignored."""
        data = getattr(span, "span_data", None)
        if type(data).__name__ != "AgentSpanData":
            return
        started = getattr(span, "started_at", None)
        ended = getattr(span, "ended_at", None)
        with self._lock:
            self._pending.append(
                {
                    "ts": _iso(started),
                    "request_id": getattr(span, "trace_id", "") or "",
                    "agent": getattr(data, "name", "") or "",
                    "ms": _duration_ms(started, ended),
                    "findings": 0,
                }
            )

    def shutdown(self) -> None:  # noqa: D102 - interface method
        return None

    def force_flush(self) -> None:  # noqa: D102 - interface method
        return None


_processor: LedgerProcessor | None = None


def register(path: Path) -> LedgerProcessor:
    """Register the ledger once, at startup (FR-11)."""
    global _processor
    processor = LedgerProcessor(path)
    add_trace_processor(processor)
    _processor = processor
    return processor


def current() -> LedgerProcessor | None:
    return _processor


def reset() -> None:
    """Test helper: forget the registered processor."""
    global _processor
    _processor = None
