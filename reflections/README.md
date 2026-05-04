# Reflections

Version-controlled markdown notebooks. The engine creates stubs at template paths; you fill them in below the frontmatter.

## Layout

- `weekly/` — `2026-W19.md` etc. Engine-created on Friday review.
- `monthly/` — `2026-05.md` etc. Engine-created on the last Saturday of the month.
- `quarterly/` — `2026-Q2.md` etc. Engine-created on the first day of each new quarter.
- `annual/` — `2026.md`. Engine-created on Jan 1.
- `debugging/` — owner-driven. Postmortems, ad-hoc debugging notes. The engine never touches this directory.
- `pairing/` — owner-driven. Notes from pairing sessions with your engineer.
- `private/` — gitignored. Move any reflection here to keep it off the public repo and the dashboard.

## Editing rules

1. **Don't rename files.** The engine matches by path. If you rename `2026-W19.md`, the next Friday run will create `2026-W19.md` again from the template, and you'll have two files for the same week.
2. **Edit below the frontmatter only.** The engine maintains the `word_count` and `status` fields in the frontmatter. Other fields (`type`, `date`, `iso_week`, etc.) are set once at stub creation and never touched again.
3. **Move to `private/` to hide.** Anything in `private/` is gitignored, not rendered in the dashboard, and never read by the engine.

## How `status` works

Each entry starts as `status: stub`. The engine's daily run walks every file in `weekly/`, `monthly/`, `quarterly/`, `annual/` and updates two frontmatter fields:

- `word_count` — set to `len(body.split())` after stripping the frontmatter.
- `status` — auto-flips from `stub` to `filled` when the body grows past **baseline + 50 words** (where baseline = the word count of the unfilled template). The +50 represents one paragraph of real prose.

The flip is **one-way and edge-triggered**. Once `filled`, the engine never reverts to `stub`. To force a revert, manually set `status: stub` in the frontmatter — the engine will respect it as long as you don't add more prose. If you delete prose below the threshold and then write back above it, the engine will auto-flip to `filled` again on the upward crossing.

## Malformed files

If a file under `weekly/`, `monthly/`, `quarterly/`, or `annual/` has malformed frontmatter, the run logs a warning and skips that file — the daily run does not fail.
