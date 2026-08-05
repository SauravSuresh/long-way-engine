# Rung 6, Option C — Previz asset catalog API

**Concept:** A real service skeleton — middleware, error envelope, layout.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Your previz startup's camera gear, render files, and their tags live
scattered across drives and a spreadsheet nobody keeps current. You want
an API that tracks gear and files with tags in one place your own tools
can query, instead of you eyeballing a shared sheet every time you need
an answer.

## Situation
You're prepping a shoot list and need every lens with a specific mount,
cross-referenced against which render files used them last. Instead of
opening the spreadsheet and scanning it by eye, you hit the catalog API
and get the answer back as JSON in under a second.

## Scope
- Create, fetch, list, and delete an asset — a gear item or a file
  record — each with a type, a name, and tags.
- List/filter assets by tag.
- Stdlib-first, no web framework.
- A middleware chain wraps every route: request logging, a request ID
  per request, panic recovery that keeps the server alive.
- Every error response — validation, not-found, panic-recovered — comes
  back in the exact same JSON error envelope shape.
- Storage sits behind an interface; handlers never import a concrete
  storage package directly.
- `httptest` (or equivalent) coverage of the handlers.
- This is the service you'll keep alive and extend for months: rungs
  7–13 add Postgres, auth, a spec, webhooks, a job queue, deployment,
  and a perf pass on top of whatever you build here. Pick something
  you're willing to keep running, not a throwaway.

## Non-goals
- No file upload or binary storage — asset records reference files,
  they don't hold file bytes.
- No gear checkout/reservation workflow.
- No web UI — API only.
- No multi-tenant access; this catalog is for your own startup.

## How it should NOT work
- Never a panic inside one handler taking the whole server down.
- Never two different JSON shapes for two different kinds of error.
- Never a 200 with an empty or null body when an asset doesn't exist —
  that's a 404 through the error envelope.
- Never deleting a tag from an asset silently deletes the asset itself.

## Acceptance
- `go test ./...` and `go vet ./...` clean; handler tests use
  `httptest`, none open a real network port.
- Every response, success or error, carries a request ID a caller can
  use to correlate it with a server log line.
- A test that deliberately triggers a panic inside a handler gets back
  the error envelope at 500, and the server keeps serving afterward.
- A tag-filter test creates several assets with overlapping tags and
  asserts the list endpoint returns exactly the matching subset.
- A test asserts validation, not-found, and panic-recovered errors all
  deserialize into the identical envelope struct.
- The test suite runs the full handler set against an in-memory fake
  implementing the storage interface.
- README documents how to run the server and lists every endpoint with
  a real example request and response.
- `go.mod` lists no HTTP framework/router dependency — the module graph
  shows only stdlib for routing and serving; the router is `net/http`.
- ADR names the real consumer (the startup) and states plainly that
  this is the rung 6–13 lab service.

## Starting nudge
Build the error envelope and the middleware chain before you write a
single asset-related handler — wire them around one throwaway `/ping`
route and confirm request ID, logging, and panic recovery all show up
for that one endpoint. That plumbing is what every later rung on this
service will sit on top of.

## ADR question
Package layout you won't regret at rung 13.
