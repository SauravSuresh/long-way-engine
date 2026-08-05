# Rung 16, Option C — OpenTelemetry end-to-end

**Concept:** Correctness under failure — the platform's operations rehearsal.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
When something in your multi-service, multi-queue stack is slow, you
have no way to see where the time actually goes across service and
queue hops — only scattered logs from each piece, read separately and
lined up by hand.

## Situation
A request feels slow end to end and you don't know if it's the API
handler, the queue wait, or the worker. Instead of guessing from
separate log files, you pull up one trace and the time is accounted for,
hop by hop, in one view.

## Scope
- OpenTelemetry instrumentation across at least two service boundaries
  and one queue boundary (e.g. API → job queue → worker) in your
  existing stack.
- Trace context propagates across every hop — a single trace ID ties the
  whole request together, visible in a trace viewer (Jaeger or a
  documented equivalent).
- Each span records enough detail (name, duration, key attributes) to
  distinguish where time is spent.
- A specific, real latency question about your own stack is posed, then
  answered using an actual captured trace, not a synthetic one.
- The trace covers a real request through the real running stack, not a
  mocked pipeline.

## Non-goals
- No metrics or logging overhaul beyond what's needed to support
  tracing.
- No sampling-strategy sophistication beyond what's needed to capture
  the demonstrated trace.
- No commercial APM vendor integration required — a self-hosted/local
  trace viewer is enough.
- No new rung follows this one — this is inside the last rung of the
  ladder; from here, build time moves to the platform's own milestones.

## How it should NOT work
- Never a trace loses its trace ID crossing a service or queue boundary,
  showing up as disconnected fragments instead of one trace.
- Never a span's duration double-counts or omits time actually spent.
- Never the latency question is answered by guessing rather than reading
  it directly off the captured trace.
- Never instrumentation changes the observable behavior of the request
  being traced.

## Acceptance
- A real request through the stack produces one trace, viewable in a
  trace viewer, with a single trace ID spanning every hop (API, queue,
  worker) — screenshot or exported trace JSON committed.
- Each span is individually inspectable (name, duration,
  parent/child relationship), and the sum of relevant span durations
  accounts for the request's observed end-to-end latency within a
  documented margin.
- A specific latency question about the real stack is stated up front,
  then answered in the write-up using numbers cited from the captured
  trace, not estimated.
- Trace-context propagation is verified specifically across the queue
  boundary — a test or demonstrated run shows the worker's span is
  correctly parented to the enqueuing request's span, not orphaned.
- README documents how to run the trace viewer locally and reproduce the
  captured trace.
- ADR states the answer to the latency question and what would have
  hidden it (e.g. missing spans, broken context propagation) had
  instrumentation been incomplete.

## Starting nudge
Get trace context propagating across the hardest hop — the queue
boundary — before instrumenting anything else. That's where trace IDs
most commonly drop silently, and proving it survives that hop first
tells you the rest of the instrumentation is just repeating a pattern
that already works. Pull Release It! once you see what an incomplete
trace hides.

## ADR question
What failure mode does this prove you can survive, and what failure
mode is still unguarded after it?
