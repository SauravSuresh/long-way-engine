# Rung 14, Option C — HTTP/1.1 server from raw TCP

**Concept:** Below HTTP — parsers, connections, backpressure.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
`net/http`'s server hides exactly what's happening on the wire. You want
to know what an HTTP server actually does, byte by byte, by implementing
enough of HTTP/1.1 yourself to serve your real rung 6 API — no server-side
`net/http` underneath.

## Situation
`curl -v` against your server should look completely ordinary — status
line, headers, body, in the right shape — except every byte of that
response came from parsing and framing code you wrote, not from
`net/http`'s server.

## Scope
- A raw TCP listener with your own HTTP/1.1 request-line, header, and
  body parsing — server-side parsing is yours, not `net/http`'s server
  (using `net/http`'s client types in tests is fine).
- Enough of HTTP/1.1 to correctly serve rung 6's existing API: request
  line, headers, `Content-Length` bodies, correct status lines, and
  persistent connections (keep-alive) for the common case.
- A protocol parser that is its own component, with its own unit tests.
- Correct handling of concurrent client connections, race-clean.
- A stated, documented policy for a client that sends data too slowly
  (a stalled/slow-loris style request) — explicit and tested.

## Non-goals
- No HTTP/2 or HTTP/3.
- No chunked transfer-encoding unless your ADR argues for it.
- No TLS — plaintext HTTP only.
- No full RFC 7230 compliance — a documented subset that correctly
  serves rung 6's real routes is enough.

## How it should NOT work
- Never a malformed request line or header crashes the server or hangs
  the connection forever.
- Never two requests on the same persistent connection interleave into
  corrupted output.
- Never a slow-loris style client ties up a server resource indefinitely
  with no timeout.
- Never `curl` against a real rung 6 endpoint gets back a response it
  can't parse.

## Acceptance
- `curl -v http://localhost:<port>/<rung-6-route>` returns a valid
  HTTP/1.1 response `curl` parses cleanly, matching rung 6's documented
  API.
- The protocol parser has its own unit tests covering valid requests and
  at least 5 malformed inputs (missing `Content-Length`, bad request
  line, oversized headers, etc.), independent of socket-handling code.
- A concurrency test opens multiple simultaneous connections making real
  requests and passes under `go test -race`.
- A test simulates a stalled/slow client and asserts the documented
  timeout/policy disconnects it instead of hanging a server resource
  indefinitely.
- A test sends two requests over one persistent connection and gets two
  correct responses, proving keep-alive works.
- `go test ./...` and `go vet ./...` (with `-race`) clean.
- README documents exactly which parts of HTTP/1.1 are supported and
  shows a real `curl -v` transcript.

## Starting nudge
Get a single request/response cycle working over a fresh connection per
request first — parse the request line and headers, write a correct
status line and body, close the connection — before adding persistent
connections or concurrency. Keep-alive and backpressure only make sense
to build once the single-shot path is provably correct.

## ADR question
Event loop vs goroutine-per-conn vs shards — measure.
