# Rung 7, Option A — Port rung 6's service to Postgres

**Concept:** Migrations, integration tests, pools — SQL as a first-class skill.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Your rung 6 service — whichever of the three you picked and kept alive —
runs on an in-memory store that forgets everything on restart. That was
fine for a skeleton; it's useless for a service you actually intend to
keep running, and Saturday's platform needs Postgres competence within
weeks anyway.

## Situation
You restart your rung 6 service to deploy a small change and watch every
note, paste, or asset that existed before the restart disappear — exactly
the failure a service you rely on can't have.

## Scope
- The same HTTP surface as your rung 6 service, unchanged from the
  caller's perspective, now persists data in Postgres — restart the
  process and the data is still there.
- Schema managed by versioned migrations (up path at minimum), applied
  through a migration tool — not hand-run SQL.
- Integration tests run against a real Postgres instance (docker-compose
  or equivalent), not a mock.
- A connection pool with explicit limits and timeouts, justified in the
  ADR — not left at whatever the driver defaults to.
- The store interface from rung 6 still holds: swapping in-memory for
  Postgres doesn't touch handler code.

## Non-goals
- No ORM required unless your ADR chooses one.
- No multi-database abstraction — Postgres only.
- No schema for features outside rung 6's existing scope.
- No production backup/replication setup — that's rung 12's job.

## How it should NOT work
- Never loses data across a restart that used to be in-memory-only.
- Never a handler that talks to the SQL driver directly instead of
  going through the store interface.
- Never a schema change applied by hand outside the versioned migration
  mechanism.
- Never a connection pool left at driver defaults with no stated reason.

## Acceptance
- `docker-compose up` (or equivalent) brings up Postgres; migrations run
  clean against it and integration tests pass.
- Killing and restarting the service process preserves data created
  before the restart, verified by test.
- Re-running the migrations against a fresh database reaches the same
  schema every time (idempotent up-path).
- Pool size and timeouts are explicit configuration, and the ADR states
  the numbers and why.
- Your existing rung 6 handler tests pass unmodified against the new
  Postgres-backed store — proof the interface held.
- `go test ./...` and `go vet ./...` clean.
- README updated with Postgres setup and migration instructions.

## Starting nudge
Run rung 6's existing handler test suite against a Postgres-backed
implementation of the same store interface before writing a single new
migration file. If those old tests fail without changes, the interface
didn't hold, and that's the thing to fix before anything else.

## ADR question
ORM vs sqlc vs raw — justify for a solo maintainer.
