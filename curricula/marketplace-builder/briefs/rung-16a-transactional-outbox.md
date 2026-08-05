# Rung 16, Option A — Transactional outbox

**Concept:** Correctness under failure — the platform's operations rehearsal.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
The rental marketplace you're building toward will need flows where a DB
commit and a message to another service both have to happen, or neither
meaningfully has — a crash between "the transfer is recorded" and "the
other service was told about it" can't be allowed to lose or double the
event.

## Situation
A deposit transfer commits to your ledger, and right as you're about to
publish the event telling the other service about it, the process gets
killed. The transfer already happened — if that message never fires,
the other side never finds out, and from its point of view the money
just vanished.

## Scope
- Two services: one commits a money-ish transfer/state change, the other
  consumes an event describing it.
- An outbox table is written in the same database transaction as the
  state change — the commit is atomic across both.
- A separate relay reads the outbox and publishes the event to the
  consuming service, marking it published only after successful
  delivery.
- A crash injected between the state-change commit and the publish step
  is survived: on restart, the event still gets published, not lost.
- The consuming service processes each event exactly once even if the
  relay redelivers it (a dedupe key on its end).

## Non-goals
- No full message broker (Kafka, etc.) required unless your ADR argues
  for it.
- No support for event types beyond the one transfer scenario.
- No multi-service saga or compensation logic.
- No real payment processor integration — money-ish, not real money.
- No new rung follows this one — this is inside the last rung of the
  ladder; from here, build time moves to the platform's own milestones.

## How it should NOT work
- Never a crash between commit and publish loses the event permanently.
- Never the relay delivers the same event twice and the consumer
  double-applies it.
- Never the state-change commits without its outbox row, or vice versa
  — they're one transaction.
- Never "exactly once" is claimed without a crash-injection test proving
  it.

## Acceptance
- A test performs the transfer, commits, then kills the process before
  the publish step runs, restarts, and asserts the event is still
  published — nothing lost.
- A test asserts the state-change row and the outbox row are written
  atomically — a forced failure between them leaves neither committed,
  not one without the other.
- A test delivers the same event to the consumer twice (simulating relay
  redelivery) and asserts the consumer applies it exactly once (dedupe
  key checked).
- A test asserts a normal, non-crashed transfer flows end to end: state
  committed, event published, consumer applies it — observable on both
  sides.
- `go test ./...` and `go vet ./...` clean; README diagrams the two
  services and the outbox flow.
- ADR names the guarantee this gives you and what failure mode remains
  outside it.

## Starting nudge
Write the crash-injection test first — force the process to exit
between the commit and the publish step — before building the relay at
all. That test is the actual spec for "crash between commit and publish
loses nothing," and it should fail against a naive implementation before
you make it pass. Release It! is worth pulling once you see what
actually breaks.

## ADR question
What failure mode does this prove you can survive, and what failure
mode is still unguarded after it?
