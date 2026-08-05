# Rung 10, Option A — Signed webhook receiver + replay hammer test

**Concept:** At-least-once delivery is the world's default — survive it.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Your lab service, carried forward from rungs 6–9, currently has no way
to receive signed external events at all. You're going to need exactly
this pattern for real once the platform starts taking Razorpay payments
— so you build and hammer-test it here first, against a simulated
payment provider, on the service you already run.

## Situation
You simulate a payment provider firing the same "payment succeeded"
webhook at your service ten times in a row, because that's what actually
happens on the internet when a provider doesn't get the acknowledgment
it expects. By the tenth delivery, your service has recorded the payment
exactly once.

## Scope
- A webhook receiver endpoint on your lab service that verifies an
  HMAC (or equivalent) signature on every incoming request, rejecting
  unsigned or incorrectly-signed payloads before any processing runs.
- Every validly signed webhook is stored — raw payload plus delivery id
  — before any processing logic runs, so a crash between receipt and
  processing loses nothing.
- Replaying the identical webhook delivery 10 times produces exactly
  one effect (for example, one recorded payment), verified by test.
- Out-of-order deliveries are tolerated — a later event followed by an
  earlier one for the same subject doesn't corrupt state.
- A replay-hammer test harness fires the same signed payload at the
  endpoint repeatedly, simulating a real provider's retry behavior.

## Non-goals
- No real payment provider integration — this is a payment simulator,
  not live Razorpay.
- No webhook management UI.
- No support for multiple signature schemes at once.
- No automatic forwarding of received events to a third system.

## How it should NOT work
- Never processes a webhook whose signature doesn't verify.
- Never records the same delivery's effect more than once, no matter
  how many times it's replayed.
- Never a crash between "received" and "processed" silently drops the
  event.
- Never assumes deliveries arrive in the order they were sent.

## Acceptance
- A test sends a payload with an invalid or missing signature and
  asserts it is rejected (4xx) without reaching processing logic.
- The replay-hammer test fires the identical signed payload 10 times
  and asserts exactly one resulting effect.
- A test interrupts the process between the store and process steps and
  shows the stored-but-unprocessed webhook is picked up and processed
  exactly once on restart.
- An out-of-order test delivers two related events in reverse order and
  asserts the final state is correct either way.
- `go test ./...` and `go vet ./...` clean; README documents how to
  generate a valid test signature.
- The ADR states the idempotency key design: who supplies it, where it
  lives, and when it expires.

## Starting nudge
Build the replay-hammer test harness before the endpoint itself — a
small script or test that can fire the same signed payload N times is
what you'll run against every version of this endpoint as you build it,
and it's the thing that catches double-processing before it ships.

## ADR question
Idempotency key design — who supplies it, where does it live, when does it expire?
