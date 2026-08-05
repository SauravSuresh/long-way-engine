# Rung 4, Option C — Concurrent link checker

**Concept:** Worker pools, bounded parallelism, cancellation, races.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Bookmarks rot — links die over time — and checking each one serially over
HTTP is slow once you have hundreds. You want a checker that fires
requests across multiple workers at once and tells you, in one run, which
links in a list are still alive.

## Situation
You've got a growing bookmarks file, maybe from rung 2, and you want to
know which links are dead before you keep piling more on top.

## Scope
- Checks a list of URLs (from a file, one per line, or another real
  source such as rung 2's bookmark store) and reports the status of each:
  reachable, broken, or timed out.
- Checks run across a bounded number of concurrent workers, not one
  goroutine per URL.
- Progress is visible while running (e.g. checked so far, out of total).
- Every check carries its own context timeout — a stalled server produces
  a timed-out result for that URL, not a hang for the whole run.
- An individual URL's outcome (404, timeout, connection refused) is a
  per-URL result to record, never a fatal error that stops the run. A
  genuinely fatal error — such as the input URL list being unreadable —
  cancels the run immediately instead of proceeding with no valid work to
  do.

## Non-goals
- No fixing or updating broken links automatically.
- No crawling beyond the given URL list.
- No content diffing beyond HTTP status (detecting rot, not rewrites).
- No GUI.

## How it should NOT work
- Never spawns a number of goroutines that scales with URL count instead
  of a bounded worker count.
- Never lets one slow or stalled URL block or delay the checking of the
  others.
- Never treats an individual URL's HTTP failure as a run-aborting error —
  that outcome is the very thing being measured.
- Never keeps running after a genuinely fatal error (e.g. an unreadable
  input file) instead of cancelling immediately.
- Never produces a race-detector warning under concurrent access to
  shared results or progress state.

## Acceptance
- Run against a mocked set of URLs (`httptest` servers) with a known mix
  of OK, 404, and hanging responses; output correctly classifies each.
- Concurrency is demonstrably bounded, verified by test.
- Progress output is visible during a run over many URLs.
- A hanging/slow URL times out per its own context deadline without
  delaying the other checks, verified by test.
- An unreadable input file (fatal error) cancels the run immediately
  without checking any URLs, verified by test.
- An individual URL's failure never cancels checking of the remaining
  URLs, verified by test.
- `go test -race ./...` clean.
- `go test ./...` and `go vet ./...` clean.
- README with install and usage examples.
- ADR names a real consumer: your rung 2 bookmarks, or another real URL
  list, checked for real.

## Starting nudge
Spin up a handful of `httptest` servers with different behaviors (200,
404, an artificial delay past your timeout) and point the checker at all
of them in one run before writing the concurrency code — the mix forces
you to decide whether one bad URL should ever touch the others.

## ADR question
Channels vs errgroup vs semaphore — pattern and why.
