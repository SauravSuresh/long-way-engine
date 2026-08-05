# Rung 8, Option C — API-key issuing and scoping service

**Concept:** AuthN + authZ; attack-path testing, not happy-path testing.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Your own scripts and CI jobs currently share one all-powerful credential
wherever they need to hit an API of yours, which means every one of them
can do everything, and revoking access to one means rotating a secret
everywhere else too. You want a service that issues scoped API keys to
machine clients instead.

## Situation
A CI job needs to read one endpoint of a service you run. Instead of
handing it the same god-credential your deploy scripts use, you issue it
a key scoped to read-only access on that one resource, and if that job
ever gets compromised, you revoke that one key without touching anything
else.

## Scope
- Issue an API key tied to an explicit scope (for example, read-only vs
  read-write, or a named set of permitted actions).
- Middleware verifies a key on protected endpoints and enforces its
  scope before the handler runs.
- A key can be revoked, and revocation takes effect immediately.
- Keys are stored non-plaintext (hashed at rest).
- Tests specifically exercise the forbidden paths: a valid key used
  outside its scope is rejected, proven by test.

## Non-goals
- No user-facing login/session flow — keys are for machine clients
  only.
- No automated key rotation scheduling.
- No per-key rate limiting.
- No UI for key management — this is an API.

## How it should NOT work
- Never stores a key in plaintext — a database leak would otherwise
  compromise every client at once.
- Never lets a revoked key continue authenticating after revocation.
- Never grants a key broader scope than what was requested/configured
  at issuance.
- Never enforces scope on some endpoints and forgets it on others —
  every protected endpoint checks scope the same way.

## Acceptance
- A test issues a key and asserts the raw key value is returned exactly
  once at issuance, never retrievable in plaintext again.
- Stored keys are hashed, verified by test.
- A test sends a request with a valid key but the wrong scope and
  asserts rejection (401/403).
- A test sends a request with the correct scope and asserts success.
- A test revokes a key, then immediately attempts to use it, and
  asserts rejection.
- The ADR states the token lifetime + revocation story for this app.
- `go test ./...` and `go vet ./...` clean.
- README shows example key issuance and an authenticated curl request.

## Starting nudge
Write the revoke-then-use test before building issuance: revocation has
to cut off access immediately, not on some cache-expiry timer, and
that's the easiest thing to get wrong if issuance ships first and
revocation gets bolted on after.

## ADR question
Token lifetime + revocation story for THIS app.
