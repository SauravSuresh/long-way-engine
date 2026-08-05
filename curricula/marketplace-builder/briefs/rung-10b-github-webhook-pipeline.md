# Rung 10, Option B — GitHub webhook to notify/deploy pipeline

**Concept:** At-least-once delivery is the world's default — survive it.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
You want to know the moment CI fails or a PR gets reviewed on your own
repos, without polling GitHub the way rung 3's poller does — a webhook
pushed to you the instant it happens, driving a real notify or deploy
action.

## Situation
A CI run fails on a repo you care about at 11pm. Instead of finding out
the next morning because nothing was watching, GitHub's webhook lands on
your receiver within seconds, your pipeline verifies it, and you get
notified before you've closed your laptop.

## Scope
- A receiver that verifies GitHub's HMAC signature
  (`X-Hub-Signature-256`) on every delivery, rejecting anything that
  doesn't verify before any handling runs.
- Every validly signed delivery is stored before any notify/deploy
  action runs, so a crash between receipt and action loses nothing.
- Replaying the same GitHub delivery id 10 times produces exactly one
  notify/deploy action, not ten.
- Out-of-order deliveries for the same subject (for example, a
  "closed" event arriving before an earlier "opened" for the same PR)
  don't corrupt tracked state.
- Triggers a real action — a notification to you, or a deploy step —
  for at least one real GitHub event type you actually use.

## Non-goals
- No support for every GitHub event type — pick the ones you use.
- No GitHub App/OAuth setup beyond a webhook secret.
- No web UI to browse received events.
- No unbounded retry-forwarding of failed downstream notifications —
  any retry is bounded and documented.

## How it should NOT work
- Never acts on a payload with a bad or missing signature.
- Never sends the same notification twice for one GitHub delivery id,
  even under replay.
- Never a crash between receipt and action silently drops the event.
- Never assumes GitHub delivers events in the order they were sent.

## Acceptance
- A test sends a payload with an invalid signature and asserts
  rejection before it reaches handler logic.
- A replay test resends the same delivery id 10 times and asserts
  exactly one resulting notify/deploy action.
- A test interrupts the process between store and action and shows the
  event survives and is processed exactly once.
- An out-of-order test delivers two related events on the same PR in
  reverse order and asserts correct final state.
- `go test ./...` and `go vet ./...` clean; README shows how to
  configure the webhook secret against a real GitHub repo.
- The ADR states the idempotency key design: who supplies it, where it
  lives, and when it expires.

## Starting nudge
Point a real GitHub repo's webhook settings at a local tunnel (ngrok or
similar) early and let real deliveries hit your endpoint while you
build. GitHub's actual retry and delivery behavior is stranger than
anything you'd invent in a test, and it's free ground truth for your
idempotency logic.

## ADR question
Idempotency key design — who supplies it, where does it live, when does it expire?
