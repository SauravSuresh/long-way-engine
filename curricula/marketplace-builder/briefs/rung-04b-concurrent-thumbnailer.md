# Rung 4, Option B — Concurrent thumbnailer

**Concept:** Worker pools, bounded parallelism, cancellation, races.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Image directories — reference photos from a shoot, gear photos — pile up
faster than you can browse them at full size. You want thumbnails
generated quickly across a whole directory, using multiple cores, without
one bad file corrupting the batch or a runaway number of goroutines
choking the machine.

## Situation
You've just imported a folder of a few hundred reference photos from a
shoot and want quick thumbnails to browse before going through the
full-size versions one by one.

## Scope
- Generates a thumbnail for every image file in a given directory, for a
  defined set of supported formats stated in the README.
- Thumbnailing runs across a bounded number of concurrent workers.
- Progress is visible while running.
- The run's policy for a fatal error (e.g. a corrupt image where the
  format claims to be supported) is explicit and stated in the ADR, and
  the first such error cancels remaining in-flight work.
- A worker that fails mid-write never leaves a partial or corrupt
  thumbnail file on disk in place of a prior good one or a missing one.

## Non-goals
- No image editing or filters beyond resizing.
- No directory watching or live regeneration.
- No GUI gallery.
- No network-hosted images.

## How it should NOT work
- Never spawns a number of goroutines that scales with image count
  instead of a bounded worker count.
- Never leaves a partially-written, corrupt thumbnail file on disk after
  a worker fails mid-write.
- Never produces a race-detector warning under concurrent access to
  shared progress or error state.
- Never silently drops a file from processing without reporting it.

## Acceptance
- Run against a fixture directory of valid images; every one gets a
  correctly generated thumbnail.
- Concurrency is demonstrably bounded, verified by test.
- Progress output is visible during a run over many files.
- Injecting one corrupt/invalid image file is reported clearly and leaves
  no partial/corrupt thumbnail on disk, verified by test.
- The first fatal error cancels remaining in-flight work, verified by
  test.
- `go test -race ./...` clean.
- `go test ./...` and `go vet ./...` clean.
- README with install and usage examples.
- ADR names a real consumer: your own image directories, thumbnailed for
  real.

## Starting nudge
Write the test for "a worker fails mid-write and no partial file is left
behind" before writing the thumbnailing code itself — that constraint
shapes how every worker has to behave, and it's cheaper to bake in than
retrofit.

## ADR question
Channels vs errgroup vs semaphore — pattern and why.
