# Rung 2, Option C — Local bookmarks manager

**Concept:** File formats, atomic writes, recovery. Data survives `kill -9`.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Useful links pile up across browser tabs and scattered notes with no
durable, searchable home. You want a CLI bookmark store — tagged,
searchable, and safe: a save either fully lands or doesn't happen at all,
even if the process dies mid-write.

## Situation
You're reading a post about a rendering technique worth remembering. You
save it with a tag from the terminal: `bm add <url> -tags previz,render`.
Weeks later you search by that tag and find it instantly, and you never
once worry that a bad save silently ate an earlier bookmark.

## Scope
- Adds a bookmark with a URL and one or more tags: `bm add <url> -tags a,b`.
- Lists or searches bookmarks by tag and/or a substring match on URL or
  title: `bm list -tag previz`.
- Each save is atomic — a save is either fully present after the command
  returns, or (on failure) not present at all; no partial entries.
- On startup, the full bookmark set is rebuilt by reading the on-disk
  file — no separate index file is trusted as the source of truth.
- A truncated/corrupted tail of the file is detected and discarded on
  startup without losing the valid entries before it.

## Non-goals
- No browser extension or import from browser bookmark files.
- No link-rot / dead-link checking.
- No fetching or storing page content.
- No syncing across machines.

## How it should NOT work
- Never leaves the store in a half-written state after a kill mid-save —
  no partial or truncated entry visible on restart.
- Never loses bookmarks that were saved before a later corruption.
- Never returns duplicate or stale results because of a botched write.

## Acceptance
- `bm add <url> -tags a,b` followed by a fresh process invocation of
  `bm list -tag a` shows it — state rebuilt from the file, not memory.
- A kill-mid-write test kills the process during a save and shows, on
  restart, that all prior bookmarks are present and no partial entry
  exists.
- A corrupt-file test truncates/corrupts the tail and shows the store
  starts cleanly, retaining every bookmark before the corruption.
- A benchmark for search/list over a generated set of many bookmarks is
  committed (`go test -bench`).
- `go test ./...` and `go vet ./...` clean.
- README with install and usage examples.
- ADR names a real consumer: your own accumulated links, stored for real.

## Starting nudge
Seed the store with a real dump of bookmarks you already have scattered
across tabs and notes, then write the kill-mid-write test against that
exact file. Real data surfaces the ugly cases — duplicate URLs, odd
unicode in titles — that a synthetic fixture won't.

## ADR question
Log vs snapshot vs rewrite-whole-file — and when do you fsync?
