# Rung 12, Option A — Dockerize the rung 6–11 stack

**Concept:** Packaging, config, graceful shutdown, health — production shape.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Right now your lab service runs however you happen to start it that day —
`go run` in a terminal you forget about, config scattered across shell
exports you half-remember, no clean way to stop it without killing
requests mid-flight. You want it packaged as something you can start,
stop, and hand off without re-deriving how it boots every time.

## Situation
You've just rebuilt your laptop, or you're handing the service to a
teammate for the afternoon. Instead of walking them through five
environment variables and a `go run` incantation, they run one
`docker-compose up`, watch `/healthz` go green, and they're working.

## Scope
- Multi-stage Dockerfile: the final runtime image contains no build
  toolchain, source tree, or dev dependencies — only what's needed to run.
- `docker-compose` (or equivalent) brings the service and its dependencies
  (Postgres, etc.) up with one command.
- `/healthz` (liveness) and `/readyz` (readiness) are distinct endpoints —
  readiness reflects real dependency state, not just "process is up."
- All configuration comes from environment variables; nothing
  environment-specific is baked into the image.
- SIGTERM triggers graceful shutdown: in-flight requests finish, new
  connections stop being accepted, then the process exits.
- The image is small on purpose — its size is measured and compared
  against a naive single-stage build to show the reduction.
- A README "how I deploy" runbook: exact commands from clone to a
  running, healthy container.

## Non-goals
- No Kubernetes manifests or orchestration.
- No CI/CD pipeline automation.
- No horizontal scaling or multi-instance concerns.
- No TLS termination — assume a reverse proxy handles that, or state it
  as explicit future work.

## How it should NOT work
- Never SIGTERM kills the process immediately, dropping whatever request
  was in flight.
- Never a secret or environment-specific value is baked into an image
  layer.
- Never the final image carries build tools, source, or test
  dependencies that bloat it for no runtime benefit.
- Never `/readyz` reports healthy while a real dependency (e.g. the
  database) is actually unreachable.

## Acceptance
- `docker build` produces the runtime image; its size is documented next
  to the size of an equivalent single-stage build, showing the reduction.
- `docker-compose up` (one command) brings the service and its
  dependencies up; `/healthz` returns 200.
- A test or documented run shows `/readyz` returning non-200 before a
  dependency is ready and 200 once it is.
- A test or documented run sends SIGTERM to a running container mid a
  slow in-flight request: the request completes successfully, no new
  connection is accepted after the signal, and the container exits.
- `docker history` (or equivalent layer inspection) shows no secret or
  environment-specific value baked into the image; all config is read
  from environment variables at startup, documented in the README.
- README "how I deploy" runbook covers clone → build → run → verify
  healthy, with real commands.
- ADR answers what's env, what's flag, what's file — and why.

## Starting nudge
Wire graceful shutdown in the Go service itself first — `http.Server.Shutdown`
against a context canceled on SIGTERM — and get it working under plain
`go run` before you touch Docker at all. Debugging shutdown behavior
inside a container, on top of debugging it in the process, is miserable;
the image becomes almost mechanical once the process already shuts down
cleanly on its own.

## ADR question
What's env, what's flag, what's file — and why?
