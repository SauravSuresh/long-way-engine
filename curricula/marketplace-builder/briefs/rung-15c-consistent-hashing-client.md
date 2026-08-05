# Rung 15, Option C — Consistent-hashing client over mini-redis nodes

**Concept:** More than one node, and the truth gets expensive.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Splitting data across multiple nodes with plain modulo hashing means
adding or removing a node reshuffles almost everything you stored. You
want a client that spreads keys across several small stores and adds
capacity without an all-keys migration every time.

## Situation
You're running 3 mini-redis nodes (rung 14's protocol, or any
RESP-compatible store) and need a fourth for headroom. Instead of nearly
every existing key moving to a new node, only the keys that were always
going to land near the new node's position move — you can watch it
happen and count them.

## Scope
- A client library assigns keys to one of N nodes using consistent
  hashing, not modulo-N.
- GET/SET (or your chosen operations) route through the client to the
  correct node based on the hash ring.
- Adding a 4th node to a running 3-node ring remaps only ~1/N of
  existing keys — measured and proven, not asserted.
- Removing a node likewise remaps only the keys that were owned by the
  removed node, not the whole keyspace.
- A node being unreachable is handled by a documented, explicit policy
  (retry, error, or skip) — never a silent wrong answer.

## Non-goals
- No automatic node failure detection or self-healing — manual add/remove
  is fine.
- No automatic data migration performed by the client itself, unless
  your ADR argues for it.
- No replication across nodes — one node owns each key.
- No support for node types other than the mini-redis nodes this rung
  targets.

## How it should NOT work
- Never adding a node remaps close to 100% of keys — that's the
  modulo-hashing failure this rung exists to avoid.
- Never two independently constructed client instances disagree about
  which node owns a given key at the same ring state.
- Never a request routes to the wrong node and silently returns a miss
  instead of the actual key's value.
- Never the ring's key-to-node mapping is nondeterministic between runs
  with the same node set.

## Acceptance
- A test populates N keys across a 3-node ring, adds a 4th node, and
  measures the fraction of keys that moved — asserts it lands close to
  the theoretical ~1/N, within a documented tolerance, not close to
  100%.
- A test removes a node and asserts only that node's keys were
  remapped, the rest unaffected.
- A test asserts two independently constructed client instances with the
  same node set agree on every key's owning node.
- A test SETs then GETs through the client against a live 3-node
  mini-redis setup and gets the correct value back, proving requests
  actually route correctly, not just that the ring math checks out.
- `go test ./...` and `go vet ./...` clean; README explains the ring
  construction and shows the remap measurement.

## Starting nudge
Build the ring's key-to-node mapping as a pure function you can unit
test against a fixed set of node names — the ~1/N remap property is a
property of the ring math itself, provable before any network client
exists. DDIA's partitioning chapter covers consistent hashing directly
if you want the reference while implementing it.

## ADR question
What guarantee does this system actually give you across nodes, and
what did it cost — latency, availability, complexity — to earn it?
