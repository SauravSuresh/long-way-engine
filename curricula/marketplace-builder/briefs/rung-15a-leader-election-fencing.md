# Rung 15, Option A — Leader election with fencing tokens

**Concept:** More than one node, and the truth gets expensive.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
As soon as more than one instance of a service can run, "only one
process does this" invariants break silently unless something enforces
it across nodes and survives a crash — not just a process that promises
to behave, but a resource that refuses writes from anyone but the real
leader.

## Situation
You run two instances of a service for redundancy. One gets
network-partitioned instead of cleanly dying, and its replacement gets
elected while the old one is still alive and still convinced it's in
charge. You need proof — not a hope — that the old one physically can't
corrupt shared state from here.

## Scope
- Multiple candidate processes race for leadership; exactly one holds it
  at a time.
- Leadership is a lease with expiry and renewal — a leader that stops
  renewing loses leadership automatically, with no manual step.
- Every leader action carries a fencing token, monotonically increasing
  across leadership changes.
- A protected resource (e.g. a shared state write) rejects a write
  carrying a stale fencing token — enforced by the resource itself, not
  trusted from the caller.
- Killing the current leader results in another candidate taking over
  within a bounded, documented time.
- The old leader, even if still partially alive after losing leadership,
  cannot successfully write to the protected resource.

## Non-goals
- No general-purpose distributed lock library — this is scoped to the
  leader-election use case.
- No automatic data migration between leadership changes.
- No cross-datacenter or multi-region concerns.
- No support for more candidates coordinating than the leader role
  itself requires.

## How it should NOT work
- Never two nodes both believe they're leader and both successfully
  write to the protected resource at the same time.
- Never a crashed leader's lease is held forever with no other candidate
  able to take over.
- Never a fencing token is reused or goes non-monotonic across
  leadership changes.
- Never "the old leader can't corrupt state" rests on the old leader
  behaving nicely instead of the resource enforcing the token.

## Acceptance
- A test starts 3+ candidate processes/goroutines and asserts exactly
  one holds leadership at any point in time.
- A test kills (or stops lease renewal for) the current leader and
  asserts another candidate becomes leader within the documented
  lease/timeout bound.
- A test captures the fencing token issued to a leader, lets a new
  leader take over, then has the old leader attempt a write with its
  stale token — the resource rejects it.
- A test asserts fencing tokens strictly increase across successive
  leadership changes and never repeat.
- `go test ./...` and `go vet ./...` clean; README explains the lease
  and fencing-token mechanism and how to run the kill-the-leader demo.

## Starting nudge
Build fencing-token enforcement on the protected resource first — one
function that rejects a write if its token is lower than the highest
one already seen — before writing any election logic at all. That
function is what actually prevents corruption, and it's unit-testable
in isolation with fabricated tokens, no election machinery required.
Pull DDIA's replication chapter if the lease-vs-token distinction gets
fuzzy.

## ADR question
What guarantee does this system actually give you across nodes, and
what did it cost — latency, availability, complexity — to earn it?
