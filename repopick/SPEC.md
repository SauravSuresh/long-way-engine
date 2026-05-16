# Tech Spec: `read-real-code` — Weekly Code Reading Picker

## 1. Problem & goal

I do a "read real code" exercise every weekend: pick a real codebase, find the entry point, trace one path, write a one-page note, make 1–2 Anki cards, push to a public notes repo. I've committed to doing this for ~3 years (≈150 sessions).

The friction is **choosing the target**. Browsing for a good repo at the start of the session wastes the best 20 minutes and is a procrastination vector. I want a single bookmarked URL I can open Saturday morning that hands me:

- One repo to read this week.
- A specific entry point or sub-system to trace.
- 1–2 curated reading links (blog post, paper, talk, design doc).

That's the entire product.

## 2. Non-goals

- Not a tracker. I'm not logging completion, streaks, or notes — those live in my notebook + public repo already.
- Not social. No accounts, no sharing, no leaderboard.
- Not a CMS. The pool of repos is hand-curated in code/JSON, not user-editable through a UI.
- Not a recommender that learns. The weighting is deterministic from static metadata.

## 3. Shape of the solution

**Static site on GitHub Pages.** Single page. Open URL → see this week's pick. No backend.

The "randomness" is deterministic from the current ISO week number, so:
- The pick is stable across reloads within the same week.
- Anyone visiting the URL on the same week sees the same pick (cacheable, shareable, reproducible).
- I can preview future weeks by changing the URL hash (e.g. `#week=2026-W42`) — useful for testing and for peeking ahead if I want.

## 4. Data model

One JSON file: `data/repos.json`. Hand-curated. Each entry:

```json
{
  "id": "boltdb",
  "name": "boltdb/bolt",
  "url": "https://github.com/boltdb/bolt",
  "ref": "v1.3.1",
  "language": "Go",
  "themes": ["databases", "storage", "b-tree"],
  "difficulty": 2,
  "loc_estimate": 4000,
  "why": "A single-file embedded KV store. Clean B+tree on mmap. Small enough to hold in your head. Read at tag v1.3.1.",
  "entry_points": [
    {
      "label": "Trace a Put through a transaction",
      "files": ["db.go", "tx.go", "bucket.go"],
      "question": "How does a write become durable? Where does the COW happen?"
    },
    {
      "label": "Understand the freelist",
      "files": ["freelist.go"],
      "question": "How are pages reclaimed without breaking in-flight readers?"
    }
  ],
  "reading": [
    {
      "title": "Ben Johnson — BoltDB internals",
      "url": "https://...",
      "kind": "blog"
    },
    {
      "title": "LMDB paper (Bolt's inspiration)",
      "url": "https://...",
      "kind": "paper"
    }
  ]
}
```

### Field notes

- **`difficulty`**: 1–5. Rough "lines you'd need to read + conceptual load." `git` is 5, `groupcache` is 2.
- **`themes`**: free-form tags but stick to a small vocabulary (databases, networking, compilers, distributed-systems, parsers, scheduling, cli-tools, version-control, search, runtime, graphics, crypto, ml-infra). The picker treats `themes[0]` as primary and the rest as secondary (see §5).
- **`entry_points`**: the picker selects *one* of these per week. This is what makes the pick a goal, not a vibe.
- **`reading`**: 1–3 links. Quality over quantity. Skip if you can't find a genuinely good one — empty array is fine.
- **`ref`** (optional): a git tag, branch, or SHA. Used for entries where you want the reader pinned to a historical version (e.g. `redis @ 1.0.0`, `git @ v0.99`). When present, the UI renders the link as `{url}/tree/{ref}` and the `why` text should explicitly mention the checkout.
- Seed the file with **~30 entries** to start. I'll add more over time; the file is the product.

### Validation

A `data/schema.json` (JSON Schema draft-07) and a check that runs in CI on PRs to `data/repos.json`. Fail the build on:
- Missing required fields.
- Duplicate `id`.
- `difficulty` outside 1–5.
- `ref` present but not a string.
- URLs that don't 200 (optional; off by default to avoid flakiness, on with `--strict`).

## 5. Picker algorithm

Deterministic. Pure function of `(week_key, repos.json)`. No randomness, no `Date.now` in the pick logic — only in resolving "what week is it now."

Theme is a **soft weight**, not a hard filter. This avoids dead ends at the difficulty curve's endpoints (early weeks where target=1 land on themes with no easy repos; late weeks where target=5 land on themes with no hard repos). Every repo is scored every week; theme just colors the weighting.

```
pick(weekKey, repos):
  seed = hash(weekKey)              // FNV-1a or similar, anything stable
  weekTheme = THEMES[seed % len(THEMES)]
  weeksSinceStart = weekKey - START_WEEK
  targetDifficulty = 1 + min(4, weeksSinceStart // 16)   // climb one level per ~4 months, cap at 5
  recent = lastNPicks(recencyWeeks(repos), weekKey, repos)   // set of repo ids

  weights = for each repo in repos:
    if repo.id in recent:
      0
    else:
      themeScore =
        1.0 if weekTheme == repo.themes[0]               // primary match
        else 0.5 if weekTheme in repo.themes             // secondary match
        else 0.2                                          // no match
      diffScore = proximity(repo.difficulty, targetDifficulty)   // gaussian, sigma=1.3
      themeScore * diffScore

  chosen = weightedPick(repos, weights, seed)
  entryPoint = chosen.entry_points[seed2 % len(entry_points)]
  return { repo: chosen, entryPoint, theme: weekTheme, target: targetDifficulty }
```

### Recency without state

Since the site is stateless, "picked in the last N weeks" is computed by **replaying the picker** for the previous N weeks at page load. Cheap (≤8 iterations, all in-memory). This is what makes it truly stateless and reproducible: anyone can verify the pick.

### Recency window is derived, not constant

Hardcoding a single value only works for today's pool size. Derive it from the pool:

```
const RECENCY_WEEKS_MAX = 12;
recencyWeeks(repos) = min(RECENCY_WEEKS_MAX, floor(repos.length * 0.4))
```

At 20 repos → 8. At 30 → 12 (capped). At 40 → 12. Self-tuning, no future intervention needed.

### Week key

`weekKey = ISO year + week, e.g. "2026-W20"`. JS: derive from `Date` with a small helper; or read from `#week=...` hash if present (for previewing).

## 6. UI

One page. Top to bottom:

1. **The pick** — repo name as a big link, the `why` sentence underneath. If `ref` is set, the link points to `{url}/tree/{ref}` (not the default branch), and the `why` text already mentions the checkout.
2. **This week's entry point** — the label, the files (as a code-styled list), the question.
3. **Reading** — 1–3 links, each with a one-word kind tag (`blog`, `paper`, `talk`, `doc`).
4. **Footer** — week number, "← prev week" / "next week →" links (set `#week=` hash), link to repo source, link to my notes repo.

Keep it monospaced and minimal. No framework needed — vanilla HTML + a single `<script type="module">` that fetches `repos.json` and renders into the DOM. Total page weight should be under 30 KB.

## 7. Tech stack

- **Vanilla JS + HTML + CSS.** No build step. No React. No Tailwind. If you want a tiny CSS reset, fine.
- **GitHub Pages** from the `main` branch, `/docs` folder (or root, pick one).
- **GitHub Actions** for the schema check on PRs.
- **No external runtime deps.** A hash function is ~20 lines; an ISO-week helper is ~10. Write them inline.

## 8. Repo layout

```
read-real-code/
├── README.md             # what this is, how to add a repo
├── index.html            # the page
├── app.js                # picker + render (one file is fine)
├── styles.css
├── data/
│   ├── repos.json        # the curated pool
│   └── schema.json
├── scripts/
│   ├── validate.mjs      # runs schema check + duplicate check
│   └── simulate.mjs      # replays picker over 156 weeks, prints distribution
└── .github/workflows/
    └── validate.yml      # runs scripts/validate.mjs on PRs to data/
```

## 9. Adding a new repo

Document this in the README:

1. Fork, add an entry to `data/repos.json`, open a PR.
2. CI validates.
3. Merge → live on next page load.

Make sure adding a repo is **easy enough that I'll actually do it** when I find a good one mid-week. The bottleneck on this project's longevity is curation effort, not code.

## 10. Acceptance criteria

- [ ] Opening the site shows exactly one repo, one entry point, and ≤3 reading links.
- [ ] Reloading the page in the same ISO week returns the same pick.
- [ ] Changing `#week=YYYY-Www` shows the pick for that week.
- [ ] Prev/next links cycle the hash and re-render.
- [ ] No repo picked in the last `recencyWeeks(repos)` weeks is picked this week.
- [ ] Difficulty target climbs roughly one level per 16 weeks, capped at 5.
- [ ] Entries with a `ref` field render their link as `{url}/tree/{ref}`.
- [ ] CI fails a PR that adds a malformed entry or a duplicate `id`.
- [ ] Seeded with ≥25 entries spanning ≥6 themes.

## 11. Resolved values

1. **`START_WEEK = "2026-W20"`** (today's week, anchors the difficulty curve).
2. **Recency** — `RECENCY_WEEKS_MAX = 12`, derived per §5. At seed=30 → 12 (capped).
3. **`THEMES`** (weekly rotation array, themes with ≥3 entries in seed):
   ```js
   const THEMES = [
     "databases", "distributed-systems", "cli-tools", "networking",
     "compilers", "ml-infra", "runtime", "language", "storage",
     "unix-tools", "networking-tools"
   ];
   ```
   Sparse themes (search, scheduling, version-control, crypto, operating-systems) still contribute via secondary tag matching — repos carrying them remain pickable on weeks their primary theme rotates in.
4. **Seed list** — 41 entries, 16 themes. Final list below; `why` / `entry_points` / `reading` filled in during curation (step 5 of build order):

   | # | id | repo | primary theme | other themes | diff | ref |
   |---|---|---|---|---|---|---|
   | 1 | boltdb | boltdb/bolt | databases | storage | 2 | v1.3.1 |
   | 2 | groupcache | golang/groupcache | distributed-systems | — | 2 | — |
   | 3 | redis-early | antirez/redis | databases | — | 3 | 1.0.0 |
   | 4 | sqlite | sqlite (amalgamation) | databases | — | 5 | — |
   | 5 | git-early | git/git | version-control | — | 4 | v0.99 |
   | 6 | ripgrep | BurntSushi/ripgrep | cli-tools | search | 3 | — |
   | 7 | fzf | junegunn/fzf | cli-tools | search | 2 | — |
   | 8 | kube-scheduler | kubernetes/kube-scheduler | scheduling | distributed-systems | 4 | — |
   | 9 | etcd-raft | etcd-io/raft | distributed-systems | — | 4 | — |
   | 10 | fluent-bit | fluent/fluent-bit | networking | — | 3 | — |
   | 11 | nginx | nginx/nginx | networking | — | 4 | — |
   | 12 | lua | lua/lua | runtime | language | 4 | — |
   | 13 | sqlite-utils | simonw/sqlite-utils | cli-tools | databases | 1 | — |
   | 14 | miniredis | alicebob/miniredis | databases | — | 2 | — |
   | 15 | tinygrad | tinygrad/tinygrad | ml-infra | — | 4 | — |
   | 16 | llama-cpp | ggerganov/llama.cpp | ml-infra | — | 4 | — |
   | 17 | whisper-cpp | ggerganov/whisper.cpp | ml-infra | — | 3 | — |
   | 18 | openzfs-arc | openzfs/zfs (ARC) | storage | — | 5 | — |
   | 19 | cpython-dict | python/cpython (Objects/dictobject.c) | runtime | language | 4 | — |
   | 20 | v8-ignition | v8/v8 (Ignition) | compilers | runtime | 5 | — |
   | 21 | llvm-mem2reg | llvm/llvm-project (mem2reg) | compilers | — | 4 | — |
   | 22 | postgres-exec | postgres/postgres (executor) | databases | — | 5 | — |
   | 23 | duckdb-planner | duckdb/duckdb (planner) | databases | compilers | 4 | — |
   | 24 | chibicc | rui314/chibicc | compilers | language | 3 | — |
   | 25 | crafting-interp | munificent/craftinginterpreters (tree-walker) | language | compilers | 2 | — |
   | 26 | litestream | benbjohnson/litestream | databases | storage | 3 | — |
   | 27 | mosh | mobile-shell/mosh | networking | — | 3 | — |
   | 28 | tigerbeetle-vsr | tigerbeetle/tigerbeetle (vsr.zig) | distributed-systems | databases | 4 | — |
   | 29 | tailscale-tsnet | tailscale/tailscale (tsnet) | networking | — | 3 | — |
   | 30 | age | FiloSottile/age | crypto | cli-tools | 2 | — |
   | 31 | busybox-cat | busybox/busybox (coreutils/cat.c) | unix-tools | cli-tools | 1 | — |
   | 32 | busybox-wc | busybox/busybox (coreutils/wc.c) | unix-tools | cli-tools | 1 | — |
   | 33 | gnu-grep-early | gnu/grep | unix-tools | search | 2 | v2.0 |
   | 34 | netcat-hobbit | Hobbit netcat (nc110) | networking-tools | networking, cli-tools | 2 | — |
   | 35 | openbsd-ping | openbsd/src (ping.c) | networking-tools | networking | 3 | — |
   | 36 | curl | curl/curl | networking-tools | networking, cli-tools | 4 | — |
   | 37 | xv6 | mit-pdos/xv6-riscv | runtime | operating-systems | 2 | — |
   | 38 | busybox-init | busybox/busybox (init.c) | unix-tools | operating-systems | 3 | — |
   | 39 | openssh-kex | openssh/openssh-portable (kex.c, kexgen.c) | networking | crypto | 5 | — |
   | 40 | musl-printf | musl/musl (src/stdio/vfprintf.c) | runtime | language | 4 | — |
   | 41 | dnsmasq | simonkelley/dnsmasq | networking | networking-tools | 3 | — |

   Difficulty distribution: 1s=3, 2s=9, 3s=12, 4s=13, 5s=4.

## 12. Things explicitly left out

- Search, filter, "give me a different one" button — the *point* is that the choice is made for me.
- Analytics. Don't add Plausible or anything.
- Dark mode toggle. Use `prefers-color-scheme` and move on.
- Anki card generation. The exercise spec says I make those by hand; that's the thinking step.

## 13. Build order

1. **Skeleton** — repo layout per §8, `data/schema.json`, `scripts/validate.mjs`, GH Actions workflow. No data, no UI logic.
2. **Picker** — `app.js` exporting `pick(weekKey, repos) → {repo, entryPoint, theme, target}` as a pure function. Not wired to DOM yet.
3. **Simulator** — `scripts/simulate.mjs` runs the picker over 156 weeks against a stub `repos.json` (30 entries, only `id`/`themes`/`difficulty` populated). Reports:
   - Pick count per repo
   - Theme distribution per 12-week block
   - Difficulty actual vs target per week
   - Any repo with 0 picks or >10 picks over 156 weeks
4. **Tune** — adjust proximity sigma, themeScore ratios, or the seed list itself against simulator output. Iterate until distribution is healthy.
5. **Curate** — fill `why`, `entry_points`, `reading` for the 30 surviving entries. Expensive; only after step 4 settles.
6. **UI** — per §6. Wire picker to DOM.
7. **Deploy** — GH Pages.

Steps 1–4: one session. Step 5: multi-day. Steps 6–7: second short session.
