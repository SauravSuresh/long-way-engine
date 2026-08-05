# Rung 3, Option A — Currency/weather CLI

**Concept:** Timeouts, retries with backoff, testing without the network.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Sometimes you need one live number right now — an exchange rate before
confirming a payment, or the current weather before heading out. A
browser tab is slow and doesn't fail gracefully on a bad connection; you
want a CLI that gets you the number in seconds or fails cleanly.

## Situation
It's midday, you're about to pay a vendor quoted in USD and want the INR
figure before you approve the transfer. Wifi is spotty. You run the tool
once — either it gives you the number in under a couple of seconds, or it
tells you plainly it couldn't reach the API. No hang, no ambiguity.

## Scope
- One CLI invocation returns one live value from a public API: pick
  either a currency conversion (`fx USD INR 100`) or current weather for
  a location, and commit to it in your ADR.
- Every network call carries a context timeout; a slow API produces a
  clear message within a bounded, stated time — never an indefinite hang.
- Transient failures (5xx, connection reset) are retried with backoff
  before the call is given up on.
- No network / unreachable API prints a one-line human-readable message
  and a non-zero exit — never a raw error or stack trace.
- A successful result is printed in a stable, parseable format.

## Non-goals
- No caching of results across runs.
- No historical or time-series data.
- No multiple locations/currencies queried in one invocation.
- No interactive prompts.

## How it should NOT work
- Never hangs indefinitely waiting on a stalled connection.
- Never prints a raw stack trace or Go error value to the user for a
  network failure.
- Never retries forever without eventually giving up and reporting
  failure.
- Never treats a successful-but-empty or malformed API response as a
  valid result.

## Acceptance
- A mocked happy-path API response produces the correctly formatted
  output, exit 0.
- A mocked slow/hanging response triggers the context timeout and a clear
  one-line message within the documented timeout window, exit non-zero.
- A mocked 500 response triggers at least one retry with backoff before
  failing, verified by asserting call count in tests.
- A simulated unreachable host produces a one-line "couldn't reach the
  API" message, not a stack trace.
- All network calls in tests go through `httptest` (or equivalent) — no
  real network access required by `go test ./...`.
- `go test ./...` and `go vet ./...` clean.
- README with install and usage examples.
- ADR names a real consumer (per the rung rules: you, checking a live
  number before you act on it).

## Starting nudge
Stand up an `httptest.Server` before writing anything against the real
API — script it to return a slow response, a 500, and a malformed body,
and let those three failing tests drive the timeout/retry/error-message
code, in that order.

## ADR question
How do you make network code testable?
