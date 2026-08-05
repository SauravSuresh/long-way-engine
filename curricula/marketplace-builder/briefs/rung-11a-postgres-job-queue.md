# Rung 11, Option A — Job queue on Postgres for your lab service

**Concept:** Background work that survives crashes.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Your lab service, carried forward from rungs 6–10, occasionally needs to
do something slow or unreliable in the background — send a notification,
process something uploaded, whatever it is by now — without making the
HTTP request wait for it or losing the work if a worker dies mid-job.

## Situation
A request to your lab service needs to kick off something that takes
longer than an HTTP client should reasonably wait for. It enqueues a job
in Postgres instead of doing the work inline, a worker picks it up, and
if that worker dies halfway through, another worker — or the same one
after a restart — picks the job back up instead of it vanishing.

## Scope
- A job table in Postgres; enqueue writes a row, and workers claim rows
  using `FOR UPDATE SKIP LOCKED` (or your language's equivalent locking
  read) so concurrent workers never grab the same job.
- Failed jobs retry with backoff up to a max-attempts limit, after which
  they land in a dead-letter state instead of retrying forever.
- A worker killed mid-job leaves the job recoverable — not lost, not
  silently marked done — verified by a test that simulates the kill.
- Running multiple workers concurrently against the same queue never
  processes one job twice, verified by test.
- At least one real job type from your lab service actually flows
  through this queue, not just a synthetic test job.

## Non-goals
- No external broker (Redis, RabbitMQ, etc.) — Postgres is the whole
  queue for this rung.
- No distributed workers across machines — multiple workers on one
  machine is enough.
- No job scheduling or cron — enqueue-and-process only.
- No priority queue or ordering guarantees beyond roughly FIFO.

## How it should NOT work
- Never lets two concurrent workers both successfully claim and process
  the same job row.
- Never a job that exceeds max-attempts keeps retrying instead of
  landing in dead-letter.
- Never a worker crash mid-job leaves the job permanently stuck
  claimed-but-unfinished with no way to recover it.
- Never a job silently dropped between enqueue and its first claim
  attempt.

## Acceptance
- A concurrency test runs N workers against M enqueued jobs and asserts
  each job was processed exactly once, using real concurrent
  goroutines/processes against a real Postgres instance.
- A kill-mid-job test simulates a worker dying after claiming a job but
  before completing it, and shows the job is eventually reclaimed and
  completed.
- A test drives a job past its max-attempts count and asserts it lands
  in a dead-letter state and stops being retried.
- A backoff test asserts increasing delay between retry attempts, not
  immediate infinite retry.
- At least one real background task from your lab service is wired
  through this queue end-to-end.
- `go test ./...` and `go vet ./...` clean; README explains how to run
  workers and inspect dead-lettered jobs.
- The ADR justifies `SKIP LOCKED` over naive polling and states when
  you'd graduate to a real broker.

## Starting nudge
Write the concurrent-claim test before the worker loop's business
logic: spin up several workers against a handful of pre-enqueued jobs
and assert no job is processed twice. That's the property `SKIP LOCKED`
exists to guarantee, and the easiest thing to silently get wrong.

## ADR question
Why SKIP LOCKED beats naive polling; when would you graduate to a real broker?
