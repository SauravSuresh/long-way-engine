# Briefs, filing, and the `lw` CLI — design

Date: 2026-08-05
Status: approved via grilling session (see below for decisions)

## Problem

The marketplace-builder ladder generated its first Todoist tasks and three
things broke on contact with reality:

1. Rung problem statements are too vague to start from ("Expression
   calculator CLI — precedence, parentheses, good errors" is a title, not
   a problem statement).
2. The owner had no idea where reflections, ADRs, and reviews get filed —
   the filing scheme exists but nothing surfaces it. Worse, the engine
   itself files marketplace-builder/devops-ready reflection stubs to the
   wrong path (doubled curriculum key).
3. There is no interactive way to feed the engine: state review is Todoist
   checkboxes probed by cron; reflections are files you must know to
   create; picking a rung option has no mechanism at all.

## Design

### 1. Briefs (48 files)

`curricula/marketplace-builder/briefs/rung-NNx-slug.md` — one file per
option (16 rungs x 3). Written by Claude, reviewed by owner, committed.

Sections, every brief:

- **Problem** — what pain this software removes, who has it.
- **Situation** — a concrete scene where it is used.
- **Scope** — definitive feature list (what it must do).
- **Non-goals** — what it explicitly does not do.
- **How it should NOT work** — anti-behaviors (e.g. "crashes on garbage
  input", "silently swallows errors").
- **Acceptance** — checks proving utility, runnable/observable.
- **Starting nudge** — one paragraph pointing at a sane starting point.
  No milestones, no handholding.
- **ADR question** — restated from modules.yaml.

Briefs are definitive on *what*; silent on *how*. Design decisions belong
to the ADR — that is the pedagogy.

### 2. Todoist task changes

- Rung task descriptions shrink to: concept line + three option titles,
  each a markdown link to its brief's GitHub blob URL + "run
  `lw rung start` to pick". (Todoist renders markdown in descriptions;
  no engine changes needed for links.)
- Engine stamps Todoist `deadline_date` on rung tasks at creation
  (due + rung length from modules.yaml). Create-only — the Todoist
  client stays write-only. Extensions are tracked in the engine repo,
  never pushed to Todoist: Todoist keeps showing the original deadline
  (visible slippage is intentional); `lw status` shows the real one.

### 3. Filing fixes

- Bug: `reflections_root` is already `reflections/<key>/`, but
  marketplace-builder and devops-ready stub_paths include the key again,
  producing `reflections/<key>/<key>/...` (already happened on disk for
  devops-ready) — and update_metadata never sees files at that depth.
  Fix: drop the key segment from `stub_path` in both curricula's ritual
  yamls. Leave the existing misfiled devops-ready files; move them in a
  separate cleanup commit.
- Reflection templates (`curricula/<key>/reflection_templates/`) remain
  the single source for stub bodies and for `lw reflect` forms.

### 4. `lw` CLI

Python + Textual, lives in the engine repo (`[project.scripts]` entry
point `lw`). Config-driven: reads the same curriculum yamls cron reads —
no hardcoded curriculum knowledge. Curricula without a rung system simply
don't get `lw rung`; reviews are generated per-curriculum from their own
yaml.

Commands (v1, exactly these):

- **`lw status`** — cross-curriculum dashboard: current module/rung,
  chosen option, streaks, real deadlines (incl. extensions), what's due
  today.
- **`lw reflect`** — pick curriculum + cadence (or infer from date);
  TUI form, one question per screen, questions taken from the
  curriculum's reflection template; then an $EDITOR pass over the
  assembled markdown (template pre-loaded); writes to the correct
  stub path; auto-commit + push.
- **`lw review`** — the Sunday state review. Questionnaire generated
  from the curriculum's `state_review.sub_tasks`; applies the actions
  (advance_module, increment_counter, mark_book_finished, ...) directly
  to state.yaml; auto-commit + push. Cron stops probing state-review
  completions for CLI-enabled curricula; the Sunday Todoist task becomes
  a reminder: "run `lw review`".
  - **Deadline gate**: when the current rung's deadline falls on or
    before this review, the questionnaire forces exactly one of:
    **shipped** (advance) / **extend** (reason required, logged to the
    rung's meta — extension count is honesty data) / **failed** (logged,
    advance anyway). Extension exists ONLY here; there is no standalone
    extend command.
- **`lw rung start`** — shows the current rung's 3 briefs, owner picks
  one; scaffolds the paper-trail dir in the engine repo and the local
  code dir; drops `adr.md` from a template with the pick + why at top.

Every `lw` write auto-commits and auto-pushes (cron runs from GitHub;
unpushed = invisible). No staging ceremony. Commit hash printed.

### 5. Artifact split: paper trail vs code

- Engine repo: `ladder/rung-NNx-slug/` holds `adr.md`, `REVIEW.md`
  (from /ladder-review), and `meta.yaml` (picked option, code path,
  deadline, extensions with reasons).
- Code: local machine, default `~/workspace/personal/ladder/rung-NNx-slug`,
  overridable at `lw rung start`; not required to be pushed anywhere.
  `/ladder-review` reads `meta.yaml` to find the code.

### 6. Out of scope (deliberate)

- No Todoist update client; write-only rule and its guard test stand.
- No Go rewrite of the CLI now. A Go rewrite is a standing candidate for
  a future rung option (real consumer, used 4x/week), not a blocker.
- Rung 5's published-library module path (subdirectory module vs its own
  repo) is deferred until rung 5.
- No changes to devops-ready/long-way beyond the stub-path fix; they get
  `lw status/reflect/review` for free via config.

## Order of work

1. Stub-path bug fix (both curricula yamls).
2. Briefs (48 files) + modules.yaml description rewrite with links.
3. Engine: `deadline_date` stamping on rung tasks.
4. `lw` CLI: status → reflect → review (incl. deadline gate) → rung start.
5. Retire cron state-review probing for CLI-enabled curricula.

## Decisions log (from grilling)

- Brief verbosity: scoped brief (what/what-not/acceptance), never how.
- One file per option, not per rung.
- Briefs live in the engine repo; tasks link them.
- Starting help = a nudge, not milestones.
- Deadline miss = extend, but only via the review's deadline gate.
- CLI is holistic (whole engine), not rung-only; TUI required.
- Python + Textual for speed and robustness; not a ladder artifact.
- State review write path = CLI only (option C); Todoist task is a
  reminder.
- Reflection capture = form, then editor pass over a pre-loaded template.
- Auto-commit + auto-push on every CLI write.
- Challenge code stays local; specs/ADRs/reviews stay in the engine repo.
