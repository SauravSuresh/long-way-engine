# Rung 6, Option B — Pastebin with expiry

**Concept:** A real service skeleton — middleware, error envelope, layout.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Sharing a chunk of logs or a render script with a teammate over Slack
means it's buried in scrollback within a day, and pasting anything
sensitive into a channel that never expires it is a habit you'd rather
not have. You want a pastebin: paste in, short link back, content that
actually goes away when it says it will.

## Situation
A render just crashed and you need to hand a teammate the relevant log
chunk right now, without it sitting in Slack forever for anyone to
scroll past later. You paste it, get back a short URL with an expiry
stamped on it, send the URL, and a week later it's gone whether either
of you remembers to delete it or not.

## Scope
- Create a paste from a body (with an optional TTL) and get back a short
  id; a sensible default TTL applies when none is given, and the
  response reports the expiry that was actually set.
- Fetch a paste by short id — returns the body until expiry, then a
  clean 404/gone, not a silently empty body.
- Pastes are immutable once created — no edit endpoint.
- Stdlib-first, no web framework.
- A middleware chain wraps every route: request logging, a request ID
  per request, panic recovery that keeps the server alive.
- Every error response — validation, not-found/expired, panic-recovered
  — comes back in the exact same JSON error envelope shape.
- Storage sits behind an interface; handlers never import a concrete
  storage package directly.
- `httptest` (or equivalent) coverage of the handlers.
- This is the service you'll keep alive and extend for months: rungs
  7–13 add Postgres, auth, a spec, webhooks, a job queue, deployment,
  and a perf pass on top of whatever you build here. Pick something
  you're willing to keep running, not a throwaway.

## Non-goals
- No edit-in-place; a paste is create-once, read-many, then gone.
- No user accounts or paste ownership.
- No syntax highlighting or web UI — API only.
- No configurable per-paste access control beyond "anyone with the
  short id can read it until it expires."

## How it should NOT work
- Never returns paste content after its TTL has elapsed just because a
  background sweeper hasn't gotten to it yet — expiry is checked at
  read time.
- Never two different JSON shapes for two different kinds of error.
- Never a panic in one request handler taking the whole server down.
- Never a short-id collision silently overwrites another paste's
  content.

## Acceptance
- `POST` a paste with a body only returns 201, a short id, and the
  default TTL that was applied.
- `POST` a paste with an explicit short TTL, then `GET` it before
  expiry returns the body; `GET` it again after expiry (via a fake
  clock or a deliberately short TTL) returns 404/gone through the error
  envelope, never the stale body.
- A test that deliberately triggers a panic inside a handler gets back
  the error envelope at 500, and the server keeps serving afterward.
- A test asserts validation, not-found/expired, and panic-recovered
  errors all deserialize into the identical envelope struct.
- The test suite runs the full handler set against an in-memory fake
  implementing the storage interface.
- `go test ./...` and `go vet ./...` clean.
- README documents how to run the server and lists every endpoint with
  a real example request and response.
- ADR names a real consumer (you, operating it) and states plainly that
  this is the rung 6–13 lab service.

## Starting nudge
Get expiry-at-read-time right before optimizing anything else: write
the test for "GET after expiry" before the create endpoint even exists,
since serving stale content past its expiry is the one bug that would
make this rung pointless.

## ADR question
Package layout you won't regret at rung 13.
