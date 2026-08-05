# Rung 5, Option B — Retry/backoff library

**Concept:** API design for strangers — the ADR discipline aimed at code.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Every network client you write from rung 3 onward needs retry-with-backoff,
and copy-pasting that logic into each project is how bugs sneak in. You
want one reusable, well documented library that gets retry semantics
right once, so every future project just imports it.

## Situation
You're wiring up another network client — polling an API for the third or
fourth time in this ladder — and instead of writing retry logic again,
you import the retry library you published, read its doc comment, and get
correct backoff-with-jitter behavior in a few lines.

## Scope
- A documented, importable retry function or type that wraps an operation
  with backoff between attempts, respecting a caller-supplied context for
  cancellation.
- Backoff includes jitter (delays are not identical/fixed across retries)
  and a configurable retry budget (max attempts and/or max total elapsed
  time).
- A documented public API with doc comments and at least one runnable
  example demonstrating typical usage.
- A zero-value or documented-default instance behaves sanely: usable out
  of the box, or the docs are explicit about required construction.
- Tests are deterministic and control time via an injectable/fake clock,
  not real sleeping.
- Published as a real, versioned package: tagged semver, resolvable via
  `go get` (or the equivalent registry for your language).

## Non-goals
- No built-in HTTP client wrapper — operates on any retryable function,
  bring your own I/O.
- No circuit breaker.
- No distributed or shared rate coordination across processes.
- No persistence of retry state across restarts.

## How it should NOT work
- Never blocks a test by literally sleeping through backoff delays.
- Never retries past the configured budget (attempts or elapsed time).
- Never ignores a cancelled context and keeps retrying anyway.
- Never panics or hangs on a retried function that always fails.

## Acceptance
- A documented example (a runnable `Example...` test or equivalent)
  compiles and runs, showing real usage end to end.
- Zero-value/default-construction behavior is tested explicitly and
  matches the docs.
- Fake-clock tests verify: jitter is present (delays differ across
  retries), the budget is honored (stops at max attempts or elapsed
  time), and a cancelled context stops retrying promptly — no
  `time.Sleep` anywhere in the test suite (grep-verifiable).
- `go test ./...` and `go vet ./...` clean.
- The package carries a real semver tag and resolves via `go get` (or the
  equivalent) from a clean environment.
- README/package docs a stranger could follow to install and use it
  without reading the source.
- At least one later rung of your own ladder actually imports and uses
  this library.

## Starting nudge
Write the fake-clock test for "a cancelled context stops retrying before
the budget is exhausted" before writing the retry loop — that's the
constraint most retry libraries get wrong, and pinning it down first
tells you what your clock/context seams need to look like.

## ADR question
What does a good library API owe its users? Polyglot invitation: doing
this in a second language doubles the API-design lesson — argue it in
the ADR if tempted.
