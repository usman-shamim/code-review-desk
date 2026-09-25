"""FR-1 and NFR-1 end to end, through a real subprocess with no API key present.

These are the checks that prove a missing key produces one sentence rather than a traceback,
and that the offline paths of FR-1 to FR-4 work with no credential at all.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SAMPLES = REPO / "samples"


def cli(*args: str, with_key: bool = False) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if not with_key:
        env.pop("OPENAI_API_KEY", None)
        # Point the loader away from the repository .env, so the key really is absent. Without
        # this the loader reads .env and re-supplies it, and NFR-1's failure mode stops being
        # observable the moment a real key exists.
        env["DESK_ENV_FILE"] = str(Path(tempfile.gettempdir()) / "desk-absent.env")
    return subprocess.run(
        [sys.executable, "-m", "desk.cli", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=env,
        timeout=180,
    )


def test_two_file_diff_produces_two_chunks() -> None:
    result = cli(str(SAMPLES / "two-file.diff"), "--dry-run-split")
    assert result.returncode == 0
    assert "2 chunk(s)" in result.stdout
    assert "src/auth.py" in result.stdout
    assert "src/util.py" in result.stdout


def test_three_file_diff_produces_three_chunks() -> None:
    result = cli(str(SAMPLES / "three-file.diff"), "--dry-run-split")
    assert "3 chunk(s)" in result.stdout


def test_empty_diff_is_a_message_not_a_traceback() -> None:
    result = cli(str(SAMPLES / "empty.diff"), "--dry-run-split")
    assert result.returncode == 2
    assert "No reviewable files found" in result.stderr
    assert "Traceback" not in result.stderr


def test_malformed_diff_is_a_message_not_a_traceback() -> None:
    result = cli(str(SAMPLES / "malformed.diff"), "--dry-run-split")
    assert result.returncode == 2
    assert "No reviewable files found" in result.stderr
    assert "Traceback" not in result.stderr


def test_unreadable_path_is_a_message() -> None:
    result = cli("/nonexistent/not-a-diff.diff", "--dry-run-split")
    assert result.returncode == 2
    assert "Could not read that diff" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_key_exits_with_one_sentence_and_no_traceback() -> None:
    """SC-005, exactly."""
    result = cli(str(SAMPLES / "two-file.diff"))
    assert result.returncode == 1
    assert "Missing env var(s): OPENAI_API_KEY" in result.stderr
    assert "Traceback" not in result.stderr
    assert len([line for line in result.stderr.splitlines() if line.strip()]) == 1


def test_the_key_failure_names_the_variable_the_spec_names() -> None:
    result = cli(str(SAMPLES / "two-file.diff"))
    assert "OPENAI_API_KEY" in result.stderr
    assert ".env.example" in result.stderr


def test_output_schema_shows_the_list_root_wrapper() -> None:
    """FR-3's acceptance: the wrapper can be pointed at."""
    result = cli(str(SAMPLES / "two-file.diff"), "--print-schema")
    assert result.returncode == 0
    assert '"response"' in result.stdout
    assert '"Finding"' in result.stdout
    assert '"severity"' in result.stdout


def test_prompt_printing_shows_strictness_differences() -> None:
    normal = cli(str(SAMPLES / "two-file.diff"), "--print-prompt")
    strict = cli(str(SAMPLES / "two-file.diff"), "--print-prompt", "--strictness", "strict")
    assert "Normal mode" in normal.stdout
    assert "Strict mode" in strict.stdout


def test_prompt_carries_no_repository_name() -> None:
    """SC-010 through the real CLI."""
    result = cli(str(SAMPLES / "two-file.diff"), "--print-prompt", "--repo", "acme/topsecret")
    assert result.returncode == 0
    assert "acme" not in result.stdout
    assert "topsecret" not in result.stdout


def test_introspection_paths_need_no_key_at_all() -> None:
    for flag in ("--dry-run-split", "--print-prompt", "--print-schema"):
        result = cli(str(SAMPLES / "two-file.diff"), flag)
        assert result.returncode == 0, f"{flag} needed a key: {result.stderr}"


@pytest.mark.parametrize(
    "name", ["two-file.diff", "three-file.diff", "planted-key.diff", "planted-critical.diff",
             "duplicate-findings.diff", "empty.diff", "malformed.diff"]
)
def test_every_sample_file_exists_and_is_handled(name: str) -> None:
    assert (SAMPLES / name).exists()
    result = cli(str(SAMPLES / name), "--dry-run-split")
    assert result.returncode in (0, 2)
    assert "Traceback" not in (result.stderr + result.stdout)


def test_pasted_diff_path_works_from_a_temp_file() -> None:
    """The interface accepts pasted text; the CLI accepts a path to the same content."""
    with tempfile.TemporaryDirectory() as tmp:
        pasted = Path(tmp) / "pasted.diff"
        pasted.write_text((SAMPLES / "two-file.diff").read_text(encoding="utf-8"))
        result = cli(str(pasted), "--dry-run-split")
    assert "2 chunk(s)" in result.stdout
