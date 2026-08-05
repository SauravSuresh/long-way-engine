# Rung 3, Option C — GitHub watcher

**Concept:** Timeouts, retries with backoff, testing without the network.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
You've got your own GitHub repos and want to know the moment a PR gets
reviewed or CI finishes, without tab-switching to GitHub every ten
minutes. You want a watcher that polls the API on your behalf and tells
you only when something you care about actually changes.

## Situation
You've pushed a PR to one of your own repos and want to know the second
CI finishes or someone leaves a review. You run the watcher, keep working,
and get told once, right when it happens — not on every poll.

## Scope
- Watches a given PR (or repo) via the GitHub API and detects new review
  comments and/or check-run status changes since the last poll.
- Notifies through one channel you control (stdout, webhook, or local
  notification) the moment a watched event occurs, without re-notifying
  for the same event on a later poll.
- Every API call carries a context timeout; a stalled GitHub API produces
  a message for that call, not a hang for the whole run.
- Rate-limit responses and transient 5xx errors are retried with backoff,
  distinct from a genuine auth/permission failure.
- An unreachable API is reported as a clear message, not a crash.

## Non-goals
- No posting comments or reviews back to GitHub.
- No watching more than one PR/repo in this version.
- No webhook-based (push) delivery from GitHub — polling only.
- No history-browsing UI.

## How it should NOT work
- Never re-notifies for an event it already reported.
- Never treats a GitHub rate-limit response the same as a hard failure —
  it backs off and keeps going.
- Never hangs indefinitely on a stalled request.
- Never crashes with a stack trace when GitHub is unreachable.

## Acceptance
- A mocked sequence of check-run/review API responses (no change → new
  review → CI passed) fires exactly one notification per new event, with
  no duplicate notification on a rerun against the same mocked state.
- A mocked rate-limit response is retried with backoff rather than
  aborting the watch.
- A mocked slow/hanging request times out per the context deadline and is
  treated as retryable.
- A simulated unreachable GitHub API produces a one-line message, not a
  stack trace.
- All GitHub API calls in tests go through `httptest` (or equivalent) —
  `go test ./...` needs no real network access or GitHub token.
- `go test ./...` and `go vet ./...` clean.
- README with install and usage, including how to supply a GitHub token.
- ADR names a real consumer: you, watching your own repos.

## Starting nudge
Record a couple of real GitHub API responses for a PR you own (check-runs,
reviews) and replay them through `httptest` as your fixtures — more
honest than hand-written JSON, and it shows exactly which fields you need
to diff between polls to detect "new."

## ADR question
How do you make network code testable?
