# Rung 12, Option C — One-command dev environment

**Concept:** Packaging, config, graceful shutdown, health — production shape.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Getting the previz startup's tooling running on a fresh machine means
chasing missing environment variables, mismatched dependency versions,
and undocumented setup steps you only remember by trial and error. You
want a fresh clone to a running, working local environment in one
command, every time, for anyone (including future you).

## Situation
You wipe your laptop, or spin up a spare machine to debug something.
Instead of losing an afternoon to "wait, what env var was that again,"
you run one command and the tooling is up, seeded, and answering
requests before your coffee's done.

## Scope
- A single command (script, Makefile target, whatever) provisions and
  starts everything needed to develop locally: service(s), database, and
  any seed data.
- Dev configuration comes from a documented template (e.g. `.env.example`
  copied and filled in) — nothing hardcoded in code or scripts.
- Running the command again on an already-running environment doesn't
  error or duplicate state (idempotent).
- A teardown command (or a flag on the same command) cleanly stops and
  removes everything that was started, freeing ports.
- Any container/base images used are chosen deliberately for size, and
  that choice is documented.
- README documents exactly what the one command does, step by step, and
  lists every prerequisite.

## Non-goals
- No production deploy tooling — that's option A or B's territory.
- No support for multiple simultaneous dev environments on one machine.
- No GUI or dashboard for the dev environment.
- No automatic dependency version management beyond what's already
  pinned in lockfiles.

## How it should NOT work
- Never the one command fails partway through and leaves a broken,
  half-started environment with no clear error.
- Never running the command twice corrupts or duplicates state — no
  duplicate seed rows, no port conflict crashing the second attempt.
- Never a config value required for the environment to work goes
  undocumented.
- Never teardown leaves orphaned containers, processes, or occupied
  ports behind.

## Acceptance
- On a machine with only the documented prerequisites installed, running
  the one documented command takes a fresh clone to a running, healthy
  service — verified by successfully hitting an endpoint.
- Running the command a second time without tearing down first does not
  error or duplicate seeded data — demonstrated.
- The teardown command cleanly stops everything and frees ports —
  verified by re-running setup immediately after and it succeeding again.
- `grep` across the setup scripts shows no hardcoded secret or
  environment-specific value; every required config value is sourced
  from `.env.example` (or equivalent) and documented.
- README documents what the one command does under the hood, and lists
  the choice of base image/size tradeoff made.
- ADR answers what's env, what's flag, what's file — and why.

## Starting nudge
Write the teardown command alongside the setup command from the start,
even a crude one — a setup script with no teardown is how you end up
debugging port conflicts and leftover containers instead of the actual
tooling. Idempotency and clean teardown are the two properties that make
"one command" trustworthy enough to actually reach for.

## ADR question
What's env, what's flag, what's file — and why?
