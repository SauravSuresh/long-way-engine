# Rung 2, Option A — Append-only key-value store CLI

**Concept:** File formats, atomic writes, recovery. Data survives `kill -9`.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Scripts and small tools constantly need a place to durably stash a few
key-value pairs without pulling in a database. You want a CLI-backed
store you can trust: if the process gets killed mid-write, nothing you'd
already committed goes missing.

## Situation
You're scripting something that tracks state between runs — a key per
item, a value that changes over time. Midway through a batch of writes,
your machine loses power. You restart the script and the store comes back
with every write that had actually completed, and nothing else.

## Scope
- CLI operations: `kv set <key> <value>`, `kv get <key>` (prints the
  value or a clear "not found" and exits non-zero), `kv delete <key>`.
- On startup, the full key state is rebuilt by replaying the on-disk log
  — no separate index file is trusted as the source of truth.
- A `kv compact` command rewrites the log to hold only current state,
  measurably shrinking the file after repeated overwrites/deletes.
- A simulated kill mid-write leaves the store recoverable on restart, with
  every write that had fully landed still present.
- A truncated/corrupted tail of the log is detected and discarded on
  startup without losing the valid entries before it.

## Non-goals
- No server or network access — a local CLI operating on a local file.
- No concurrent multi-process writers.
- No secondary indexes, range queries, or TTL/expiry.
- No encryption.

## How it should NOT work
- Never loses a write that had already been durably committed before a
  simulated `kill -9` mid-write.
- Never treats a corrupted/truncated tail record as fatal — it should
  discard the bad tail and recover the valid entries before it, not
  refuse to start or wipe the whole store.
- Never returns a stale or wrong value for a key after compaction.

## Acceptance
- `kv set foo bar` followed by a fresh process invocation of `kv get foo`
  prints `bar` — state rebuilt from the file, not carried in memory.
- A kill-mid-write test simulates a process kill during a write and shows
  the store recovers cleanly with all prior committed entries intact.
- A corrupt-file test truncates/corrupts the tail of the log and shows the
  store starts cleanly, retaining every entry before the corruption.
- `kv compact` measurably shrinks the file after many overwrites/deletes
  of the same keys, verified by test.
- A benchmark of `kv get` read throughput is committed (`go test -bench`).
- `go test ./...` and `go vet ./...` clean.
- README with install and usage examples.
- ADR names a real consumer (per the rung rules: you, operating it).

## Starting nudge
Before writing any storage code, script a `kill -9` against a toy writer
to see what a half-written record actually looks like on disk. That's the
exact shape of corruption your recovery code has to tolerate, and it's
cheaper to learn now than to guess.

## ADR question
Log vs snapshot vs rewrite-whole-file — and when do you fsync?
