# Feature spec — the seasons layer

*Charted 2026-10-11 via wayfinder map [#6](https://github.com/SauravSuresh/long-way-engine/issues/6);
decisions in tickets #7–#13. Implemented the same day; this document is the
reference for what was built and why. Vocabulary: `CONTEXT.md`.*

---

## Goal

One focus at a time. The engine already runs N syllabuses in parallel, each
with its own ritual times, Todoist project and streak. In practice that
stacked everything onto the same evenings and the owner choked. The seasons
layer sits above the syllabuses and decides, for every date, which single
**Milestone** holds the owner's **deep block**; everything else is paused.
It is modelled on the owner's "Seasons" planning page (Deep Work / Slow
Productivity rules: sequence don't sacrifice, few things at once, short
protected depth, a hard stop).

## Non-goals

- The XP system is untouched.
- Bucket contents and ordering are the owner's call, made in the planner,
  not here.
- No two-way sync with the Claude artifact; it was the design reference.
- Per-syllabus streaks, cards and reflections keep working; they are no
  longer the headline but nothing is deleted.

## Opt-in

The layer is on iff `seasons.yaml` exists at the repo root. Without it every
code path below is skipped and the engine behaves exactly as before.

## Files

| File | Owner | Written by |
|---|---|---|
| `seasons.yaml` | the owner | planner (`docs/plan.html`) or by hand |
| `state/seasons.yaml` | the engine | daily run, `lw season` |
| `docs/assets/catalog.json` | the engine | daily run (syllabus catalog for the planner) |
| `docs/assets/data.json` → `seasons` | the engine | daily run (forecast + progress for planner and dashboard) |

### `seasons.yaml`

```yaml
todoist_project_id: "<Seasons project>"   # bare-season blocks + discipline tasks
rhythm:
  sleep: {from: "22:00", to: "05:30"}
  fixed_hours: {from: "09:30", to: "18:30", days: [monday, …, friday]}
  shutdown: "21:00"
  rest_week: true
  deep_blocks:                 # weekday absent = no block
    monday: {start: "07:30", minutes: 90, lane: main}
    tuesday: {start: "07:30", minutes: 90, lane: side}
bucket:                        # ordered; order is the only decision
  - id: marketplace-rungs-1-5  # stable slug, generated once
    name: Marketplace rungs 1–5
    area: Work
    hours: 200
    lane: main
    syllabus: marketplace-builder   # optional; absent = Bare Season
    modules: [1, 5]                 # or track: {category, item}; or neither = whole syllabus
    pin_start: 2026-10-20           # optional earliest start
disciplines:
  - id: anki
    name: "Anki · {milestone}"  # {milestone} = current main season's name, "Rest" in a rest week
    minutes: 20
    start: "06:55"
    days: [monday, …, sunday]   # default every day
```

Lanes are implied: two lanes iff any block has `lane: side`. Validation
(`src/seasons.py: validate`, run at startup and by `lw`): slug ids, unique,
hours ≥ 1, block minutes ≥ 15, times `HH:MM`, a bound syllabus exists and is
enabled in `config.yaml`, track declared, module range within the syllabus,
at most one of track / modules.

### `state/seasons.yaml`

```yaml
milestones:
  marketplace-rungs-1-5:
    logged: {2026-10-13: 90}  # minutes per IST date
    done: null                # ISO date set by `lw season done`
rest_until: null
rests: [{from: …, to: …}]     # past rest weeks, for the streak walker
last_run: {main: <id>, side: <id>, resting: false, paused: [<syllabus keys the layer paused>]}
```

The current main/side season is **derived** every run from bucket order and
state, never stored. Done milestones stay in the bucket; state holds progress.

## Forecast (`src/forecast.py`, canonical; `docs/assets/forecast.js`, port)

Day-by-day simulation from today (the 03:00 IST run precedes the block).
Current main/side = first not-done milestone per lane, regardless of hours.
Each block day subtracts that weekday's minutes from the lane's current
milestone; remaining = hours × 60 − logged. `pin_start` is an earliest start
with no pre-emption. When a **main** milestone finishes and others remain,
a 7-day rest week follows in which both lanes skip blocks and disciplines
continue. Side-marked days with an empty side queue go to main; when the main
queue is empty, side milestones take main blocks. Hours reached but not done:
the milestone ends today in the forecast and its tasks keep firing until
`lw season done`. Horizon 730 days. Both implementations are tested against
`tests/golden/seasons/*.yaml`.

## Daily run (`src/season_run.py`, hooked from `src/main.py`)

1. **Load + validate** `seasons.yaml`; errors fail the run (exit 2) like a
   bad `config.yaml`.
2. **Pause reconciliation** per syllabus: in-season set = {main, side}
   syllabuses, empty during a rest week. Off-season → open an indefinite
   pause (recorded in `last_run.paused`). Back in season → close it
   (`pause_history` gains the interval, so `derive_month` counts only
   in-season days). Only pauses the layer opened are lifted, except an
   owner pause whose `paused_until` has passed, which is lifted too.
3. **Ritual gating** inside `run_for_syllabus`: a ritual fires only if its
   syllabus is in-season and (it has no `track` gate, or its gated track is
   the season's bound track). A ritual with `slot: deep_block` has its due
   time replaced by the block start and fires only when today's block
   serves that syllabus's milestone. Module-bound seasons do not change
   gating.
4. **Season tasks**: if no slot ritual covered today's block, one generic
   task "Deep block · <milestone> (<minutes> min)" at block start, in the
   syllabus's Todoist project if bound, the Seasons project if bare, id
   `seasons:block:<id>:<date>`. One task per discipline per listed day,
   id `seasons:disc:<id>:<date>`, in the Seasons project; `sunday_off` does
   not apply to disciplines.
5. **Sweep + credit**: the existing past-due sweep marks completions; a
   completed block task credits that weekday's block minutes onto its due
   date, once per day per milestone. Minutes never come from Todoist.
6. **Persist** `state/seasons.yaml` with `last_run`.

## `lw season`

`status` (current main/side/rest + forecast table), `done [id]` (sets
`done`; starts a rest week if it was main, `rest_week` is on and others
remain; records the rest in `rests`), `log <minutes> [--date] [--milestone]`,
`rest-end`. Writes state and auto-commits like the other `lw` commands.

## Dashboard (`src/season_dashboard.py`)

`config.yaml` → `dashboard.sections: [seasons, syllabus_cards]` sets page
order; omit a name to hide it; default is both when the layer is on. The
TRMNL band keeps its markup, classes and 800×480 contract; with the layer on
its tiles become main season / side season (or disciplines) / disciplines,
with the deep-work streak. The Seasons section is server-rendered and
read-only: hero line, today line, seasons chart, four-week heatmap, bucket.

Streaks: deep-work streak = consecutive block days with logged minutes,
walking back from yesterday, skipping days without a block and rest weeks.
One streak per discipline over completed discipline tasks.

## Planner (`docs/plan.html`)

Edits the whole owner file with live forecast; never writes engine state.
Reads `catalog.json` and `data.json` from Pages, `seasons.yaml` via the
GitHub contents API when a fine-grained token (contents: read/write on this
repo) is saved in the browser, else read-only from raw.githubusercontent.com.
Commit = PUT with sha; a 409 means reload. Download is the fallback.
`?src=<url>` previews any file. Research behind it: #7 (Pages/API facts),
#8 (Todoist completion data).

## Turning it on

1. Create a Todoist project for bare seasons and disciplines; note its id.
2. `cp examples/seasons.example.yaml seasons.yaml`, set `todoist_project_id`,
   fill the bucket (or do it in the planner once a token is saved).
3. Commit and push. The next daily run reconciles pauses, creates the
   block and discipline tasks, and renders the Seasons section.
4. Optional: a fine-grained PAT for the planner; paste it once in
   `docs/plan.html`.

## Open questions (map fog)

- Reflection file paths for the life-wide weekly and the season
  retrospective; what happens to per-curriculum reflection dirs.
- Migration notes for existing Todoist caches when a syllabus goes
  off-season mid-week (today its already-created tasks simply age out).
