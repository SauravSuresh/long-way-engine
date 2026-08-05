# Rung 8, Option B — Magic-link login service

**Concept:** AuthN + authZ; attack-path testing, not happy-path testing.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Every side tool you build ends up needing a login, and you'd rather not
manage passwords — yours or anyone else's — for a tool that doesn't need
that much ceremony. You want a passwordless login service: email in, a
single-use link out, and a real session on the other end of clicking it.

## Situation
You want to let a collaborator into a small internal tool without
issuing them a password to remember or you having to build a reset
flow. They enter their email, get a link, click it once, and they're in
— and that link is useless to anyone who finds it in an old inbox a
month later.

## Scope
- Requesting a magic link takes an email address and issues a
  single-use link/token, delivered via email (a logging or dev-SMTP
  sender is fine).
- Clicking the link within its validity window authenticates the user
  and starts a session.
- The same token used a second time is rejected — links are single-use.
- Tokens are stored non-plaintext (hashed at rest), so a database leak
  doesn't hand out live sessions.
- The ADR states and justifies sessions vs JWT for this app.
- Auth middleware protects at least one real endpoint; a test proves
  unauthenticated access to it is rejected.

## Non-goals
- No password-based login fallback.
- No account recovery beyond requesting a fresh link.
- No real email delivery infrastructure — logging or a dev SMTP relay
  is sufficient.
- No multi-device session management UI.

## How it should NOT work
- Never authenticates the same link token a second time.
- Never issues a link with no expiry.
- Never stores the raw link token in plaintext where it could be read
  straight out of a database leak.
- Never authenticable by guessing or incrementing a token — tokens are
  unguessable, proven by their construction, not just their length.

## Acceptance
- A test requests a link, uses the resulting token once, and asserts
  authentication succeeds.
- The same test reuses the identical token and asserts it is rejected
  the second time.
- A test using an expired token asserts rejection.
- Stored tokens are hashed, verified by test — never equal to the raw
  token value handed to the client.
- A test hits a protected endpoint without a valid session and asserts
  rejection (401/403).
- The ADR states sessions vs JWT and the token lifetime + revocation
  story for this app.
- `go test ./...` and `go vet ./...` clean.
- README documents how to request and use a login link.

## Starting nudge
Write the reuse test before anything else: request a link, use it once
and assert success, use the identical token again and assert rejection.
That single-use guarantee is the one property a magic-link system can't
ship without, so build the storage and lookup logic to make that test
pass first.

## ADR question
Token lifetime + revocation story for THIS app.
