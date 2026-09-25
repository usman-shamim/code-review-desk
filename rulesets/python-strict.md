# Review ruleset: python-strict
#
# This is the file FR-9 requires a reviewer to consult before producing findings.
# It is read through the run context, by identifier, never pasted into a prompt by the caller.
#
# Deleting this file must NOT fail the review: the reading tool returns a sentence instead.

## Severity definitions

- **critical** — the change introduces or exposes a credential, an injection path, or a
  destructive operation that runs without confirmation.
- **major** — the change breaks an existing contract, swallows an error, or leaves a security
  control unreachable on a reachable path.
- **minor** — the change is correct but harder to read or to maintain than it needs to be.

## What every reviewer must check

1. **Credentials** — no API key, token, password or private key appears as a literal. This is the
   rule the output guardrail enforces independently: if a finding quotes a credential, the whole
   report is refused, so describe the credential, never reproduce it.
2. **Errors** — an exception that is caught and discarded is a major finding. Name what the code
   loses by discarding it.
3. **Input at boundaries** — data from outside the process (argv, environment, files, the network)
   is validated before use, not assumed.
4. **Assertions that cannot fail** — a test that asserts a constant, or asserts nothing, is a major
   finding; it reports coverage the project does not have.

## Style rules

- Findings cite a file and a line. A finding without a line is a review note, not a finding.
- Report the smallest number of findings that fully describes the problem. One finding per issue,
  not one per reviewer.
