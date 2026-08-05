# Rung 11, Option B — Email digest sender with scheduling and dedup

**Concept:** Background work that survives crashes.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
You want a periodic digest email — of things worth reviewing, whatever
you decide belongs in it — sent reliably, without duplicate sends when
the sending process restarts or two workers overlap.

## Situation
Your digest job runs on its usual schedule, but the process happens to
restart mid-run because of a deploy. Instead of a recipient getting the
same digest twice, or nobody getting one at all, exactly one digest goes
out per recipient for that period, no matter what the process did in
between.

## Scope
- Digest jobs are enqueued per recipient per period.
- Failed sends retry with backoff up to a max-attempts limit, after
  which the recipient's job for that period lands in a dead-letter
  state instead of retrying forever.
- A worker crash mid-send doesn't lose the job — it's either confirmed
  sent or safely retried, never ambiguous.
- Concurrent workers never send the same digest to the same recipient
  for the same period twice — deduplicated by a key such as
  recipient + period.
- A real send path is exercised end to end, even if it targets a test
  inbox or a log rather than a live mail provider.

## Non-goals
- No HTML email templating system beyond a basic template.
- No unsubscribe management UI.
- No real third-party email service integration required — a logging
  or dev sender is sufficient.
- No per-recipient schedule customization beyond a fixed period.

## How it should NOT work
- Never sends the same recipient the same period's digest twice, even
  under concurrent workers or a crash-and-retry.
- Never retries a permanently failing address forever instead of
  dead-lettering it.
- Never marks a digest as sent when the send actually failed.
- Never a crash mid-send loses track of whether it went out.

## Acceptance
- A dedup test races two concurrent workers against the same
  recipient+period digest and asserts exactly one send.
- A kill-mid-send test shows the job recovers to a known state — either
  confirmed sent or safely retried, never both or neither.
- A max-attempts test drives a permanently failing recipient past the
  limit and asserts it dead-letters instead of retrying forever.
- A backoff test asserts increasing delay between retry attempts.
- `go test ./...` and `go vet ./...` clean; README documents how
  digests are scheduled and how to inspect dead-lettered ones.
- The ADR justifies `SKIP LOCKED` over naive polling and states when
  you'd graduate to a real broker.

## Starting nudge
Define the dedup key — recipient plus period — and write the
concurrent-send test against it before building the actual
email-sending code. That key is what makes "no double-processing under
concurrent workers" true or false, and it's cheap to get wrong if it's
bolted on after the send logic already exists.

## ADR question
Why SKIP LOCKED beats naive polling; when would you graduate to a real broker?
