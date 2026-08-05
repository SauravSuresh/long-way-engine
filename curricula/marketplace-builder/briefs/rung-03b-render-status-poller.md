# Rung 3, Option B — Render-status poller

**Concept:** Timeouts, retries with backoff, testing without the network.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
At the previz startup, renders run long on a render service, and the team
finds out they're done (or failed) by manually refreshing a dashboard.
You want a poller that watches a job's status on your behalf and notifies
the moment it finishes, so nobody babysits a progress bar.

## Situation
You kick off an overnight render and go to bed. If it fails at 2am,
nobody knows until someone opens the dashboard at 9. You want something
that polls the render service for you and tells you — pass or fail — the
moment the job reaches a terminal state.

## Scope
- Given a render job identifier, polls the render service's status
  endpoint on an interval until the job reaches a terminal state (done or
  failed).
- Fires a notification the moment the job finishes, through one channel
  you control (stdout, webhook, or local notification), with a clear
  pass/fail result.
- Every poll request carries a context timeout; a stalled render service
  produces a message for that poll, not a hang for the whole run.
- Transient failures during polling (5xx, connection errors) are retried
  with backoff and are not treated as job failure.
- A fully unreachable render service is reported as a clear message, not
  a crash, and polling can be resumed.

## Non-goals
- No dashboard or UI.
- No watching multiple jobs concurrently in this version.
- No control over the render farm (starting or cancelling jobs).
- No historical job-log storage.

## How it should NOT work
- Never reports a job as failed because of a transient network blip
  during polling.
- Never hangs indefinitely on a single stalled poll request.
- Never stops polling silently without reporting why.
- Never crashes with a stack trace when the render service is unreachable.

## Acceptance
- A mocked status sequence (running → running → done) ends the poll loop
  and fires the done notification exactly once.
- A mocked 500 during a poll is retried with backoff and does not end the
  loop or report job failure.
- A mocked slow/hanging poll request times out per the context deadline
  and is treated as retryable, not a job failure.
- A simulated fully unreachable service produces a one-line message and a
  clean exit or retry — not a stack trace.
- All render-service calls in tests go through `httptest` (or
  equivalent) — `go test ./...` needs no real network or render service.
- `go test ./...` and `go vet ./...` clean.
- README with install and usage examples.
- ADR names the consumer: your team, notified for real when a render
  finishes.

## Starting nudge
Fake the render service's status endpoint with `httptest` before touching
the real one — script the exact state sequence (queued, running, done)
and the exact failure modes (timeout, 500, connection refused) you need
to survive, and let each drive a test before the polling code exists.

## ADR question
How do you make network code testable?
