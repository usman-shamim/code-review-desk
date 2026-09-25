"""FR-8 — the output guardrail that refuses any report quoting a credential.

Detection is shape-based, so a planted fake key is refused exactly as a real one would be
and no network call is made to decide. The matched text is deliberately never returned,
logged, or embedded in the guardrail's output_info: NFR-1 forbids a credential reaching the
report, the ledger, the trace or the interface, and that includes the refusal itself.
"""

from __future__ import annotations

import re
from typing import Any

from agents import GuardrailFunctionOutput, RunContextWrapper, output_guardrail

from .models import Report

REFUSAL_MESSAGE = "The report was refused: it contained something shaped like a credential."

# Order matters only for which pattern is reported first; all are checked.
_CREDENTIAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-./+]{16,}"),
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd|bearer)\b"
        r"\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+]{12,}"
    ),
)


def contains_credential(text: str) -> bool:
    """True if `text` contains anything shaped like a credential.

    Returns a bool rather than the match so callers cannot accidentally propagate the secret.
    """
    return any(pattern.search(text) for pattern in _CREDENTIAL_PATTERNS)


def _text_of(output: Any) -> str:
    if isinstance(output, Report):
        parts = [finding.message for finding in output.findings]
        parts.append(output.refusal_message)
        return "\n".join(parts)
    return str(output)


@output_guardrail(name="no_credentials")
async def no_credentials(
    ctx: RunContextWrapper[Any], agent: Any, output: Any
) -> GuardrailFunctionOutput:
    """Inspects the finished report. Runs after the model has been paid for."""
    triggered = contains_credential(_text_of(output))
    return GuardrailFunctionOutput(
        # A fixed sentence, never the offending text.
        output_info=REFUSAL_MESSAGE if triggered else None,
        tripwire_triggered=triggered,
    )
