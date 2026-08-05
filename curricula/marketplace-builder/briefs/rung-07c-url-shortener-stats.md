# Rung 7, Option C — URL shortener with click stats

**Concept:** Migrations, integration tests, pools — SQL as a first-class skill.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
You share links to render outputs, PRs, and status pages constantly, and
have no idea whether anyone actually opens them. You want your own URL
shortener that redirects fast and counts every click accurately — a
deliberately write-heavy schema exercise, since every redirect is a
write.

## Situation
You send a shortened link to a client waiting on a render preview. An
hour later you want to know, honestly, whether they've opened it yet —
you check the stats endpoint and get an exact click count, not a
guess.

## Scope
- Shorten a URL and get back a short code.
- `GET` on the short code redirects to the original URL and records a
  click (timestamp at minimum) for that code.
- A stats endpoint returns the click count for a given short code.
- Schema managed by versioned migrations, applied through a migration
  tool.
- Integration tests run against a real Postgres instance.
- A connection pool sized and justified for write-heavy traffic in the
  ADR.
- Storage sits behind an interface; handler code never talks to the SQL
  driver directly.

## Non-goals
- No custom/vanity short codes.
- No link expiry.
- No user accounts or link ownership.
- No analytics dashboard UI — the stats endpoint returns data, not
  charts.

## How it should NOT work
- Never undercounts clicks under concurrent redirects — a lost write is
  the failure mode this rung exists to catch.
- Never lets two different long URLs collide on the same short code.
- Never data loss on process restart.
- Never a query built by concatenating user input into SQL.

## Acceptance
- A concurrency test fires N parallel redirect requests at the same
  short code and asserts the stats endpoint reports exactly N clicks
  afterward.
- Migrations run against a clean database and reach a known schema,
  verified by test.
- An integration test runs the full shorten → redirect → stats flow
  against a real Postgres instance.
- Pool size and timeouts are explicit configuration sized for
  write-heavy load, and the ADR states the numbers and why.
- The full handler test suite runs unmodified against an in-memory fake
  implementing the same store interface as the Postgres-backed store —
  proving handler code depends only on the interface, not the database.
- `go test ./...` and `go vet ./...` clean.
- README documents setup, migrations, and example requests.

## Starting nudge
Write the concurrent-click test before optimizing anything: fire 50
parallel redirects at one short code and assert the stats endpoint
reports exactly 50. That's the one bug — lost updates under
concurrency — this rung exists to catch, and it's worth having early.

## ADR question
ORM vs sqlc vs raw — justify for a solo maintainer.
