# Rung 8, Option A — Users and roles on rung 7's service

**Concept:** AuthN + authZ; attack-path testing, not happy-path testing.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Your rung 7 service — now Postgres-backed — accepts every request as
equally trusted, which was fine while you were the only caller and is
wrong the moment anyone else touches it. You need real users and at
least two roles before you hand a URL to anyone but yourself.

## Situation
You give a collaborator access to your service and realize there is
currently no difference between them running a routine query and them
deleting everything in it. You need owner vs admin roles that actually
restrict something, proven before you hand out the URL, not assumed.

## Scope
- Users authenticate with a password against your rung 7 service.
- Passwords are hashed with bcrypt or argon2 — never stored or logged
  in plaintext.
- At least two roles, owner and admin, with observably different
  permissions on at least one real endpoint carried over from rung 7.
- Auth middleware rejects unauthenticated or unauthorized requests
  before they reach handler logic.
- The ADR states and justifies sessions vs JWT for this app.
- Tests specifically exercise the forbidden paths: an admin (or an
  unauthenticated caller) attempting an owner-only action is rejected,
  proven by a passing test, not assumed from the code.

## Non-goals
- No self-service password reset flow (rung 8's other options cover
  passwordless patterns; not required here).
- No OAuth or social login.
- No fine-grained per-resource ACLs beyond the owner/admin split.
- No login-attempt rate limiting (rung 5's limiter could be reused
  later, but it's not required for this rung).

## How it should NOT work
- Never stores or logs a plaintext password anywhere, including error
  messages.
- Never lets an admin or an anonymous caller successfully perform an
  owner-only action — that path fails every single time, proven by a
  test that attempts exactly that.
- Never issues a token with no expiry and no revocation story at all.
- Never enforces the role check only in a client — enforcement happens
  server-side, in the middleware or handler.

## Acceptance
- A test attempts an owner-only action as an admin and as an
  unauthenticated caller, and asserts both are rejected (401/403).
- A test attempts the same action as an owner and asserts it succeeds —
  proving the check isn't just "reject everything."
- Stored password hashes are bcrypt/argon2 output with a deliberate
  cost factor, verified by test — never equal to the plaintext.
- The ADR states sessions vs JWT and the token lifetime + revocation
  story for this app.
- `go test ./...` and `go vet ./...` clean.
- README documents how to create a user and log in.

## Starting nudge
Write the forbidden-path test first: pick one real rung 7 endpoint and
write the test asserting an admin gets rejected from its owner-only
variant, before wiring any hashing or middleware. That test gives the
whole rung one concrete target to build toward.

## ADR question
Token lifetime + revocation story for THIS app.
