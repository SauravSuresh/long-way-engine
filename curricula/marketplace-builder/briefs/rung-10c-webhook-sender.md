# Rung 10, Option C — Webhook sender with retries and signing

**Concept:** At-least-once delivery is the world's default — survive it.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Every rung so far in this arc has been about receiving webhooks — now
build the other side of the contract: a sender that reliably delivers
signed events to a subscriber's URL. Your own platform will eventually
need to notify integrators the same way providers notify you, and that
delivery discipline has to exist somewhere first.

## Situation
An event fires that a subscriber cares about. Their endpoint happens to
be down for thirty seconds when you try to deliver it. Instead of that
notification being lost, your sender retries with backoff, the
subscriber comes back up, and the delivery lands — with a signature the
subscriber can verify came from you.

## Scope
- Register a subscriber URL for an event type.
- On a triggering event, deliver a signed payload (HMAC over the body
  with a shared secret) to the subscriber.
- Failed deliveries — connection failure, 5xx, timeout — are retried
  with backoff up to a bounded max-attempts.
- Delivery is at-least-once: the sender never silently gives up without
  recording that it did.
- Each delivery carries a stable id the subscriber can use to dedupe on
  their end.

## Non-goals
- No subscriber-side idempotency enforcement — that's the receiver's
  job, not this sender's.
- No webhook management UI.
- No arbitrary custom retry schedule per subscriber.
- No delivery to more than one URL per event/subscriber pairing.

## How it should NOT work
- Never sends a payload without a verifiable signature.
- Never retries a dead subscriber forever with no bound.
- Never a failed delivery silently vanishes with no record it was
  attempted.
- Never reuses the same delivery id for two different payloads.

## Acceptance
- A test delivers to a subscriber double that fails N times then
  succeeds, and asserts retries happen with increasing backoff and the
  delivery eventually lands.
- A test delivers to a subscriber that never succeeds and asserts
  retries stop at the documented max-attempts, with the failure
  recorded rather than lost.
- A test verifies the delivered payload's signature independently,
  proving the subscriber could validate it came from this sender.
- A test asserts each delivery carries a stable id, unique per
  (event, subscriber).
- A test asserts a triggering event is durably recorded (store) before
  any send attempt is made, and a crash right after that record — before
  the first send attempt completes — leaves the delivery recoverable and
  still sent exactly once on recovery, not skipped.
- A test replays a subscriber's ack for a delivery out of order (a later
  delivery's ack arrives before an earlier one's, or the same ack
  arrives twice) and asserts delivery/retry state isn't corrupted by
  it — the sender's bookkeeping per delivery id stays consistent.
- `go test ./...` and `go vet ./...` clean; README shows how a
  subscriber verifies the signature.

## Starting nudge
Write the subscriber test double first — an HTTP handler in your test
suite that fails a configurable number of times before succeeding — and
build the retry/backoff loop against it before wiring in a real trigger
source. That double proves the backoff and give-up behavior without
waiting on real network flakiness.

## ADR question
Idempotency key design — who supplies it, where does it live, when does it expire?
