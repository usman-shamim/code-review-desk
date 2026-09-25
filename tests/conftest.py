"""Shared fixtures. Nothing here needs an API key."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from desk.models import ReviewContext

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = REPO_ROOT / "samples"


@pytest.fixture
def samples() -> Path:
    return SAMPLES


@pytest.fixture
def context() -> ReviewContext:
    return ReviewContext(
        repo="acme/secret-internal-project",
        language="python",
        ruleset_id="python-strict",
    )


@pytest.fixture
def strict_context() -> ReviewContext:
    return ReviewContext(
        repo="acme/secret-internal-project",
        language="python",
        ruleset_id="python-strict",
        strictness="strict",
    )


@pytest.fixture
def two_file_diff() -> str:
    return (SAMPLES / "two-file.diff").read_text(encoding="utf-8")


@pytest.fixture
def has_api_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


requires_key = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="needs OPENAI_API_KEY; every offline check runs without it",
)
