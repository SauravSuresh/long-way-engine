# Rung 9, Option C — Previz asset API spec + second client

**Concept:** Contract before code.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
A spec is only as good as its ability to stand in for the source code.
You want proof that a stranger — in this case, a second client you
build yourself without looking at the server's implementation — could
build a working integration against your previz asset API from the spec
alone.

## Situation
You need a second tool (a CLI, a script, whatever fits) to talk to your
asset catalog. Instead of importing the server's own types or reading
its handler code, you sit down with only the OpenAPI spec open and
build the client against that — and it works, first try, because the
contract actually carried the information.

## Scope
- An OpenAPI spec for the asset endpoints (create, get, list, tag
  filter), written first and passing `spectral lint` clean.
- The first implementation matches the spec exactly.
- The list endpoint uses cursor-based pagination.
- Creating an asset is idempotent given a client-supplied idempotency
  key.
- Every documented error response carries a documented error code.
- A second client, built from the spec alone — no shared code, no
  reading the server's implementation — successfully exercises every
  endpoint in the spec.
- Contract tests run in CI against the first implementation.

## Non-goals
- The second client doesn't need its own persistent storage or test
  suite beyond proving it can call every endpoint correctly.
- No requirement that the second client be written in a different
  language, though it's allowed.
- No UI for either client.
- No file/binary upload support.

## How it should NOT work
- Never a spec that fails spectral lint shipped as final.
- Never building the second client by peeking at the server's source to
  fill a spec gap — that defeats the point of the rung.
- Never a retried create-asset request with the same idempotency key
  produces a second asset.
- Never a list endpoint that claims cursor pagination in the spec but
  behaves like offset pagination in practice.

## Acceptance
- `spectral lint <spec>` exits clean.
- CI runs contract tests against the first implementation and fails the
  build on any spec/implementation mismatch.
- A cursor-pagination test pages through the list endpoint with more
  assets than fit on one page.
- An idempotency test retries a create-asset request with the same key
  and asserts a single resulting asset.
- The second client successfully performs create, get, list, and
  tag-filter using only the spec as reference — the README documents
  that it was built without consulting the server's source.
- Every documented error code is exercised by a test asserting the
  implementation returns it for the matching condition.
- `go test ./...` and `go vet ./...` clean.

## Starting nudge
Desk reference: *API Design Patterns* is worth reading before drafting
the spec, particularly the pagination and idempotency sections. Write
the spec, lint it, then build the second client in a fresh directory
with the spec file as the only reference open — no peeking at the
server code — since that's the actual test this rung is designed to
run.

## ADR question
Spec as source of truth: when it and the implementation disagree, which one moves?
