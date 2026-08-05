# Rung 12, Option B — VPS deploy with systemd

**Concept:** Packaging, config, graceful shutdown, health — production shape.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Your lab service has only ever lived in a terminal session on your own
machine — close the laptop and it's gone. You want it running on a
machine that stays up, restarts itself when it crashes or the box
reboots, backs up its own data, and answers to a real domain — because
you're about to depend on it staying alive for the rest of the ladder.

## Situation
You close your laptop for the weekend. Monday morning you open it back
up, hit your domain, and the service is just there — it never noticed
you were gone, because it hasn't been living in your terminal for weeks.

## Scope
- A systemd unit runs the service: starts on boot, restarts automatically
  on crash.
- A domain (or subdomain) resolves to the VPS and reaches the running
  service.
- Automated, scheduled backups of persistent data (e.g. Postgres), with
  at least one restore actually performed and verified, not just assumed
  to work.
- Configuration loaded from environment (a systemd `EnvironmentFile` or
  equivalent), never hardcoded in a unit file or committed to a repo.
- The deployed binary is built deliberately small (stripped, no
  unnecessary bundled assets) — its size is documented.
- A documented deploy process: the exact steps that update the running
  service on the box.
- The service stays up and reachable for the rest of the ladder — a real
  commitment, not a one-time demo.

## Non-goals
- No Kubernetes or container orchestration platform.
- No autoscaling.
- No automated CI/CD deploy pipeline — a documented manual deploy is
  fine.
- No multi-region or high-availability setup.

## How it should NOT work
- Never the service fails to come back after a VPS reboot.
- Never a crash takes the service down permanently with no automatic
  restart.
- Never a backup exists that was never actually restored and confirmed
  to work.
- Never a secret or credential sits in a world-readable file or gets
  committed to any repo.

## Acceptance
- `systemctl status <service>` shows the unit active and enabled
  (starts on boot) — documented in the runbook.
- Killing the service process directly and observing systemd restart it
  automatically within its documented restart policy — demonstrated.
- A simulated or real VPS reboot results in the service running again
  with no manual intervention — demonstrated.
- The domain resolves to the VPS and a request against it (e.g.
  `curl https://yourdomain/healthz`) reaches the running service.
- A backup is taken, then restored into a fresh database, and the
  restored data is verified to match — actually run, not just described.
- Config values are loaded via a systemd `EnvironmentFile` with
  restricted permissions; no secret appears in the unit file or any
  committed file.
- README "how I deploy" runbook: exact steps to push a new version of
  the service to this box.
- ADR answers what's env, what's flag, what's file — and why.

## Starting nudge
Get the systemd unit running your service with its restart policy first,
using whatever config values you'd otherwise pass on the command line —
that's the piece every other requirement here sits on top of. Domain,
backups, and the deploy runbook are all easier to reason about once you
can already kill the process and watch it come back on its own.

## ADR question
What's env, what's flag, what's file — and why?
