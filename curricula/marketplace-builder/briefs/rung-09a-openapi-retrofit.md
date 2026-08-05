# Rung 9, Option A — OpenAPI retrofit of rungs 6–8's service

**Concept:** Contract before code.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Your lab service has grown handler by handler across rungs 6 through 8
with no single source of truth for its shape. Fields drifted from what
you originally intended and nothing stops a future change from breaking
a client without anyone noticing — a rehearsal for the discipline the
platform's public API will need on Saturdays.

## Situation
You sit down to write a client for your own service and end up reading
your own handler source to figure out what a field is actually called,
because there's no spec. That's exactly the position you don't want
anyone consuming your API to be in.

## Scope
- An OpenAPI spec describing every endpoint of your rung 6–8 service,
  written first and passing `spectral lint` clean.
- The implementation is refactored to match the spec exactly — the spec
  is the source of truth, not documentation written after the fact.
- List endpoints use cursor-based pagination, matching the spec.
- Every documented error response carries a documented error code,
  consistent with the existing error envelope.
- Every mutating endpoint (create/update/delete) is idempotent given a
  client-supplied idempotency key — retrying the same request doesn't
  double-apply it.
- Contract tests run in CI, verifying the running implementation
  actually matches the spec.

## Non-goals
- No API versioning scheme (v1/v2 in the path, etc.) — one current
  version only.
- No client SDK generation requirement.
- No GraphQL or alternate transport — REST/OpenAPI only.
- No backward-compatibility shims for pre-spec behavior.

## How it should NOT work
- Never a spec that fails spectral lint shipped as final.
- Never an endpoint whose real behavior diverges from what the spec
  documents — caught by contract tests, not manual review.
- Never a mutation applied twice because a client retried with the same
  idempotency key.
- Never offset-based pagination (`?page=2`) presented as cursor
  pagination.

## Acceptance
- `spectral lint <spec>` exits clean.
- CI runs contract tests against the live implementation and fails the
  build on any spec/implementation mismatch.
- A list endpoint accepts a cursor parameter and returns a next-cursor,
  verified by a test that pages through more results than fit on one
  page.
- A retried mutation with the same idempotency key produces exactly one
  effect, verified by test (send it twice, assert a single record).
- Every error response documented in the spec has a documented code,
  and a test asserts the implementation returns that exact code for
  that condition.
- `go test ./...` and `go vet ./...` clean; README points at the spec
  file and shows how to lint it.
- A changelog or ADR records every place refactoring to match the spec
  actually changed behavior from what rungs 6–8 originally shipped.

## Starting nudge
Desk reference: *API Design Patterns* is worth having open for this
one. Start by spec'ing the two or three endpoints most likely to have
drifted — a list endpoint and one mutation — before spec'ing the whole
surface, since those are where cursor pagination and idempotency will
force real implementation changes.

## ADR question
Spec as source of truth: when it and the implementation disagree, which one moves?
