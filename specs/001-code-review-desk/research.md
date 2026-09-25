# Phase 0 Research: Code Review Desk

**Feature**: `001-code-review-desk` | **Date**: 2026-09-25
**Purpose**: Resolve every open technical decision before design, so `plan.md` contains no
`NEEDS CLARIFICATION` markers.

Format below is Decision / Rationale / Alternatives considered, per the `/sp.plan` workflow.

---

## 1. Agent framework

**Decision**: OpenAI Agents SDK (`openai-agents`), using its `Agent`, `Runner`, `clone()`,
`as_tool()`, `handoffs`, `RunConfig`, `RunHooks`, `AgentHooks`, `@output_guardrail`, tracing,
and `asyncio` for concurrency.

**Rationale**: The brief's concept-coverage table is effectively the SDK's feature list —
cloning, agents-as-tools, handoffs, advanced tool control, structured output, guardrails,
lifecycle hooks, run lifecycle hooks, custom runners, tracing. Using the SDK means each numbered
requirement maps to a named, documented primitive that can be pointed at in the viva, rather than
to hand-written infrastructure that only resembles it. Tracing in particular is built in, which
satisfies FR-13 without adding an observability stack.

**Alternatives considered**: A hand-rolled asyncio pipeline (rejected: FR-6, FR-8, FR-10 and
FR-13 would all become bespoke code with no SDK primitive to name, and the graded contrast in
FR-1 versus FR-7 would collapse into "two places that read a config value"). Pydantic AI
(rejected: strong framework, but its guardrail and handoff vocabulary differs from the one the
brief's coverage table implies).

## 2. Provider and model

**Decision**: OpenAI `gpt-5-nano`, configured **on the agent** for reviewers (FR-1), with the
cheaper re-run applied via run-level configuration (FR-7).

**Rationale**: The operator holds an OpenAI credential and no Google credential. The graded
property is the *level* at which the model is configured, and that property is preserved exactly.
The deviation from the brief's named `gemini-2.5-flash` is recorded in `spec.md` Assumptions, per
the constitution's governance rule, rather than silently absorbed.

**Alternatives considered**: Gemini 2.5 Flash as literally written (rejected: no credential
available, so the build could not run at all). Configuring the model in one shared constant
(rejected: that is exactly the ambiguity FR-1 versus FR-7 is designed to expose).

## 3. Concurrency

**Decision**: `asyncio.gather` over three cloned reviewers, started together and awaited as a
group.

**Rationale**: FR-5 grades the wall-clock difference between concurrent and sequential execution.
`gather` schedules all three coroutines before awaiting any of them, so the three model calls
overlap. Keeping the sequential variant a one-line change (a loop instead of `gather`) makes the
two measurements directly comparable, which is what the viva asks to see.

**Alternatives considered**: Threads (rejected: the SDK's surface is async, so threads would wrap
an async API and add a second concurrency model for no benefit). A task queue (rejected: the fan
out is exactly three items and returns as a group — a queue would only add a stage to the
pipeline).

## 4. Reviewer derivation: clone or redeclare

**Decision**: One base reviewer definition; the security, tests and style reviewers are produced
by `clone()` with different instructions and model settings.

**Rationale**: FR-5 asks which parts of the three reviewers are shared with the base and which are
their own — a question that only has a crisp answer if the sharing is real. Cloning also keeps
the three definitions provably in sync on tools and structure, so a diff between them is limited
to instructions and settings.

**Alternatives considered**: Three separately declared agents (rejected: the shared/own split
becomes a matter of eyeballing three files, and drift becomes possible). A single agent run three
times with different prompts (rejected: the brief explicitly describes them as differing in model
settings too, which is an agent-level property).

## 5. Merge as a tool, remediation as a handoff

**Decision**: Merge is exposed with `as_tool`; remediation is reached through `handoffs`.

**Rationale**: Recorded in full in `spec.md` Assumptions — merging returns a value the Desk must
keep working with, so the conversation must stay put; remediation transfers the operator to a
different job. `handoffs` moves conversation ownership, `as_tool` does not, and that is precisely
the distinction being graded.

**Alternatives considered**: Both as tools (rejected: remediation would return a proposal as a
value rather than addressing the operator, which is not what "proposes the patch directly to the
user" describes). Both as handoffs (rejected: the Desk would lose control of its own report
assembly).

## 6. Structured output and the list wrapper

**Decision**: Reviewer `output_type` is `list[Finding]`, and the wrapper object the SDK generates
is expected and explained rather than worked around.

**Rationale**: Strict schemas must be objects at the root, so a list root is wrapped in an object
with a single `response` key, while the value returned in `final_output` is still a plain Python
list. FR-3's "done when" requires pointing at that wrapper and explaining it, so the plan treats
it as a documented feature of the boundary rather than a surprise.

**Alternatives considered**: Wrapping the list in a hand-written container model (rejected: it
adds a second wrapper on top of the SDK's, so two objects must be explained instead of one). A
single finding per call (rejected: FR-3 requires a list).

## 7. Context passing

**Decision**: `ReviewContext` as a dataclass passed into every run and read by tools as
`RunContextWrapper[ReviewContext]` — the wrapper parameter being excluded from the generated
tool schema.

**Rationale**: FR-2 forbids the context appearing in prompt text, and the schema exclusion is the
mechanism that makes the prohibition enforceable: a repository name in a prompt is invisible to
the type system, whereas a tool reading it from the wrapper is typed and greppable.

**Alternatives considered**: Serialising the context into the system prompt (rejected: it is the
thing being tested against). Module-level globals (rejected: `clone()` and concurrent runs share
state, and three reviewers mutating a global is a race, not a design).

## 8. Guardrail placement

**Decision**: An `@output_guardrail` on the report path, with
`OutputGuardrailTripwireTriggered` caught in the pipeline and reported as a refusal.

**Rationale**: FR-8 requires the finished report to be inspected and the program not to crash.
The guardrail receives the output *after* the model has already produced it — so the spend has
already happened when the tripwire fires, which is the viva question about what had already been
paid for. Catching rather than letting the exception propagate is what turns a crash into a
refusal.

**Alternatives considered**: A post-hoc string scan in the pipeline (rejected: nothing binds it to
the SDK's output boundary, and there is no tripwire to point at). Filtering the diff before the
model sees it (rejected: FR-8 is explicitly about the output side, and the brief's coverage table
says "guardrails — FR-8 (output side)"; input-side redaction would also hide from the security
reviewer exactly what it is meant to find).

## 9. Ledger mechanism

**Decision**: A custom trace processor, registered once at startup, appending one line per
completed run to `ledger.jsonl`.

**Rationale**: FR-11 requires registration at startup and that no agent definition mentions the
ledger. A trace processor sits outside the agent graph, receives run events, and can be removed by
deleting a single registration — which is exactly FR-11's "done when" test. It also explains why
the ledger holds more lines than there are reviewers.

**Alternatives considered**: A custom `Runner` subclass (rejected: it would have to be passed at
every call site, so the ledger would be mentioned in code that should not know about it). Writing
from inside the hooks (rejected: hooks are attached to agents, violating "no agent definition
mentions it").

## 10. Streaming to the interface

**Decision**: Streamed runs whose events are iterated as they arrive, awaited from the Chainlit
page, with the report and context held in session state.

**Rationale**: FR-12 needs findings visible before completion, and it explicitly warns against the
synchronous variant — so the handler awaits. Session state holds the context so a second diff
reuses it rather than rebuilding it.

**Alternatives considered**: Polling a completed result (rejected: nothing appears until the end,
which fails FR-12's first acceptance scenario).

## 11. Turn ceiling

**Decision**: 8 turns per reviewer.

**Rationale**: The floor is three turns (forced ruleset read, a diff-chunk read, the finding
pass), so 8 leaves room for one re-read and one retry without approaching the ceiling in normal
operation, while still bounding a reviewer that loops on a tool. Full reasoning is in `plan.md`
under Decided Numbers.

**Alternatives considered**: Leaving the SDK default in place (rejected: FR-9 requires a chosen
ceiling and a stated reason, and an inherited default cannot be defended). A very low ceiling such
as 3 (rejected: a single retry would terminate the review and produce a spurious partial result).

## 12. Credential loading

**Decision**: `python-dotenv`, loading the repository-root `.env` at import of the config module,
with `require_env("OPENAI_API_KEY")` as the first statement of the entry point. A committed
`.env.example` names the variable without a value.

**Rationale**: NFR-1 requires keys in a gitignored `.env`, a missing key to fail at startup with
one sentence, and no stack trace. Loading at import guarantees the value is present before any
client is constructed, and checking with a helper that prints one sentence and exits non-zero is
what turns a `KeyError` traceback into a sentence. `.env.example` documents the variable without
ever carrying a real value.

**Alternatives considered**: Reading `os.environ["OPENAI_API_KEY"]` directly (rejected: a missing
key raises `KeyError`, producing exactly the traceback NFR-1 forbids). Parsing `.env` by hand
(rejected: reinvents quoting and comment handling for no gain). Relying on the shell environment
alone (rejected: nothing then keeps the key out of the shell history and out of the repo, which is
the point of `.env`).
