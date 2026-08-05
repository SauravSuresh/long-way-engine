# Rung 16, Option B — Chaos week on your deployed stack

**Concept:** Correctness under failure — the platform's operations rehearsal.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
The rung 12 deployment has never actually been tested against real
failure — a process killed mid-request, a disk filling up, a network
partition. "It'll probably be fine" isn't evidence, and this is the last
rung before that deployment starts carrying real weight.

## Situation
Your service has been running quietly on the VPS for weeks. Instead of
waiting for a real outage to find out what breaks, you deliberately
break it yourself, on purpose, with a written plan and someone — you —
watching and ready to revert.

## Scope
- A written runbook, produced before any chaos, listing the specific
  experiments to run (process kill mid-work, disk fill, network
  partition/latency injection — at least 3 distinct experiments) and how
  each is triggered and reverted.
- Each experiment is actually executed against the real deployed stack,
  and its observed behavior is recorded.
- A postmortem, written after, documents what broke, what didn't, and
  why, per experiment.
- At least one real fix is shipped in response to something the chaos
  exposed, with before/after behavior for that fix demonstrated.
- A safe rollback/abort plan exists for each experiment so a chaos run
  doesn't cause lasting damage.

## Non-goals
- No automated chaos-engineering framework built for repeat use — a
  documented manual or scripted process is enough.
- No fixing every issue found — one real, demonstrated fix is the bar.
- No load testing — that's rung 13's territory, unless a failure only
  surfaces under load.
- No new rung follows this one — this is inside the last rung of the
  ladder; from here, build time moves to the platform's own milestones.

## How it should NOT work
- Never a chaos experiment is run without a documented rollback/abort
  plan written first.
- Never a "fix" ships without demonstrating the specific failure it
  addresses, before and after.
- Never an experiment causes silent data loss with no acknowledgment in
  the postmortem.
- Never the postmortem skips an experiment that revealed something bad
  because it was inconvenient.

## Acceptance
- A runbook is committed before the chaos week starts, listing ≥3
  distinct experiments (process kill, disk fill, partition/latency) with
  trigger and rollback steps for each.
- Each experiment is actually run against the real deployed stack;
  observed behavior — what happened, what recovered, what didn't — is
  recorded per experiment.
- A postmortem is committed after, one section per experiment, stating
  pass/fail against expectations.
- At least one concrete fix is shipped, with a before/after
  demonstration of the specific failure it closes (e.g. repeating the
  experiment that previously failed now passes).
- README/ADR states which failure modes are now covered and which are
  explicitly still unguarded after the week.

## Starting nudge
Write the runbook — what you're going to break and exactly how you'll
revert it — before you break anything. A chaos experiment with no
written rollback plan first is how a "week" turns into a real outage.
Pull Release It! after whatever breaks worst turns out to be the most
instructive move here.

## ADR question
What failure mode does this prove you can survive, and what failure
mode is still unguarded after it?
