"""FR-1, SC-001 — the diff is split by file before any model sees it.

Everything here is pure text handling, so it runs with no API key and no network.
"""

from __future__ import annotations

from desk.diff import render_chunks, split_diff


def test_two_file_diff_produces_two_chunks(two_file_diff: str) -> None:
    chunks = split_diff(two_file_diff)
    assert len(chunks) == 2
    assert [chunk.path for chunk in chunks] == ["src/auth.py", "src/util.py"]


def test_three_file_diff_produces_three_chunks(samples) -> None:
    chunks = split_diff((samples / "three-file.diff").read_text(encoding="utf-8"))
    assert [chunk.path for chunk in chunks] == ["src/auth.py", "src/util.py", "src/report.py"]


def test_chunks_carry_their_hunks(two_file_diff: str) -> None:
    first = split_diff(two_file_diff)[0]
    assert "+++ b/src/auth.py" in first.text
    assert "+import os" in first.text


def test_empty_diff_yields_no_chunks() -> None:
    assert split_diff("") == []


def test_malformed_diff_yields_no_chunks(samples) -> None:
    assert split_diff((samples / "malformed.diff").read_text(encoding="utf-8")) == []


def test_binary_file_is_not_treated_as_reviewable_text() -> None:
    binary = (
        "diff --git a/logo.png b/logo.png\n"
        "index 0000000..1111111 100644\n"
        "Binary files a/logo.png and b/logo.png differ\n"
        "diff --git a/src/a.py b/src/a.py\n"
        "--- a/src/a.py\n"
        "+++ b/src/a.py\n"
        "@@ -1 +1 @@\n"
        "-x = 1\n"
        "+x = 2\n"
    )
    chunks = split_diff(binary)
    assert [chunk.path for chunk in chunks] == ["src/a.py"]


def test_git_binary_patch_is_skipped() -> None:
    patch = (
        "diff --git a/blob.bin b/blob.bin\n"
        "GIT binary patch\n"
        "literal 12\n"
        "zcmZQzU|?VX0000\n"
    )
    assert split_diff(patch) == []


def test_deletion_with_no_added_lines_is_still_a_chunk() -> None:
    deletion = (
        "diff --git a/src/gone.py b/src/gone.py\n"
        "deleted file mode 100644\n"
        "--- a/src/gone.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-a = 1\n"
        "-b = 2\n"
    )
    chunks = split_diff(deletion)
    assert len(chunks) == 1
    assert chunks[0].path == "src/gone.py"


def test_chunks_are_observable_before_any_model_call(samples) -> None:
    """SC-001's real point: this function cannot call a model, so the ordering is structural."""
    import inspect

    source = inspect.getsource(split_diff)
    for forbidden in ("Runner", "Agent", "openai", "await"):
        assert forbidden not in source


def test_render_chunks_is_readable(two_file_diff: str) -> None:
    rendered = render_chunks(split_diff(two_file_diff))
    assert "2 chunk(s)" in rendered
    assert "src/auth.py" in rendered


def test_render_chunks_handles_nothing() -> None:
    assert render_chunks([]) == "No chunks produced."
