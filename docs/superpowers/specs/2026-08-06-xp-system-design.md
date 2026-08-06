# XP system — design

Date: 2026-08-06
Status: approved (design round, owner sign-off)

## Problem

The engine tracks streaks and honesty but offers no positive reward loop.
The owner wants task completions to earn points, points to accumulate into
levels, and levels to unlock self-defined rewards (in the spirit of
Obsidian's grind-manager and Rewarder plugins).

## Decisions (from design round)

- **Level-unlock, not spending.** XP only grows; reaching level N
  permanently unlocks that level's reward. No currency, no claiming
  mechanics, no deductions.
- **Derived, not ledgered.** XP is recomputed from history on every engine
  run, exactly like streaks — no new mutation paths, no drift, idempotent.
  Trade-off accepted: XP updates when the cron (or a local run) happens,
  not the instant a task is ticked.
- **Weighted points** by task type, defaults in an owner-editable yaml.
- **Rewards are the owner's** — scaffolded file with placeholders, owner
  edits real rewards in.

## Architecture

### src/xp.py (new, pure — the streaks.py sibling)

No IO beyond what callers pass in. Inputs mirror the streak walkers plus
two local sources:

- per-syllabus task cache entries × the run's Todoist completion set
  (same walk `src/streaks.py` does),
- `ladder/*/meta.yaml` files (rung outcomes, extensions, failures),
- reflections metadata (`status: filled` frontmatter — a reflection pays
  only when actually written, not when the stub was created),
- state (for exam-gate counters) and the xp config.

Output dataclass `XPResult`: `total: int`, `by_source: dict[str, int]`
(keys: daily, weekly_ritual, reflections, deep_block, rungs, exam_gates,
streak_bonus), `level: int`, `level_progress: int`, `next_level_at: int`,
`unlocked: list[Reward]`, `next_reward: Reward | None`.

Classification of a cache entry uses what the cache already stores
(template id) joined to the loaded templates' cadence/labels: cadence
`daily` → daily; label `deep-block` → deep_block; other weekly rituals →
weekly_ritual. Completion detection is identical to the streak walkers'.

### xp.yaml (repo root, owner-editable)

```yaml
weights:
  daily: 10
  weekly_ritual: 25
  reflection_filled: 30
  deep_block: 40
  rung_shipped: 200
  rung_zero_extension_bonus: 50
  rung_extension_penalty: 25   # per extension, floor below
  rung_shipped_floor: 100
  rung_failed_moved_on: 50     # showing up matters
  exam_gate: 300
  streak_bonus_per_task: 5     # while daily streak >= threshold
  streak_bonus_threshold: 7

levels:
  base: 100
  growth: 1.4    # cumulative XP for level N = round(base * N^growth)
                 # L1 100, L2 ~264, L3 ~466, L5 ~957, L10 ~2612

rewards:
  - level: 2
    reward: "PLACEHOLDER — e.g. movie night, no guilt"
  - level: 4
    reward: "PLACEHOLDER — e.g. that lens filter"
  - level: 7
    reward: "PLACEHOLDER — e.g. weekend trip"
```

Missing file or missing keys → built-in defaults (same values as above);
unknown keys ignored. Rung scoring: shipped = `rung_shipped`
+ `rung_zero_extension_bonus` if no extensions, − `rung_extension_penalty`
× len(extensions), never below `rung_shipped_floor`; outcome failed =
`rung_failed_moved_on` (a retry that later ships scores as shipped —
failures list does not reduce the shipped score beyond its extensions).

### Wiring

- **Cron/local run:** `src/main.py` computes XP after streaks (it has the
  completion sets there) and adds an `xp` block to the dashboard data
  (`docs/assets/data.json`) at top level (XP is global across curricula,
  not per-syllabus). Dashboard HTML renders total, level, progress bar,
  and the reward ladder.
- **`lw status`:** one global line read from data.json (stale ≤ last
  cron, same as streaks): `XP 340 · Level 2 · 126 to Level 3 · 1 reward
  unlocked`. Graceful-absent (older data.json → no line).
- **`lw xp` (new subcommand):** plain print (no TUI): per-source
  breakdown, level + progress, then the reward ladder from xp.yaml with
  🔓 (level reached) / 🔒 per entry. Reads data.json for the completion-
  derived part; reads ladder meta + xp.yaml live (they're local files).

## Non-goals

- No spending/claiming flow, no notifications, no Todoist writes.
- No live XP on task-tick (derived model; next run picks it up).
- No per-curriculum XP totals in v1 (one global pool).
- No backfill semantics beyond what the data already gives: completions
  before the current start_date are ignored by the same rule the streak
  walkers use, so the fresh start of 2026-08-06 also starts XP at 0.

## Testing

- Pure unit tests for src/xp.py: classification, weights application,
  rung scoring incl. extension penalty floor and failed-moved-on, level
  curve boundaries, unlocked/next reward resolution, config defaults on
  missing file/keys.
- One integration-shaped test: build a small cache + completion set +
  tmp ladder meta and assert the composed XPResult.
- data.json shape: dashboard test asserting the xp block appears.
- lw: status-line test (with and without xp block in data.json), lw xp
  output test at logic level.
