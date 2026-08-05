# Rung 15, Option B — Replicated log, consensus-lite

**Concept:** More than one node, and the truth gets expensive.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
A single-node service is a single point of failure. Before ever reaching
for a real Raft library in the platform you're building toward, you want
to understand — by building a stripped-down version yourself — exactly
what a replicated log buys you, and exactly what it costs.

## Situation
One node in your 3-node cluster goes down mid-write. The other two still
have quorum, keep accepting writes, and when the downed node comes back
it catches up to exactly what the majority already agreed on — no manual
reconciliation, no "which copy is right" guesswork.

## Scope
- 3 nodes maintain a replicated append-only log.
- A write is acknowledged to the client only after a majority of nodes
  have durably stored it.
- A minority-partitioned or crashed node does not block writes from
  proceeding on the majority.
- A node that was down or partitioned, once it rejoins, catches its log
  up to match what the majority already committed.
- Convergence is proven by a test: after a simulated partition, writes,
  and rejoin, all 3 nodes' logs match up to the last committed entry.
- The ADR explicitly lists which real-Raft guarantees this
  implementation drops.

## Non-goals
- No full Raft (leader-election safety proofs, snapshotting, membership
  changes) — out of scope unless your ADR argues for it.
- No client-facing query routing or load balancing.
- No more than 3 nodes.
- No cross-datacenter latency modeling.

## How it should NOT work
- Never a write is acknowledged to the client before a majority durably
  has it.
- Never a minority partition is able to accept writes the majority never
  sees (split-brain).
- Never a rejoining node ends up with a log that diverges from the
  majority's committed entries instead of converging to them.
- Never the ADR claims Raft-equivalent safety without naming what was
  actually dropped to get there.

## Acceptance
- A test asserts a write is acknowledged only once ≥2 of 3 nodes have
  durably stored it: killing the 3rd node before it acks still succeeds
  the write; killing 2 of 3 blocks or fails the write rather than
  silently acking on 1.
- A test partitions one node, performs writes against the majority,
  heals the partition, and asserts the previously-partitioned node's log
  converges to match the majority's committed log.
- A test asserts a minority partition (1 of 3, isolated) cannot get its
  own writes acknowledged while separated from the majority.
- `go test ./...` and `go vet ./...` clean; README documents the
  replication protocol.
- ADR names every guarantee dropped versus real Raft (e.g. no leader
  election safety proof, no log compaction, no membership changes —
  whatever applies).

## Starting nudge
Get a single write acknowledged after a majority of 3 in-memory fakes
agree, with no networking involved at all, before wiring in real nodes
or a partition simulator. Ack-after-majority is the one invariant
everything else in this rung has to preserve. DDIA's replication chapter
is worth pulling when the convergence-vs-consistency vocabulary gets
slippery.

## ADR question
What guarantee does this system actually give you across nodes, and
what did it cost — latency, availability, complexity — to earn it?
