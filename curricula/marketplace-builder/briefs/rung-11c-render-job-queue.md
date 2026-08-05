# Rung 11, Option C — Render-job queue for the previz pipeline

**Concept:** Background work that survives crashes.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Previz render jobs are slow and sometimes fail for reasons outside your
control — a bad scene file, a GPU driver hiccup, whatever it is that
week — and right now they get run by hand or by a script you have to
babysit. You want a queue that runs them, retries transient failures,
and gives up cleanly on jobs that are never going to succeed, so you can
stop watching a terminal.

## Situation
You kick off a batch of render jobs before leaving for the day. One hits
a transient GPU driver hiccup halfway through. Instead of the whole
batch silently stalling or that one job vanishing, it retries
automatically, and if it still can't complete after a few tries, it's
sitting in a dead-letter list waiting for you in the morning instead of
buried in a log.

## Scope
- Enqueue a render job (referencing a scene/asset, from your lab
  service's catalog if you built one).
- Workers claim jobs using `FOR UPDATE SKIP LOCKED` (or your language's
  equivalent) and run them.
- Failed jobs retry with backoff up to a max-attempts limit, then land
  in a dead-letter state.
- A worker crash mid-render doesn't lose the job — it's recoverable,
  either retried or clearly marked stuck for inspection, never silently
  gone.
- Concurrent workers never both run the same render job.
- At least one real render — or a realistic stand-in that represents
  actual render duration and failure modes — actually runs through the
  queue.

## Non-goals
- No render-farm orchestration across multiple machines — single
  machine, multiple workers.
- No GPU/resource scheduling logic beyond one job claimed per worker.
- No render progress-percentage UI.
- No automatic classification of transient vs permanent failure types —
  a uniform retry policy is fine.

## How it should NOT work
- Never lets two workers both render the same job concurrently, wasting
  GPU time or corrupting shared output.
- Never a job that's failed past max-attempts keeps retrying instead of
  dead-lettering.
- Never a worker crash mid-render leaves the job stuck claimed forever
  with no recovery path.
- Never a completed render gets silently marked failed, or vice versa,
  due to a race between the worker finishing and recording the result.

## Acceptance
- A concurrency test runs multiple workers against multiple queued jobs
  and asserts each job is processed exactly once.
- A kill-mid-job test kills a worker mid-render and shows the job
  recovers and completes on retry or via another worker.
- A dead-letter test engineers a job to always fail and asserts it
  lands in dead-letter after max-attempts and stops retrying.
- A backoff test asserts increasing delay between retry attempts.
- At least one real or realistic-stand-in render job flows through the
  queue end to end.
- `go test ./...` and `go vet ./...` clean; README documents queue
  operation and dead-letter inspection.
- The ADR justifies `SKIP LOCKED` over naive polling and states when
  you'd graduate to a real broker.

## Starting nudge
Write the concurrent-claim test first, using a fake "render" that just
sleeps and fails on command, before wiring in anything that touches
your actual render pipeline. That fake gives you fast, deterministic
control over the exact failure modes this rung's tests need to
exercise.

## ADR question
Why SKIP LOCKED beats naive polling; when would you graduate to a real broker?
