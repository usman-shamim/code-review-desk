"""FR-1 — split a unified diff by file, before any model sees it.

Nothing in this module calls a model. The split is pure text handling, which is why
`--dry-run-split` can be demonstrated without an API key.
"""

from __future__ import annotations

from .models import DiffChunk

_BINARY_MARKERS = ("GIT binary patch", "Binary files ")
_PATH_PREFIXES = ("a/", "b/")


def _chunk_starts(lines: list[str]) -> list[int]:
    """Indices where a new file's block begins.

    git-style diffs carry `diff --git`; plain unified diffs only have `---`/`+++`.
    Prefer the former when present so the two are never double-counted.
    """
    git_starts = [i for i, line in enumerate(lines) if line.startswith("diff --git ")]
    if git_starts:
        return git_starts
    return [
        i
        for i, line in enumerate(lines)
        if line.startswith("--- ")
        and i + 1 < len(lines)
        and lines[i + 1].startswith("+++ ")
    ]


def _strip_prefix(raw: str) -> str:
    for prefix in _PATH_PREFIXES:
        if raw.startswith(prefix):
            return raw[len(prefix) :]
    return raw


def _extract_path(block: list[str]) -> str:
    """Prefer the +++ side, fall back to --- (a deletion has /dev/null on the +++ side)."""
    plus = next((line for line in block if line.startswith("+++ ")), None)
    minus = next((line for line in block if line.startswith("--- ")), None)

    for line in (plus, minus):
        if line is None:
            continue
        raw = line[4:].split("\t")[0].strip()
        if raw == "/dev/null":
            continue
        return _strip_prefix(raw)

    head = block[0] if block else ""
    if head.startswith("diff --git "):
        parts = head.split()
        if len(parts) >= 4:
            return _strip_prefix(parts[3])
    return "(unknown)"


def _is_binary(block: list[str]) -> bool:
    return any(marker in line for line in block for marker in _BINARY_MARKERS)


def split_diff(raw: str) -> list[DiffChunk]:
    """One DiffChunk per file.

    Binary files are excluded rather than handed to a reviewer as text. An empty or
    malformed diff yields no chunks; the caller turns that into a message, not a traceback.
    """
    lines = raw.splitlines()
    starts = _chunk_starts(lines)

    chunks: list[DiffChunk] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = lines[start:end]
        if _is_binary(block):
            continue
        chunks.append(DiffChunk(path=_extract_path(block), text="\n".join(block)))

    return chunks


def render_chunks(chunks: list[DiffChunk]) -> str:
    """Human-readable summary for `--dry-run-split`."""
    if not chunks:
        return "No chunks produced."
    width = max(len(chunk.path) for chunk in chunks)
    lines = [f"{len(chunks)} chunk(s), produced before any model call:"]
    for index, chunk in enumerate(chunks, start=1):
        changed = sum(
            1 for line in chunk.text.splitlines() if line[:1] in ("+", "-")
        )
        lines.append(f"  {index:>2}. {chunk.path:<{width}}  {changed:>3} changed line(s)")
    return "\n".join(lines)
