# Feature spec — reMarkable PDF delivery

*Drafted 2026-05-04. Not implemented. Implementation deferred until at least
one weekly review cycle has shipped under the engine's reflection workflow,
so the inputs are stable.*

---

## Goal

Get long-form text — articles, blog posts, and the engine's own filled
reflections — onto the owner's reMarkable Paper Pro at the right time, so
the reading and review work moves off-screen onto e-ink.

Two streams, distinct in source, content sensitivity, and timing:

1. **Fun reading.** Public articles + blogs the owner curates. Should
   appear on the rM ahead of the time the owner reads them — typically
   the morning of, before the daily-evening-hands-on slot ends.
2. **Review re-reads.** The four cadence reflections (weekly / monthly /
   quarterly / annual) the engine already produces. Should appear on the
   rM at the start of the next review window — Friday night for the
   week's filled reflection, last-Saturday morning for the month's, etc.

The engine never deletes content from the rM. The engine never edits the
text of an article. PDFs are write-once, owner removes manually.

---

## Non-goals

- Not a feed reader. Owner-curated lists only; no RSS, no smart
  recommendations, no automatic article discovery.
- Not a Pocket / Instapaper replacement. Articles arrive as PDFs of the
  current page render — no readability extraction beyond what the source
  page provides.
- Not a sync system. One-way push. Annotations made on the rM stay on
  the rM (Phase H+ might revisit).
- No reMarkable cloud account integration. Cloud auth surface is too big
  and the cloud API is unofficial. Direct device or static-host fetch
  only.
- No paid-content circumvention. If a URL needs auth, owner provides a
  cookie file (mirroring the JBlocklove approach). The engine never
  bundles credentials.

---

## Reference architecture

[`JBlocklove/remarkable-daily-pdf`](https://github.com/JBlocklove/remarkable-daily-pdf)
is the rM-side prior art and the basis for the device-side delivery
plan. Key shape:

- A small POSIX shell script + `wget` runs on the rM under a `systemd`
  timer.
- For each configured URL, downloads a PDF, generates a Xochitl UUID +
  metadata, drops it into Xochitl's storage. The document appears in
  the device library at next refresh.
- Cookie files for auth'd content live on-device under a known path.

That model is the right primitive: simple, debuggable, doesn't depend on
unstable cloud APIs. This spec adopts it as-is for the rM-side, and adds
an engine-side layer above it.

---

## Architecture decisions

### Where the engine lives in this pipeline

The engine prepares content. The rM fetches content. They never talk
directly.

```
┌────────────────────────────┐         ┌────────────────────────────┐
│ Engine (GitHub Actions)    │         │ reMarkable Paper Pro       │
│                            │         │                            │
│  1. Read state.yaml        │         │  systemd timer fires daily │
│     (curated URLs +        │         │                            │
│      reflection paths)     │         │  pulls from configured     │
│                            │         │  endpoints, drops PDFs     │
│  2. Generate PDFs:         │         │  into Xochitl              │
│     - articles from URLs   │         │                            │
│     - reflections from     │  ───>   │                            │
│       markdown             │         │                            │
│                            │         │                            │
│  3. Publish to two paths:  │         │                            │
│     - public outbox        │         │                            │
│       (GH Pages-served)    │         │                            │
│     - private outbox       │         │                            │
│       (NEVER published)    │         │                            │
└────────────────────────────┘         └────────────────────────────┘
```

The two outboxes are the contract.

### Public vs private outbox

| | Public outbox | Private outbox |
|---|---|---|
| Path | `outbox/public/` | `outbox/private/` |
| Sources | Articles fetched from public URLs | Filled reflection markdown |
| Tracked in git? | Yes (single source of truth) | **NO — `.gitignore`'d** |
| Served by GH Pages? | Yes | No |
| rM-side delivery | Plain `wget` against the GH Pages URL | Manual transfer (USB or `rcu`) until Phase 3 |

Reflections are owner's personal writing. They must NEVER reach a public
artifact. The split is enforced by:

1. `.gitignore` entry on `outbox/private/`.
2. A unit test that walks any public render artifact (HTML, PDF, JSON in
   `docs/`) and fails if it contains text that exists in any
   `reflections/` file.
3. A regression test that asserts the renderer for the private outbox
   refuses paths that resolve under `outbox/public/` or `docs/`.

### Why not push from engine directly to rM?

Considered. Rejected for these reasons:

- **rM cloud API is unofficial.** Endpoints, auth flow, and rate limits
  drift between firmware versions. Coupling the engine to that API would
  break the engine every time reMarkable ships an OS update.
- **Local push (USB/SSH) requires the engine to know about the device.**
  The engine runs in GitHub Actions; it has no LAN visibility to the
  owner's tablet.
- **Static hosting is already wired.** Phase F shipped GH Pages. The
  public outbox piggybacks on that path. One fewer credential, one fewer
  network hop.

For the private outbox: until a confidently-private push channel exists
(Phase 3 below), the owner moves files manually. The engine produces
them in a known path; owner uses USB or
[`rcu`](https://www.davisr.me/projects/rcu/) to drop them on the rM.

---

## Engine-side surfaces

### `articles.yaml` (new owner-curated config)

Mirror of the existing `task_templates/*.yaml` structure but for fun
reading.

```yaml
# articles.yaml — owner-curated, hand-maintained, free-text URLs.
- url: https://danluu.com/diseconomies-scale/
  cadence: once          # once-and-done; archived after fetch
  added: 2026-04-15
- url: https://lethain.com/staff-engineer-paths/
  cadence: once
  added: 2026-04-22
- url: https://www.bryanbraun.com/2024/.../some-essay
  cadence: once
  added: 2026-04-28
  cookie_file: cookies/example.txt   # optional, relative to repo root
```

- `cadence: once` is the only supported value initially. Future
  cadences (weekly digest, etc.) deferred until the once-path is stable.
- `added` is informational; engine doesn't act on it.
- `cookie_file` is the same shape as the JBlocklove approach.
- Engine fetches each URL exactly once per (URL, owner-edit) pair —
  hash-keyed dedup mirroring `external_id` but for articles. After
  first successful fetch, the article is "done"; subsequent runs skip
  it. Owner removes the entry when they want to forget about it.

### Reflection PDF triggers

| Reflection cadence | When PDF is generated | Where it lands |
|---|---|---|
| weekly (Friday) | Saturday 03:00 IST cron, IF the prior week's reflection has `status: filled` | `outbox/private/reviews/weekly/{iso_year}-W{iso_week:02d}.pdf` |
| monthly (last-Saturday) | Sunday 03:00 IST cron after the last-Saturday | `outbox/private/reviews/monthly/{year}-{month:02d}.pdf` |
| quarterly | Day-after the quarter-end cron | `outbox/private/reviews/quarterly/{year}-Q{quarter}.pdf` |
| annual | January 2 cron | `outbox/private/reviews/annual/{year}.pdf` |

Engine consults the existing reflection-walker output (status + path)
to decide whether to generate. If status isn't `filled`, no PDF — the
owner gets nothing to re-read until they finish the reflection.

### PDF generation

Markdown → PDF: use `pandoc` with the existing reflection template.
`pandoc` is a single binary, deterministic output, no Python deps.

URL → PDF: use a headless renderer. Two options to evaluate at
implementation time:

- **`wget` + `wkhtmltopdf`**: matches the JBlocklove approach; handles
  most static articles cleanly; fails on heavily JS-driven pages.
- **`weasyprint`** (Python): better typography, no JS support either,
  but installs as a Python dep so it lives inside the existing GH
  Actions environment.

Recommend wkhtmltopdf as the starter; revisit if articles render badly.
Engine tolerates a render failure per article — log a warning, continue
with the rest of the queue.

### Scheduling integration

Two new template kinds in the existing scheduler — additive, no changes
to the existing cadences:

```yaml
# task_templates/articles.yaml (NEW)
- id: daily-articles-fetch
  cadence: daily
  skip_if: [sunday]   # rest day, queue carries forward
  hook: fetch_articles  # NEW field — engine calls a registered hook
                        # rather than creating a Todoist task

# task_templates/reviews.yaml (NEW)
- id: weekly-review-pdf
  cadence: weekly
  day_of_week: saturday
  hook: emit_weekly_review_pdf
```

`hook` is a new field that says "instead of (or in addition to) creating
a Todoist task, dispatch this named callable." The hook registry is a
small dict in `src/main.py` mapping hook name → function. Failures
log-and-continue per the existing render-hook pattern.

This keeps article delivery on the same cron as task creation — one
schedule, one place to edit, one set of skip rules.

### Outbox lifecycle

- `outbox/public/articles/{date}/{slug}.pdf` — public articles.
- `outbox/private/reviews/{cadence}/{key}.pdf` — review re-reads.
- A separate `outbox/manifest.json` lists the files the rM should fetch
  next, with their public URLs (or "pickup-only" sentinels for private
  files). The rM-side script consults this manifest, not a directory
  listing.

Pruning: public PDFs older than 90 days are deleted at the end of each
run (matches the cache prune horizon). Private PDFs never auto-deleted
— owner removes manually.

---

## rM-side delivery

### Phase 1 — JBlocklove fork on the device

Configure the device's `download-pdfs` script to read from the public
outbox manifest at:

```
https://sauravsuresh.github.io/long-way-engine/outbox/manifest.json
```

The script iterates the URLs, downloads each via wget with the existing
JBlocklove plumbing, places PDFs in the right Xochitl directories.
Daily systemd timer fires; nothing on the engine side changes.

### Phase 2 — review PDF pickup

Owner manually transfers private review PDFs via USB or rcu after
running:

```
python scripts/build_outbox.py
```

(local, no network) which generates the private PDFs from filled
reflections. Manual sync model; minimal automation but zero privacy
risk.

### Phase 3 (deferred) — authenticated private channel

Eventually: a private GitHub repo that mirrors `outbox/private/`,
fetched by the rM with a deploy key. Or: an SSH push from a local
script the owner runs from their laptop. Defer until manual transfer
becomes annoying enough to warrant the surface area.

---

## Risks

1. **Article-fetch fragility.** wkhtmltopdf chokes on dynamic pages.
   Mitigation: log-and-skip per-article, owner sees gaps in the queue
   rather than a broken cron.
2. **rM firmware updates breaking JBlocklove plumbing.** Out of the
   engine's control. Spec inherits the upstream project's risk profile.
   Mitigation: pin to a specific commit of JBlocklove on the device.
3. **Privacy leak through misconfigured paths.** Reflections accidentally
   committed under `outbox/public/`. Mitigation: `.gitignore` +
   regression test that cross-checks public-render artifacts against
   reflection content (see Public vs private section).
4. **Storage growth on the rM.** 90-day window × ~daily articles ≈ ~100
   PDFs. Owner removes manually; not engine concern.
5. **Manifest race.** Engine writes manifest while rM reads it. Mitigation:
   atomic write (`tmp + rename`) on the engine side, mirror the cache
   pattern.
6. **Cookie file leak.** If `cookies/` is needed for paid content,
   committing it leaks credentials. Mitigation: `cookies/` in
   `.gitignore`, owner stores cookies on-device only.
7. **rM is offline when the timer fires.** PDF lands next time the device
   has wifi. JBlocklove handles this gracefully.

---

## Open questions (resolve before implementation)

1. **Articles cadence — daily or sub-daily?** Spec assumes one fetch
   per day at the same cron as the engine. If owner wants instant push
   on adding to `articles.yaml`, that needs a different trigger
   (workflow_dispatch on push, etc.). Likely defer to "daily" for v1.
2. **PDF generation toolchain — wkhtmltopdf vs weasyprint vs
   readability-extractor + pandoc?** Pick at implementation time after a
   one-day quality bake-off on a representative set of URLs (Dan Luu,
   LWN, NYT, a SubStack post, a Medium article).
3. **Review-PDF formatting.** Default to the `pandoc` markdown render?
   Or apply a custom rM-friendly stylesheet (larger margins, bigger
   font)? Recommend the latter; one CSS file shipped with the engine.
4. **Hook registry vs separate orchestrator.** Spec proposes adding a
   `hook:` field to templates. Alternative: a separate
   `outbox_orchestrator.py` that runs after the task scheduler. Hooks
   are tighter integration; orchestrator is cleaner separation. Re-evaluate
   when implementing.
5. **Manifest format.** JSON proposed, but a simple `urls.txt` may
   suffice if the rM-side script is adapted minimally. JSON future-proofs
   metadata (titles, dates, categories) at low cost.
6. **What about the daily reading book (`current_book`)?** Out of scope
   here — books are paper, not PDFs. Engine doesn't push book content.
7. **Failure surfacing.** Currently dashboard tracks engine errors
   only. Should article-fetch failures surface on the dashboard? Likely
   a small "outbox" section showing recent fetch results + failures.

---

## Phasing

| Phase | Scope | Done when |
|---|---|---|
| H1 | Outbox plumbing + manifest format. Articles only. wkhtmltopdf. JBlocklove on the device. | One week of daily article PDFs land on the rM with zero owner intervention. |
| H2 | Review-PDF generation from filled reflections. Manual USB transfer. | One full weekly review cycle produces a re-read PDF on Saturday morning. |
| H3 | Authenticated private channel for review PDFs (private repo + rM deploy key OR self-hosted webhook). Eliminates manual transfer. | Owner stops touching USB cables for two consecutive review cycles. |
| H4 (deferred) | Article-fetch quality work. Readability extraction. Per-source CSS. Pre-fetch readtime estimates. | Engagement: owner reads >50% of fetched articles. Surfaces in dashboard. |

---

## Constraints to hold

The existing engine constraints carry over without modification:

- Python ≥3.11. Stdlib + `requests`, `PyYAML`, `pytest`, plus
  whichever PDF tool wins the bake-off.
- No production Todoist writes outside `--dry-run` / sandbox flags. (This
  feature doesn't touch Todoist; mentioned for the avoidance of doubt.)
- Single clock injection point. Article fetch and PDF generation
  timestamps go through `src/clock.py`.
- Owner TZ everywhere; UTC only for cache stamps.
- No LLM in the runtime path.
- The repo is the system. `articles.yaml` is committed; cookies are not;
  reflections are; reflection PDFs are not.
- No web framework. No background daemons. The engine remains a
  cron-driven script with a hook registry.

— end of spec —
