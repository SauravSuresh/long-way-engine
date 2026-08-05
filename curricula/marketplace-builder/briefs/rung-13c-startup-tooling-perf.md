# Rung 13, Option C — Find and fix a real slowness in the startup's tooling

**Concept:** Profiling discipline — hypothesis, measurement, one fix.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Some piece of the previz startup's actual tooling — a build script, an
asset pipeline step, a CI job — is annoyingly slow in daily use, and
you've just tolerated it. You want to apply the same measure-first
discipline to a real bottleneck instead of a synthetic one, and fix it
for good.

## Situation
You run the same slow tooling command for the tenth time this week,
watching a progress bar crawl, and finally decide to actually profile it
instead of grumbling about it. Twenty minutes later the flamegraph shows
the real cost isn't where you assumed, and the fix is smaller than the
grumbling suggested.

## Scope
- A concrete, reproducible measurement of the current slow operation's
  time (or resource cost), captured before any change, using a real
  command against real tooling.
- A profile (pprof or the appropriate tool for the tooling's runtime)
  produces a flamegraph or equivalent hot-path evidence.
- A hypothesis is written down before touching code, backed by that
  evidence.
- Exactly one deliberate change is made in response to that hypothesis.
- The identical operation is rerun post-fix; before/after numbers are
  committed side by side.
- The tooling's observable output/behavior is verified unchanged aside
  from speed.

## Non-goals
- No fixing multiple unrelated slow spots in the same pass.
- No infrastructure upgrade counted as "the fix" unless the profile
  evidence actually points there.
- No rewriting the tooling from scratch.
- No fix that changes the tooling's observable output or behavior.

## How it should NOT work
- Never a "we made it faster" claim ships without a reproducible
  before/after measurement.
- Never a fix is applied on a hunch with no profiling evidence behind
  it.
- Never a fix silently changes the tool's output or behavior while
  claiming a speed win.
- Never the flamegraph is skipped because "the answer was obvious."

## Acceptance
- Before measurement: the identical real command, timed or profiled,
  with output committed.
- A flamegraph or equivalent hot-path evidence is committed.
- A written hypothesis, stated before the fix.
- Exactly one deliberate change implements the fix, isolated as a single
  commit or diff.
- After measurement: the identical command rerun, before/after numbers
  compared directly.
- The tool's existing tests/checks (if any) still pass, or its output is
  otherwise verified unchanged aside from speed.
- ADR is the performance report: hypothesis, flamegraph evidence, the
  one fix, and before/after numbers.

## Starting nudge
Time the operation exactly as you already run it day to day, unmodified,
before opening a profiler — that number is what "10x" or "twice as fast"
actually gets compared against, and it has to come from the real
command, not a stripped-down reproduction of it.

## ADR question
This rung's ADR is a performance report — hypothesis, flamegraph
evidence, the one deliberate fix, and before/after numbers, not a
design narrative.
