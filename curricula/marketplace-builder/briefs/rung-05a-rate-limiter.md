# Rung 5, Option A — Rate limiter library

**Concept:** API design for strangers — the ADR discipline aimed at code.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Every service you build ends up needing to bound the rate of some
operation — API calls, requests to your own service — and you keep
rewriting ad hoc limiting logic each time. You want one small, well
documented library you can pull into any project and trust without
reading its source.

## Situation
You're wiring up an API and need to cap requests per API key. Instead of
hand-rolling a limiter again, you `go get` your own rate-limiter package,
read its doc comment, and it does exactly what the docs say — no
surprises, no reading the implementation to find out how it behaves at
its zero value.

## Scope
- A token-bucket rate limiter, usable per key — independent limits for
  each identifier such as an API key or IP address.
- A documented, importable public API (package doc plus doc comments on
  every exported type and function) that a stranger can use correctly
  from the docs alone.
- At least one runnable example demonstrating typical usage.
- A zero-value or documented-default instance behaves sanely: either it's
  usable out of the box, or the docs are explicit about required
  construction — never a silent no-op or a panic on first use.
- Tests are deterministic and control time via an injectable/fake clock
  rather than sleeping.
- Published as a real, versioned package: tagged and resolvable via
  `go get`/pkg.go.dev (or the equivalent registry for your language).

## Non-goals
- No distributed or cross-process rate limiting — single-process only.
- No built-in HTTP middleware wrapper; a plain library, bring your own
  integration.
- No persistence of bucket state across restarts.
- No configuration file format — construction is through the API.

## How it should NOT work
- Never blocks a test suite by literally sleeping to wait out a rate
  window.
- Never panics or silently does nothing when used at its zero value
  without documented construction.
- Never allows a burst past the configured capacity, and never
  permanently locks a key out past its refill rate.
- Never exposes internal state in a way that lets a caller corrupt it
  without going through the public API.

## Acceptance
- A documented example (a runnable `Example...` test or equivalent)
  compiles and runs, showing real usage end to end.
- Zero-value/default-construction behavior is tested explicitly and
  matches what the docs say.
- Fake-clock tests verify token refill, burst capacity, and per-key
  independence — no `time.Sleep` anywhere in the test suite
  (grep-verifiable).
- `go test ./...`, `go vet ./...`, and a doc-coverage check (e.g.
  `golint`/equivalent) clean.
- The package carries a real semver tag (e.g. `v0.1.0`) and resolves via
  `go get` (or the equivalent registry) from a clean environment.
- README/package docs a stranger could follow to install and use it
  without reading the source.
- At least one later rung of your own ladder actually imports and uses
  this library — not just plans to.

## Starting nudge
Write the example test you'd want to read as a stranger before writing
the limiter itself — an example that shows construction, a call that
succeeds, and a call that's rejected — and let that be the first thing
that has to compile.

## ADR question
What does a good library API owe its users? Polyglot invitation: doing
this in a second language doubles the API-design lesson — argue it in
the ADR if tempted.
