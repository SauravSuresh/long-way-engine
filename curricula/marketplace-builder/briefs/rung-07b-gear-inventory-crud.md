# Rung 7, Option B — Camera-gear inventory CRUD

**Concept:** Migrations, integration tests, pools — SQL as a first-class skill.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Your previz startup's camera gear is tracked in a spreadsheet that drifts
out of date the moment two people touch it in the same week. You want a
proper relational store for gear — name, category, serial, status — that
you can query reliably, and this is deliberately platform-adjacent
practice: a rental marketplace lives and dies on schema discipline like
this.

## Situation
You need to know which lenses are marked "in for repair" right now,
without trusting whether the spreadsheet was updated after the last
shoot. You run a query against the inventory service and get the answer
straight from the database, not from someone's memory.

## Scope
- CRUD over gear items: name, category, serial number, status
  (available/checked-out/in-repair or similar).
- Search/filter gear by category and status.
- Schema managed by versioned migrations, applied through a migration
  tool.
- Integration tests run against a real Postgres instance, not a mock.
- A connection pool with explicit limits and timeouts, justified in the
  ADR.
- Storage sits behind an interface; handler code never talks to the SQL
  driver directly.

## Non-goals
- No reservation/booking calendar for gear.
- No barcode/QR scanning integration.
- No multi-warehouse or multi-location tracking.
- No financial/depreciation tracking.

## How it should NOT work
- Never a query built by concatenating user input into SQL — every
  query is parameterized.
- Never a schema change applied by hand outside the versioned migration
  mechanism.
- Never data loss on process restart.
- Never a handler that bypasses the store interface to talk to the
  database directly.

## Acceptance
- Migrations run against a clean database and reach a known schema,
  verified by test.
- An integration test creates, reads, updates, and deletes a gear item
  against a real Postgres instance.
- A test that attempts a classic SQL-injection payload through a search
  filter proves the query is parameterized and the payload has no
  effect beyond being treated as literal text.
- Pool size and timeouts are explicit configuration, and the ADR states
  the numbers and why.
- The full handler test suite runs unmodified against an in-memory fake
  implementing the same store interface as the Postgres-backed store —
  proving handler code depends only on the interface, not the database.
- `go test ./...` and `go vet ./...` clean.
- README documents setup, migrations, and example CRUD requests.

## Starting nudge
Write the migration for the gear table before any application code, and
write the first integration test against it — insert one row, read it
back. That's the seam that proves your Postgres wiring works before any
CRUD logic exists on top of it.

## ADR question
ORM vs sqlc vs raw — justify for a solo maintainer.
