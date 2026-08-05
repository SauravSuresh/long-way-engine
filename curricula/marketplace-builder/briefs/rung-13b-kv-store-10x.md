# Rung 13, Option B — Make rung 2's KV store 10x faster

**Concept:** Profiling discipline — hypothesis, measurement, one fix.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Rung 2's append-only KV store was built for correctness, not speed, and
nobody has ever measured what it actually costs to use. You want a
disciplined pass — benchmark it, profile it, form a hypothesis, make one
change — with a 10x target you either hit or can explain precisely why
you didn't.

## Situation
You're about to lean on this KV store for something that actually
matters, and "it's probably fine" isn't good enough anymore. You run the
existing benchmark, pull the flamegraph, and the bottleneck isn't where
you assumed — it's an allocation in the hot path you'd never have
guessed without looking.

## Scope
- A Go benchmark suite (`go test -bench`) exercises the store's real
  operations (get/put/etc.), producing a reproducible before number.
- A pprof profile (CPU or memory) is captured during that benchmark and
  rendered as a flamegraph identifying the real hot path.
- A hypothesis is written down before touching code: which specific
  operation, allocation, or lock is the bottleneck, and why.
- Exactly one deliberate code change is made in response to that
  hypothesis.
- The identical benchmark is rerun post-fix; before/after numbers are
  committed side by side, reaching (or explaining a documented shortfall
  from) 10x.
- Rung 2's original test suite still passes after the fix.

## Non-goals
- No rewrite of the store from scratch.
- No new external dependency added just to "be fast" without profiler
  evidence pointing there.
- No bundling more than one change into "the fix."
- No trading away the durability/correctness rung 2 already tested for
  to gain speed.

## How it should NOT work
- Never a benchmark number is reported without the raw command/output
  needed to reproduce it.
- Never the fix breaks a pre-existing rung 2 test to gain speed.
- Never the 10x claim rests on before and after benchmarks that aren't
  shaped identically.
- Never a fix is applied without profiler evidence behind it.

## Acceptance
- `go test -bench=. -benchmem` output for the original implementation
  (before) is committed.
- A pprof flamegraph captured during that benchmark run is committed.
- A written hypothesis, stated before the fix, names the specific
  bottleneck.
- Exactly one deliberate change implements the fix, isolated as a single
  commit or diff.
- `go test -bench=. -benchmem` is rerun identically post-fix; before/after
  numbers show ≥10x improvement on the targeted operation, or the
  write-up documents exactly why it fell short.
- The original rung 2 test suite still passes after the fix.
- ADR is the performance report: hypothesis, flamegraph evidence, the
  one fix, and the before/after benchmark numbers.

## Starting nudge
Run the existing benchmark once, unmodified, before you form any
opinion about what's slow — the flamegraph from that run is your only
legitimate source of a hypothesis. Resist fixing the first thing that
looks inefficient by eye; fix what the profile actually shows as hot.

## ADR question
This rung's ADR is a performance report — hypothesis, flamegraph
evidence, the one deliberate fix, and before/after numbers, not a
design narrative.
