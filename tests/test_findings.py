"""FR-3 and FR-6 — typed findings, and the merge that reconciles them."""

from __future__ import annotations

from agents import AgentOutputSchema

from desk.models import (
    SEVERITY_ORDER,
    Finding,
    MergeInput,
    RemediationInput,
    Report,
    dedupe_findings,
    sort_findings,
)


def _finding(file: str, line: int, severity: str, message: str = "m") -> Finding:
    return Finding(file=file, line=line, severity=severity, message=message)


def test_output_schema_wraps_a_list_root_in_an_object() -> None:
    """FR-3: the wrapper is required, and explaining it is part of the requirement."""
    schema = AgentOutputSchema(list[Finding]).json_schema()
    assert "response" in schema["properties"]
    assert schema["required"] == ["response"]
    assert schema["properties"]["response"]["type"] == "array"
    assert schema["properties"]["response"]["items"]["$ref"].endswith("Finding")


def test_finding_severity_is_constrained() -> None:
    enum = Finding.model_json_schema()["properties"]["severity"]["enum"]
    assert set(enum) == {"critical", "major", "minor"}


def test_criticals_are_countable_with_one_expression(two_file_diff: str) -> None:
    findings = [
        _finding("a.py", 1, "critical"),
        _finding("a.py", 9, "minor"),
        _finding("b.py", 4, "major"),
    ]
    report = Report(findings=findings)
    assert sum(1 for f in report.findings if f.severity == "critical") == 1
    assert report.criticals() == 1


def test_severity_order_is_critical_first() -> None:
    assert SEVERITY_ORDER == {"critical": 0, "major": 1, "minor": 2}


def test_sort_findings_orders_by_severity_then_location() -> None:
    ordered = sort_findings(
        [
            _finding("z.py", 1, "minor"),
            _finding("a.py", 5, "critical"),
            _finding("a.py", 2, "critical"),
        ]
    )
    assert [(f.severity, f.file, f.line) for f in ordered] == [
        ("critical", "a.py", 2),
        ("critical", "a.py", 5),
        ("minor", "z.py", 1),
    ]


def test_dedupe_collapses_the_same_line_to_the_highest_severity() -> None:
    """FR-6: three reviewers seeing one problem produce one finding, not three."""
    merged = dedupe_findings(
        [
            _finding("a.py", 10, "minor", "naming is unclear"),
            _finding("a.py", 10, "critical", "this concatenates user input"),
            _finding("a.py", 10, "major", "swallows the exception"),
        ]
    )
    assert len(merged) == 1
    assert merged[0].severity == "critical"
    # No reviewer's explanation is discarded.
    message = merged[0].message
    for part in ("naming is unclear", "concatenates user input", "swallows the exception"):
        assert part in message


def test_dedupe_keeps_distinct_lines_apart() -> None:
    merged = dedupe_findings([_finding("a.py", 1, "minor"), _finding("a.py", 2, "minor")])
    assert len(merged) == 2


def test_dedupe_of_nothing_is_nothing() -> None:
    assert dedupe_findings([]) == []


def test_merge_input_is_the_structured_payload() -> None:
    """FR-6: a nested as_tool run inherits no state, so the findings are passed in."""
    payload = MergeInput(findings=[_finding("a.py", 1, "critical")])
    assert len(payload.findings) == 1


def test_remediation_input_names_the_finding_that_triggered_it() -> None:
    payload = RemediationInput(
        finding=_finding("a.py", 1, "critical", "hardcoded password"),
        context_summary="python, strict",
    )
    assert payload.finding.severity == "critical"
    assert "password" in payload.finding.message


def test_report_defaults_are_safe() -> None:
    report = Report()
    assert report.findings == []
    assert report.partial is False
    assert report.refused is False
