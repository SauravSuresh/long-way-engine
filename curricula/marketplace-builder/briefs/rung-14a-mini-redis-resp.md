# Rung 14, Option A — Mini-Redis speaking RESP

**Concept:** Below HTTP — parsers, connections, backpressure.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Every store you've built so far has hidden the wire behind a library or
a JSON-over-HTTP handler. You want to understand a real binary protocol
by implementing one from raw bytes, and end up with something you can
actually poke at using the real `redis-cli` — not a toy only your own
client understands.

## Situation
You want to inspect a key in your own store the exact way you inspect
one in real Redis: `redis-cli -p 6380 GET foo`. Because your server
speaks RESP, that just works — no custom client, no translation layer.

## Scope
- A TCP server implementing RESP (RESP2 at minimum) well enough for the
  real `redis-cli` binary to connect and run your supported commands.
- A protocol parser that is its own component, with its own unit tests,
  independent of connection/networking code.
- Correct handling of multiple concurrent client connections.
- Race-detector clean under concurrent access from multiple clients
  hitting the same keys.
- A stated, documented policy for a client that can't keep up (a slow
  reader whose buffer fills) — explicit, not accidental.

## Non-goals
- No full Redis command set — a documented subset is fine.
- No persistence (AOF/RDB) — in-memory only, unless your ADR argues
  otherwise.
- No clustering or replication.
- No RESP3 or pub-sub unless deliberately chosen and argued in the ADR.

## How it should NOT work
- Never a malformed RESP frame from one client crashes the server or
  corrupts another client's connection.
- Never a concurrent command on a shared key races under `-race`.
- Never a slow or stuck client silently blocks every other connected
  client with no documented policy handling it.
- Never real `redis-cli` receives a response it can't parse for a
  supported command.

## Acceptance
- `redis-cli -p <port> SET foo bar` then `redis-cli -p <port> GET foo`
  returns `bar` against the real `redis-cli` binary.
- The protocol parser has its own test file covering valid frames and at
  least 5 malformed/edge frames (empty, truncated, wrong type marker,
  oversized, etc.), independent of any socket code.
- A concurrency test opens multiple simultaneous connections issuing
  overlapping commands against shared keys and passes under
  `go test -race`.
- The documented slow-client policy is exercised by a test — a client
  that stops reading is handled per the stated policy (e.g.
  disconnected after a bound) rather than left blocking the server.
- `go test ./...` and `go vet ./...` (with `-race` in CI) clean.
- README lists the exact supported command subset and shows a real
  `redis-cli` session against the server.

## Starting nudge
Write the parser tests against raw byte slices of RESP frames before you
open a single socket — bulk-string lengths, arrays, and nil all have
enough edge cases that you want the parser solid before concurrency
makes debugging harder. This is also a fair rung to reach for a systems
language in, if you've been meaning to.

## ADR question
Event loop vs goroutine-per-conn vs shards — measure.
