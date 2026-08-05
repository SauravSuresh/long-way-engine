# Rung 9, Option B — Spec-first public URL shortener

**Concept:** Contract before code.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
You want to publish a URL shortener API for other tools — your own or
someone else's — to call, and you don't want its first breaking change
to be the moment someone else notices before you do.

## Situation
You're about to hand a shortener endpoint to a second project of yours
to integrate against. Instead of building the handlers and writing docs
after the fact, you write the spec first, lint it, and only then start
implementing — so the contract, not the code, is what you and any future
caller agree on.

## Scope
- An OpenAPI spec for the shortener, written first and passing
  `spectral lint` clean, before implementation begins.
- Create a short link and get back a short code; redirect on `GET`;
  a stats/list endpoint uses cursor-based pagination.
- Every documented error response carries a documented error code.
- Creating a short link is idempotent given a client-supplied
  idempotency key — retrying with the same key returns the same short
  code rather than creating a second one.
- Contract tests run in CI, verifying the implementation matches the
  spec.

## Non-goals
- No custom/vanity short codes.
- No analytics dashboard UI beyond the stats endpoint's raw data.
- No login-attempt or request rate limiting required for this rung.
- No authentication — this is a public API by design.

## How it should NOT work
- Never a spec that fails spectral lint shipped as final.
- Never an endpoint whose real behavior diverges from what the spec
  documents.
- Never a retried create-link request with the same idempotency key
  produces two different short codes for the same URL.
- Never a list endpoint implemented as offset pagination while the spec
  claims cursor pagination.

## Acceptance
- `spectral lint <spec>` exits clean.
- CI runs contract tests against the live implementation and fails the
  build on any mismatch.
- A cursor-pagination test pages through a stats/list endpoint with
  more results than fit on one page.
- An idempotency test retries a create-link request with the same key
  and asserts the same short code and a single underlying record.
- Every documented error code is exercised by a test asserting the
  implementation returns it for the matching condition.
- `go test ./...` and `go vet ./...` clean; README links the spec file.

## Starting nudge
Desk reference: *API Design Patterns* is worth keeping open while you
shape this. Write the spec for create-link and get-stats before any
handler code exists, run it through spectral until it's clean, and only
then start implementing against it — idempotency and pagination are
exactly what determine whether the spec was worth writing.

## ADR question
Spec as source of truth: when it and the implementation disagree, which one moves?
