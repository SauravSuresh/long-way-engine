# Rung 2, Option B — Cash ledger CLI

**Concept:** File formats, atomic writes, recovery. Data survives `kill -9`.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Tracking your own spending with a spreadsheet or an app means friction
between "I just spent money" and "it's logged" — and a crash mid-save
shouldn't cost you an entry you already made. You want a CLI ledger you
can append to in seconds, that survives being killed mid-write, and that
can tell you what you spent in a given month.

## Situation
You've just paid for a gear rental. Before you forget the amount, you run
`ledger add` from your phone's terminal app or your laptop, right there.
Later, at month's end, you run a report and it matches what you actually
spent, entry for entry.

## Scope
- Appends a dated entry (amount, description, category) via a single CLI
  command: `ledger add -amount 1450 -desc "lens rental" -category gear`.
- A report command prints totals for a given month, broken down by
  category: `ledger report 2026-08`.
- On startup, the full ledger (every entry, running totals) is rebuilt by
  replaying the on-disk file — no separate index file is trusted.
- A simulated kill mid-append leaves prior entries intact and readable on
  restart.
- A truncated/corrupted tail of the file is detected and discarded on
  startup without losing the valid entries before it.

## Non-goals
- No multi-currency support or exchange-rate conversion.
- No budgets, alerts, or forecasting.
- No import from bank statements or other apps.
- No GUI or charts — text output only.

## How it should NOT work
- Never loses an entry that had already been durably appended before a
  simulated `kill -9` mid-write.
- Never treats a corrupted/truncated tail as fatal for the whole ledger —
  it discards the bad tail and keeps everything before it.
- Never produces a monthly total that doesn't match manually summing the
  surviving entries for that month.

## Acceptance
- `ledger add ...` followed by a fresh process invocation still shows that
  entry — state rebuilt from the file, not carried in memory.
- `ledger report 2026-08` against a known fixture prints the correct
  per-category and overall totals for that month.
- A kill-mid-write test simulates a process kill during an append and
  shows prior entries intact on restart.
- A corrupt-file test truncates/corrupts the tail and shows the ledger
  starts cleanly, retaining every entry before the corruption.
- A benchmark for generating a monthly report over a large number of
  entries is committed (`go test -bench`).
- `go test ./...` and `go vet ./...` clean.
- README with install and usage examples.
- ADR names the consumer: your actual spending, tracked for real.

## Starting nudge
Start logging your real spending in whatever format you land on from day
one — a ledger you're not actually using won't surface the recovery bugs,
and "my own money total is wrong" is a much better bug report than a
synthetic test.

## ADR question
Log vs snapshot vs rewrite-whole-file — and when do you fsync?
