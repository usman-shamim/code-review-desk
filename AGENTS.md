# module2-code-review-desk Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-09-25

## Active Technologies

- Python 3.11+ (targets the `openai-agents` SDK's async surface) + `openai-agents` (OpenAI Agents SDK), `pydantic`, `python-dotenv`, `chainlit` (001-code-review-desk)
- `uv` for environment and dependency management; `pytest` for tests

## Project Structure

```text
src/desk/       # the pipeline package (config, diff, models, agents, tools, guardrails,
                # hooks, ledger, pipeline, cli)
app.py          # Chainlit page: paste a diff, stream findings
rulesets/       # ruleset files a reviewer must consult
specs/          # spec, plan, tasks and design artifacts
tests/          # pytest
```

## Commands

```bash
uv sync                       # create the environment and install dependencies
uv run pytest                 # run the tests
uv run ruff check .           # lint
uv run desk-review <diff>     # review a unified diff from the command line
uv run chainlit run app.py    # start the streaming interface
```

## Code Style

Python 3.11+: follow standard conventions. Requirements are numbered `FR-1`…`FR-13` and
`NFR-1`…`NFR-5`; each file in `src/desk/` maps onto named requirements, and the mapping is
recorded in `specs/001-code-review-desk/plan.md`.

**Non-negotiables from `.specify/memory/constitution.md`**: credentials live only in the
gitignored `.env` and are loaded with `python-dotenv`; a missing key fails at startup with one
sentence, never a traceback; no tool may raise into the runner; every agent declares its own
model settings; the reviewed code is never executed.

## Recent Changes

- 001-code-review-desk: Added Python 3.11+ (targets the `openai-agents` SDK's async surface) + `openai-agents` (OpenAI Agents SDK), `pydantic`, `python-dotenv`, `chainlit`

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
