"""NFR-1 — credentials live in a gitignored .env and nowhere else.

The .env file is loaded at import, before any client is constructed, so a missing key
fails at startup with one sentence and a non-zero exit rather than a KeyError traceback.
Never read a credential with os.environ["KEY"]: that is the traceback this forbids.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"

# Loaded at import. Missing file is not an error here; a missing *variable* is, below.
load_dotenv(ENV_PATH)

# FR-1: the reviewer model, configured on the agent itself.
DEFAULT_MODEL = "gpt-5-nano"

# FR-7: the run-level override. Applied through RunConfig, never written into an agent.
DEFAULT_CHEAP_MODEL = "gpt-5-mini"

# FR-9: the turn ceiling. See plan.md, Decided Numbers, for the reasoning behind 8.
DEFAULT_MAX_TURNS = 8

REQUIRED_ENV = ("OPENAI_API_KEY",)


def require_env(*names: str) -> None:
    """Exit with one sentence if any credential is absent.

    Raises SystemExit(1) rather than a traceback — NFR-1, SC-005.
    """
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        print(
            f"Missing env var(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        raise SystemExit(1)


def model_name() -> str:
    return os.environ.get("DESK_MODEL") or DEFAULT_MODEL


def cheap_model_name() -> str:
    return os.environ.get("DESK_CHEAP_MODEL") or DEFAULT_CHEAP_MODEL


def max_turns() -> int:
    try:
        return int(os.environ.get("DESK_MAX_TURNS") or DEFAULT_MAX_TURNS)
    except ValueError:
        return DEFAULT_MAX_TURNS


def rulesets_dir() -> Path:
    return Path(os.environ.get("DESK_RULESETS_DIR") or (REPO_ROOT / "rulesets"))
