# Rung 5, Option C — TTL + LRU cache library

**Concept:** API design for strangers — the ADR discipline aimed at code.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Multiple projects end up needing a small in-memory cache with expiry and
a size bound, and each one gets its own bespoke map-with-a-mutex. You
want one trustworthy, published library instead of reinventing it per
project.

## Situation
You're building a service and want to cache lookups with a TTL so you're
not hitting the underlying store on every request. You reach for the
cache library you published instead of writing another one-off cache.

## Scope
- A documented, importable cache combining a max-size LRU eviction policy
  with a per-entry TTL expiry.
- Safe for concurrent use from multiple goroutines without the caller
  adding external locking.
- A documented public API with doc comments and at least one runnable
  example demonstrating typical usage.
- A zero-value or documented-default instance behaves sanely: usable out
  of the box, or the docs are explicit about required construction.
- Tests are deterministic and control time via an injectable/fake clock,
  not real sleeping, for TTL behavior.
- Benchmarks for Get/Set under concurrent access are included and
  documented.
- Published as a real, versioned package: tagged semver, resolvable via
  `go get` (or the equivalent registry for your language).

## Non-goals
- No persistence to disk.
- No distributed or shared cache across processes.
- No cache-warming or preloading framework.
- No built-in metrics/telemetry export.

## How it should NOT work
- Never returns an expired entry as if it were still valid.
- Never exceeds its configured max size under concurrent writes.
- Never races under `-race` when accessed concurrently from multiple
  goroutines.
- Never blocks a test by literally sleeping to wait out a TTL.

## Acceptance
- A documented example (a runnable `Example...` test or equivalent)
  compiles and runs, showing real usage end to end.
- Zero-value/default-construction behavior is tested explicitly and
  matches the docs.
- Fake-clock tests verify TTL expiry (an entry is a miss exactly when its
  TTL has elapsed) and LRU eviction (size stays bounded, least-recently-
  used evicted first) — no `time.Sleep` anywhere in the test suite
  (grep-verifiable).
- `go test -race ./...` clean under concurrent Get/Set from multiple
  goroutines.
- Benchmarks for concurrent Get/Set are committed (`go test -bench`).
- `go vet ./...` clean.
- The package carries a real semver tag and resolves via `go get` (or the
  equivalent) from a clean environment.
- README/package docs a stranger could follow to install and use it
  without reading the source.
- At least one later rung of your own ladder actually imports and uses
  this library.

## Starting nudge
Write the fake-clock test for "an entry set with a 1-minute TTL is a miss
after the clock advances past it" before writing any storage code — the
TTL-vs-LRU interaction is the part worth deciding deliberately rather
than by accident of implementation order.

## ADR question
What does a good library API owe its users? Polyglot invitation: doing
this in a second language doubles the API-design lesson — argue it in
the ADR if tempted.
