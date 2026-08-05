# Rung 14, Option B — TCP chat server

**Concept:** Below HTTP — parsers, connections, backpressure.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
You want hands-on understanding of connection-level concurrency and
backpressure, built from raw sockets and testable with tools you already
have — not hidden behind a chat framework or a websocket library.

## Situation
You want to smoke-test a multi-client idea by opening several terminal
`nc localhost <port>` sessions side by side and watching a message typed
in one show up in the others, live, with no custom client involved.

## Scope
- A TCP server accepting multiple concurrent client connections.
- Clients join or create named rooms; a message sent by a client
  broadcasts to every other client in the same room.
- A self-documented, line-based (or otherwise simple) protocol with its
  own parser and its own unit tests.
- Correct concurrent handling of clients joining, leaving, and
  broadcasting — race-clean.
- A stated, documented policy for a slow client that can't keep up with
  broadcast volume (e.g. bounded buffer plus disconnect) — explicit and
  tested.
- Works against a real off-the-shelf client like `nc` or `telnet` — no
  custom client required to demo it.

## Non-goals
- No authentication.
- No private/direct messages between users — rooms only, unless your
  ADR argues otherwise.
- No persistence of chat history across restarts.
- No web UI.

## How it should NOT work
- Never one slow client's stalled socket blocks message delivery to
  every other client in the room.
- Never a client disconnecting mid-write corrupts another client's
  stream or crashes the server.
- Never two clients joining the same room concurrently race under
  `-race`.
- Never a message broadcasts to a room other than the sender's.

## Acceptance
- Two or more `nc` sessions joined to the same room: a message typed in
  one appears in the others.
- The protocol parser has its own unit tests, independent of networking
  code, covering valid lines and at least 5 malformed inputs.
- A concurrency test with many simulated clients joining, leaving, and
  broadcasting concurrently passes under `go test -race`.
- A test simulates a slow/non-reading client and asserts the documented
  policy kicks in (disconnect after a bound, or dropped messages per
  policy) without blocking delivery to other clients.
- `go test ./...` and `go vet ./...` (with `-race`) clean.
- README documents the protocol's message format and the slow-client
  policy, with a real `nc`/`telnet` walkthrough.

## Starting nudge
Get broadcast working single-threaded first — one room, blocking
sends, no concurrency guards — so the message-routing logic is right
before backpressure and races enter the picture. The slow-client policy
only becomes a real design decision once you can reliably reproduce a
client that stops reading.

## ADR question
Event loop vs goroutine-per-conn vs shards — measure.
