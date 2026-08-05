# Rung 4, Option A — Parallel file hasher/dedupe

**Concept:** Worker pools, bounded parallelism, cancellation, races.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
The previz startup's render-output directories accumulate huge numbers of
large files, and re-run jobs leave duplicates behind. Hashing everything
serially to find them takes forever; you want a hasher that uses all the
cores you have without spawning more work than the machine can handle.

## Situation
You've got a render-output directory with tens of thousands of frames
from a job that got re-run twice. You want to know which files are exact
duplicates so you can reclaim disk, without waiting an hour for a
single-threaded pass.

## Scope
- Hashes every file under a given directory tree (recursively) and
  reports groups of files that share an identical hash.
- Hashing runs across a bounded number of concurrent workers, not one
  goroutine per file.
- Progress is visible while running (e.g. files processed so far, out of
  total).
- The first unrecoverable error (e.g. a file that can't be read) cancels
  remaining in-flight work rather than running every file to completion
  regardless.
- Runs against a large real directory without exhausting memory or file
  descriptors.

## Non-goals
- No deletion of duplicate files — report only.
- No cross-machine or network hashing.
- No incremental/cached hashing between runs.
- No GUI.

## How it should NOT work
- Never spawns a number of goroutines that scales with file count instead
  of a bounded worker count.
- Never keeps processing remaining files for minutes after a fatal error
  before reporting it.
- Never produces a race-detector warning under concurrent access to
  shared state.
- Never reports two files as duplicates when their contents differ, or
  vice versa.

## Acceptance
- Run against a fixture directory with known duplicate and unique files;
  output correctly groups the exact duplicates.
- Concurrency is demonstrably bounded (a configurable worker count,
  verified by test — no unbounded goroutine spawn per file).
- Progress output is visible during a run over many files.
- Injecting one unreadable file causes the run to cancel remaining
  in-flight work and report the error, verified by test.
- `go test -race ./...` clean.
- `go test ./...` and `go vet ./...` clean.
- README with install and usage examples.
- ADR names the consumer: your startup's render-output directories,
  hashed for real.

## Starting nudge
Build a small fixture directory with a handful of duplicate and unique
files plus one unreadable one, and write the cancellation test against
that fixture first — proving the run stops promptly on the bad file is
the part worth getting right before optimizing anything.

## ADR question
Channels vs errgroup vs semaphore — pattern and why.
