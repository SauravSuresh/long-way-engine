# Rung 13, Option A — k6 load profile + pprof hunt

**Concept:** Profiling discipline — hypothesis, measurement, one fix.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Your rung-12 deployment works, but you have no evidence-based idea how
it behaves under load — you're guessing at what's slow instead of
measuring it. You want a disciplined pass: load it, profile it, form a
hypothesis, make one change, and prove the change mattered.

## Situation
Someone asks how your deployed service holds up under real traffic and
you realize you don't actually know — you've never put load on it and
watched where the time goes. You point k6 at it, pull up the flamegraph,
and for the first time you can say exactly which function is eating the
p95.

## Scope
- A k6 (or documented equivalent) load script exercises real endpoints
  of the deployed rung-12 service, producing a baseline load profile
  before any code changes.
- A pprof profile (CPU or memory, whichever the hypothesis targets) is
  captured during that load and rendered as a flamegraph.
- A hypothesis is written down before touching code: which function or
  path is expected to be hot, and why, based on the flamegraph.
- Exactly one deliberate code change is made in response to that
  hypothesis.
- The identical k6 script is rerun post-fix; before/after numbers (e.g.
  p95 latency, throughput) are committed side by side.
- A write-up documents the hunt end to end — this is the rung's ADR.

## Non-goals
- No optimizing code paths the profile doesn't show as hot.
- No infrastructure scaling (more instances, bigger VPS) counted as
  "the fix" — this rung is a code-level fix.
- No architectural rewrite of the service.
- No bundling more than one change into "the fix."

## How it should NOT work
- Never a fix applied without flamegraph evidence backing the
  hypothesis — that's guessing, not profiling.
- Never before/after numbers reported from two different load profiles
  or parameters.
- Never more than one deliberate change bundled together, making the
  improvement impossible to attribute.
- Never a claimed improvement that doesn't reproduce when the identical
  k6 script is rerun.

## Acceptance
- k6 output (latency percentiles, throughput) for the pre-fix run is
  committed.
- A pprof flamegraph, captured during that pre-fix load test, is
  committed as a file or image.
- A written hypothesis, stated before the fix, names the specific
  function or path expected to be hot and why.
- Exactly one code change implements the fix, visible as a single,
  isolated commit or diff.
- k6 is rerun with identical parameters post-fix; before/after numbers
  are committed together, showing the measured difference.
- `go test ./...` and `go vet ./...` clean.
- ADR is the performance report: hypothesis, flamegraph evidence, the
  one fix, before/after numbers, and what you'd hunt next.

## Starting nudge
Run the k6 baseline against the currently-deployed service before you
open a profiler at all — without a number, you have no way to know
later whether your fix actually moved anything. Let the flamegraph tell
you where to look; don't let intuition pick the fix first.

## ADR question
This rung's ADR is a performance report — hypothesis, flamegraph
evidence, the one deliberate fix, and before/after numbers, not a
design narrative.
