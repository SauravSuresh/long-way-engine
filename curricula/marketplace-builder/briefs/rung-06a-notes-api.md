# Rung 6, Option A — Notes/snippets API

**Concept:** A real service skeleton — middleware, error envelope, layout.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
You keep useful commands, config fragments, and half-remembered fixes
scattered across scratch files, Slack DMs to yourself, and terminal history
that ages out. None of it is queryable and none of it survives a wiped
laptop. You want an HTTP API you run yourself that stores notes and
snippets with a title, body, and tags, and hands them back fast.

## Situation
You're three commands into fixing something you're certain you already
fixed a month ago. Instead of grepping five folders and your shell
history, you hit your notes API from a terminal one-liner and the snippet
you wrote back then is on screen before your coffee's cold.

## Scope
- Create a note (title, body, tags), fetch one by id, list notes with an
  optional tag filter, delete by id — all JSON in, JSON out.
- Stdlib-first: `net/http` (or your language's stdlib equivalent), no web
  framework.
- A middleware chain wraps every route: request logging, a request ID
  assigned per request and returned to the caller, and panic recovery
  that keeps the server alive.
- Every error response — validation failure, not-found, panic-recovered —
  comes back in the exact same JSON error envelope shape.
- Storage sits behind an interface; the handlers never import a concrete
  storage package directly.
- `httptest` (or equivalent) coverage of the handlers — no test spins up
  a real listener on a real port.
- This is the service you'll keep alive and extend for months: rungs
  7–13 add Postgres, auth, a spec, webhooks, a job queue, deployment, and
  a perf pass on top of whatever you build here. Pick something you're
  willing to keep running, not a throwaway.

## Non-goals
- No authentication or authorization — every request is trusted for now
  (rung 8's job).
- No requirement to survive a process restart — in-memory storage is
  fine (rung 7 adds Postgres).
- No web UI; this is an API only.
- No full-text search ranking — exact or substring tag/title match is
  enough.

## How it should NOT work
- Never a panic inside one handler taking the whole server down —
  recovery middleware catches it and the server keeps serving the next
  request.
- Never two different JSON shapes for two different kinds of error.
- Never a 200 with an empty or null body when a note doesn't exist —
  that's a 404 through the error envelope.
- Never a handler that imports a concrete storage type instead of the
  interface.

## Acceptance
- `go test ./...` and `go vet ./...` clean; handler tests use `httptest`,
  none open a real network port.
- Every response, success or error, carries a request ID a caller can
  use to correlate it with a server log line.
- A test that deliberately triggers a panic inside a handler gets back
  the error envelope at 500, and a subsequent request to the same server
  succeeds — proving recovery, not restart.
- A test asserts a 400 (bad input), a 404 (missing note), and a 500
  (recovered panic) all deserialize into the identical envelope struct.
- The test suite runs the full handler set against an in-memory fake
  implementing the storage interface — nothing in the handler package
  references a concrete store type.
- README documents how to run the server and lists every endpoint with a
  real example request and response.
- ADR names a real consumer (you, operating it) and states plainly that
  this is the rung 6–13 lab service.

## Starting nudge
Build the error envelope and the middleware chain before you write a
single note-related handler — wire them around one throwaway `/ping`
route and confirm request ID, logging, and panic recovery all show up
for that one endpoint. That plumbing is what every later rung on this
service will sit on top of.

## ADR question
Package layout you won't regret at rung 13.
