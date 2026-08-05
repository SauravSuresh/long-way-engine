# Briefs, Filing Fixes & Deadline Stamping — Implementation Plan (Part A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the reflection stub misfiling bug, write all 48 rung challenge briefs, link them from shrunken Todoist task descriptions, and stamp Todoist deadlines on rung tasks.

**Architecture:** Content-first: briefs are standalone markdown in `curricula/marketplace-builder/briefs/`, linked by GitHub blob URL from `modules.yaml` descriptions. The only engine change is a create-only `deadline_days → deadline_date` pass-through (Todoist client stays write-only). Spec: `docs/superpowers/specs/2026-08-05-briefs-filing-lw-cli-design.md`.

**Tech Stack:** Python 3 / pytest / PyYAML (all already in repo). Markdown content. Todoist unified API v1 (`API_ROOT = "https://api.todoist.com/api/v1"`, `src/todoist.py:42`).

## Global Constraints

- Repo root: `/Users/sauravsuresh/workspace/personal/long-way-engine`. Run tests as `python -m pytest` from repo root (venv at `.venv/`).
- Todoist client is write-only BY DESIGN (`src/todoist.py:1-25`, guarded by `tests/test_todoist.py::test_completion_client_no_shared_methods`). Never add update/PATCH calls.
- Every commit message ends with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Push after the final task: `gh auth switch -u SauravSuresh && git push origin main` (cron runs from GitHub; unpushed commits are invisible to it).
- Brief URLs use base: `https://github.com/SauravSuresh/long-way-engine/blob/main/curricula/marketplace-builder/briefs/`
- Briefs are definitive on WHAT, silent on HOW. Design decisions (architecture, data structures, algorithms) belong to the learner's ADR. A brief that prescribes design is a defect.

### Brief template (used by Tasks 3–5)

Every brief file follows exactly this structure:

```markdown
# Rung N, Option X — <Title>

**Concept:** <the rung's one concept, from modules.yaml>
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
<2-4 sentences: what pain this software removes, who has it. Real, not invented — grounded in the option text in modules.yaml (owner context: solo dev, previz startup, daily Anki review, own repos/renders).>

## Situation
<A concrete scene, 2-4 sentences, second person: "It's 7am, you're...">

## Scope
<Definitive bullet list of features it MUST have. Each bullet observable behavior, not implementation.>

## Non-goals
<Bullet list of things it explicitly does NOT do. At least 3.>

## How it should NOT work
<Bullet list of anti-behaviors — failure modes that mean the challenge is not met (e.g. "crashes with a stack trace on garbage input", "silently overwrites data"). At least 3, drawn from the rung's "Must" list risks.>

## Acceptance
<Bullet list of runnable/observable checks. Concrete commands with expected output where possible. Include every "Must" item from the modules.yaml rung entry, made concrete for this option.>

## Starting nudge
<ONE paragraph pointing at a sane starting point. No milestones, no step lists, no handholding.>

## ADR question
<Restated verbatim from the rung's entry in modules.yaml.>
```

### Example brief (the register all 48 must match)

This is `rung-01a-expression-calculator.md`, written in full. Batch tasks: match this depth and tone.

```markdown
# Rung 1, Option A — Expression calculator CLI

**Concept:** Small sharp tools; parsing; table-driven tests; clean errors.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Shell arithmetic is miserable: `expr` chokes on `*`, `bc` needs flags to do
floats, and neither gives a usable error when you typo an expression. You
want one small binary that evaluates ordinary infix arithmetic exactly the
way a calculator would, and tells you precisely what's wrong when it can't.

## Situation
You're in a terminal splitting a gear-rental invoice: `calc '(1450*3 + 800) / 4'`.
You fat-finger a parenthesis. Instead of a cryptic `parse error`, the tool
shows you where the expression broke and you fix it without breaking flow.

## Scope
- Evaluates a single expression passed as one CLI argument: `calc '2*(3+4)'` → `14`.
- Operators: `+ - * /`, unary minus, parentheses, decimal numbers.
- Correct precedence and associativity (`2+3*4` → `14`; `2-3-4` → `-5`).
- Division by zero reported as an error, not a panic or `+Inf`.
- Malformed input produces a one-line error naming the position or token
  that broke parsing, and a non-zero exit code.
- `--help` explains usage in ≤10 lines.

## Non-goals
- No variables, functions, or constants (`pi`, `sqrt` — no).
- No REPL/interactive mode; one expression per invocation.
- No arbitrary-precision arithmetic; float64 is fine.
- No expression history, config file, or colors.

## How it should NOT work
- Never a stack trace or panic reaching the user, no matter the input
  (`calc '((('`, `calc ''`, `calc '$(rm -rf /)'` are all one-line errors).
- Never a wrong answer accepted silently — precedence bugs are the failure
  mode this rung exists to catch.
- Never exit 0 when evaluation failed.

## Acceptance
- `calc '2*(3+4)'` prints `14`, exit 0.
- `calc '2+3*4'` prints `14` (precedence, not left-to-right `20`).
- `calc '1/0'` prints a one-line error mentioning division by zero, exit 1.
- `calc '2*('` prints a one-line error pointing at the problem, exit 1.
- Table-driven tests cover: precedence, associativity, parentheses, unary
  minus, decimals, and at least 5 malformed inputs.
- `go test ./...` and `go vet ./...` clean.
- README with install + 3 usage examples.
- ADR names a real consumer (per the rung rules: you, operating it).

## Starting nudge
Write the table of test cases first — valid expressions with expected
values, malformed ones with the error you'd want to see. That table forces
you to decide error wording and edge behavior before any parsing code
exists, and it becomes your table-driven test verbatim.

## ADR question
How do you parse — and where's the seam between the CLI and the reusable core?
```

### Brief filename table (all 48 — slugs are final, Tasks 3–6 depend on them)

| Rung | a | b | c |
|---|---|---|---|
| 01 | rung-01a-expression-calculator | rung-01b-markdown-to-html | rung-01c-flashcard-drill |
| 02 | rung-02a-append-only-kv | rung-02b-cash-ledger | rung-02c-bookmarks-manager |
| 03 | rung-03a-currency-weather-cli | rung-03b-render-status-poller | rung-03c-github-watcher |
| 04 | rung-04a-parallel-file-hasher | rung-04b-concurrent-thumbnailer | rung-04c-concurrent-link-checker |
| 05 | rung-05a-rate-limiter | rung-05b-retry-backoff | rung-05c-ttl-lru-cache |
| 06 | rung-06a-notes-api | rung-06b-pastebin-expiry | rung-06c-previz-asset-catalog |
| 07 | rung-07a-postgres-port | rung-07b-gear-inventory-crud | rung-07c-url-shortener-stats |
| 08 | rung-08a-users-roles | rung-08b-magic-link-login | rung-08c-api-key-service |
| 09 | rung-09a-openapi-retrofit | rung-09b-spec-first-shortener | rung-09c-previz-spec-second-client |
| 10 | rung-10a-webhook-receiver-replay | rung-10b-github-webhook-pipeline | rung-10c-webhook-sender |
| 11 | rung-11a-postgres-job-queue | rung-11b-email-digest-sender | rung-11c-render-job-queue |
| 12 | rung-12a-dockerize-stack | rung-12b-vps-deploy | rung-12c-one-command-dev-env |
| 13 | rung-13a-k6-pprof-hunt | rung-13b-kv-store-10x | rung-13c-startup-tooling-perf |
| 14 | rung-14a-mini-redis-resp | rung-14b-tcp-chat-server | rung-14c-http-from-tcp |
| 15 | rung-15a-leader-election-fencing | rung-15b-replicated-log-lite | rung-15c-consistent-hashing-client |
| 16 | rung-16a-transactional-outbox | rung-16b-chaos-week | rung-16c-otel-end-to-end |

All files: `curricula/marketplace-builder/briefs/<slug>.md`.

---

### Task 1: Stub-path bug — regression test + fix

The engine joins `reflections/<curriculum-key>/` + `stub_path.removeprefix("reflections/")` (`src/reflections.py:96`, root set at `src/main.py:795`). Four stub_paths repeat the key, so stubs land at `reflections/<key>/<key>/...` where the metadata tracker (`src/reflections.py:122-146`, fixed `CADENCE_DIRS` depth) never sees them.

**Files:**
- Modify: `curricula/marketplace-builder/rituals/weekly.yaml:66`
- Modify: `curricula/marketplace-builder/rituals/monthly.yaml:26`
- Modify: `curricula/devops-ready/rituals/weekly.yaml:221`
- Modify: `curricula/devops-ready/rituals/monthly.yaml:103`
- Test: `tests/test_reflections.py` (append)

**Interfaces:**
- Produces: stub_paths of the form `reflections/<cadence>/...` for every curriculum (consumed by Part B's `lw reflect`).

- [ ] **Step 1: Write the failing regression test** — append to `tests/test_reflections.py`:

```python
def test_stub_paths_do_not_repeat_curriculum_key():
    """reflections_root already includes the curriculum key (src/main.py:795);
    a stub_path that repeats it files stubs at reflections/<key>/<key>/..."""
    import yaml as _yaml
    from pathlib import Path as _Path

    curricula_dir = _Path(__file__).resolve().parents[1] / "curricula"
    checked = 0
    for ritual_yaml in curricula_dir.glob("*/rituals/*.yaml"):
        key = ritual_yaml.parent.parent.name
        entries = _yaml.safe_load(ritual_yaml.read_text(encoding="utf-8")) or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            stub = ((entry or {}).get("reflection") or {}).get("stub_path", "")
            if not stub:
                continue
            checked += 1
            assert not stub.startswith(f"reflections/{key}/"), (
                f"{ritual_yaml}: stub_path {stub!r} repeats curriculum key "
                f"{key!r}; engine will file it at reflections/{key}/{key}/..."
            )
    assert checked > 0, "no stub_paths found — glob or repo layout changed"
```

- [ ] **Step 2: Run it, verify it fails**

Run: `python -m pytest tests/test_reflections.py::test_stub_paths_do_not_repeat_curriculum_key -v`
Expected: FAIL naming the four bad files.

- [ ] **Step 3: Fix the four yaml lines** (drop the key segment only; keep everything else byte-identical):

- `curricula/marketplace-builder/rituals/weekly.yaml:66` → `stub_path: "reflections/weekly/{iso_year}-W{iso_week:02d}.md"`
- `curricula/marketplace-builder/rituals/monthly.yaml:26` → `stub_path: "reflections/monthly/{year}-{month:02d}.md"`
- `curricula/devops-ready/rituals/weekly.yaml:221` → `stub_path: "reflections/weekly/{iso_year}-W{iso_week:02d}.md"`
- `curricula/devops-ready/rituals/monthly.yaml:103` → `stub_path: "reflections/monthly/{year}-{month:02d}.md"`

- [ ] **Step 4: Full test suite passes**

Run: `python -m pytest`
Expected: all pass (golden tests don't encode stub paths; if one fails, read its diff before touching anything).

- [ ] **Step 5: Move the already-misfiled files** (separate concern, same commit is fine — it's the same bug's fallout):

```bash
git mv reflections/devops-ready/devops-ready/monthly/2026-06.md reflections/devops-ready/monthly/2026-06.md 2>/dev/null || { mkdir -p reflections/devops-ready/monthly && git mv reflections/devops-ready/devops-ready/monthly/2026-06.md reflections/devops-ready/monthly/2026-06.md; }
git mv reflections/devops-ready/devops-ready/monthly/2026-07.md reflections/devops-ready/monthly/2026-07.md
rmdir reflections/devops-ready/devops-ready/monthly reflections/devops-ready/devops-ready
```

- [ ] **Step 6: Commit**

```bash
git add -A tests/test_reflections.py curricula/ reflections/
git commit -m "fix(reflections): stub_path repeated curriculum key, stubs misfiled

reflections_root already includes the key; four stub_paths repeated it,
filing stubs at reflections/<key>/<key>/ where update_metadata never
looks. Regression test + move the two misfiled devops-ready files.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Briefs batch 1 — rungs 1–5 (15 files)

**Files:**
- Create: `curricula/marketplace-builder/briefs/<slug>.md` for every rung 1–5 slug in the filename table (15 files; `rung-01a-expression-calculator.md` is written verbatim from the example in this plan's Global Constraints).

**Interfaces:**
- Consumes: Brief template + example brief + filename table from this plan file (`docs/superpowers/plans/2026-08-05-briefs-filing-deadline.md`) — READ THAT SECTION FIRST. Source facts: each rung's entry in `curricula/marketplace-builder/modules.yaml` (the option line, the "Must" list, the ADR question).
- Produces: brief files whose names Task 5 links from modules.yaml.

- [ ] **Step 1:** Read the template, example, and filename table in this plan; read `curricula/marketplace-builder/modules.yaml` rungs 1–5.
- [ ] **Step 2:** Write `rung-01a-expression-calculator.md` exactly as given in the example, then the other 14, one file each, following the template. Ground every Problem/Situation in the option's own text (e.g. 01c's consumer is the owner's real daily Anki review; 03b/04a/11c serve the previz startup). Every "Must" bullet from the rung's modules.yaml entry must appear, made concrete, in that option's Acceptance section. Scope stays WHAT-only — no design prescriptions.
- [ ] **Step 3:** Verify completeness:

Run: `ls curricula/marketplace-builder/briefs/rung-0[1-5]* | wc -l`
Expected: `15`
- [ ] **Step 4:** Spot-check one file per rung against the template's section list (all 8 sections present, in order).
- [ ] **Step 5: Commit**

```bash
git add curricula/marketplace-builder/briefs/
git commit -m "docs(briefs): rung 1-5 challenge briefs (15 files)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Briefs batch 2 — rungs 6–11 (18 files)

**Files:**
- Create: `curricula/marketplace-builder/briefs/<slug>.md` for every rung 6–11 slug in the filename table (18 files).

**Interfaces:**
- Consumes: same as Task 2 (template/example/table in this plan file; `modules.yaml` rungs 6–11).
- Produces: brief files whose names Task 5 links from modules.yaml.

- [ ] **Step 1:** Read the template, example, and filename table in this plan; read `curricula/marketplace-builder/modules.yaml` rungs 6–11.
- [ ] **Step 2:** Write the 18 briefs. Phase-2 wrinkles to honor: rung 6's chosen service is the lab for rungs 7–13 — its briefs' Scope must say the service will be extended for months (choose one you'll keep alive), still without prescribing design; rung 7a/9a/10a/11a build on earlier rungs — their Problem sections reference that continuity; rung 9's "Desk reference: API Design Patterns" belongs in the Starting nudge.
- [ ] **Step 3:** Verify: `ls curricula/marketplace-builder/briefs/rung-0[6-9]* curricula/marketplace-builder/briefs/rung-1[01]* | wc -l` → `18`
- [ ] **Step 4:** Spot-check one file per rung (8 sections, in order).
- [ ] **Step 5: Commit**

```bash
git add curricula/marketplace-builder/briefs/
git commit -m "docs(briefs): rung 6-11 challenge briefs (18 files)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Briefs batch 3 — rungs 12–16 (15 files)

**Files:**
- Create: `curricula/marketplace-builder/briefs/<slug>.md` for every rung 12–16 slug in the filename table (15 files).

**Interfaces:**
- Consumes: same as Task 2 (template/example/table in this plan file; `modules.yaml` rungs 12–16).
- Produces: brief files whose names Task 5 links from modules.yaml.

- [ ] **Step 1:** Read the template, example, and filename table in this plan; read `curricula/marketplace-builder/modules.yaml` rungs 12–16.
- [ ] **Step 2:** Write the 15 briefs. Phase-3 wrinkles: rung 13's ADR is a performance report (its briefs' ADR question section says so); rung 15/16 briefs include the pull-reading pointer (DDIA / Release It!) in the Starting nudge; rung 16 briefs note the exit condition (ladder ends, platform absorbs build time) in Non-goals or Situation, whichever reads naturally.
- [ ] **Step 3:** Verify: `ls curricula/marketplace-builder/briefs/ | wc -l` → `48`
- [ ] **Step 4:** Spot-check one file per rung (8 sections, in order).
- [ ] **Step 5: Commit**

```bash
git add curricula/marketplace-builder/briefs/
git commit -m "docs(briefs): rung 12-16 challenge briefs (15 files)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: modules.yaml — shrink descriptions to links, add deadline_days

**Files:**
- Modify: `curricula/marketplace-builder/modules.yaml` (all 16 rung entries)

**Interfaces:**
- Consumes: brief filenames from the table (Tasks 2–4 must be done).
- Produces: `deadline_days` field on every rung entry (consumed by Task 6's engine change); descriptions with GitHub links.

- [ ] **Step 1:** Rewrite every rung entry's `description` to this exact shape (rung 1 shown; repeat the pattern for all 16 using each rung's concept line, option titles, and slugs):

```yaml
- id: rung-1
  title: "Rung 1: CLI craft & tests (~2 wk) — pick one of 3"
  description: |
    Concept: small sharp tools; parsing; table-driven tests; clean errors.
    Pick ONE — read all three briefs first:
    A. [Expression calculator CLI](https://github.com/SauravSuresh/long-way-engine/blob/main/curricula/marketplace-builder/briefs/rung-01a-expression-calculator.md)
    B. [Markdown -> HTML converter](https://github.com/SauravSuresh/long-way-engine/blob/main/curricula/marketplace-builder/briefs/rung-01b-markdown-to-html.md)
    C. [Flashcard drill CLI](https://github.com/SauravSuresh/long-way-engine/blob/main/curricula/marketplace-builder/briefs/rung-01c-flashcard-drill.md)
    Run `lw rung start` to pick and scaffold.
  due: "today at {ritual_times.build_monday}"
  deadline_days: 14
  labels: [rung, phase-1]
  cadence: once-per-module
  module_number: 1
```

  Keep the file's header comment block (rules) intact. `deadline_days` per rung, from the `~N wk` in each title: rungs 1,2,3,4,6,7,8,9,10,11,13 → `14`; rungs 5,12,14,15,16 → `21`.

- [ ] **Step 2:** Validator + suite still green:

Run: `python -m pytest tests/test_curriculum_validator.py tests/test_golden.py && python -m pytest`
Expected: all pass. (Golden fixtures snapshot resolved descriptions for specific dates — if a golden test diff shows ONLY the new description text, regenerate/update those fixtures per the pattern in `tests/test_golden.py`; any other diff is a real regression, stop and investigate.)

- [ ] **Step 3:** Verify every linked slug exists:

```bash
grep -o 'briefs/[a-z0-9-]*\.md' curricula/marketplace-builder/modules.yaml | sed 's|briefs/||' | sort > /tmp/linked.txt
ls curricula/marketplace-builder/briefs/ | sort > /tmp/present.txt
diff /tmp/linked.txt /tmp/present.txt
```
Expected: no output (48 = 48, names identical).

- [ ] **Step 4: Commit**

```bash
git add curricula/marketplace-builder/modules.yaml tests/
git commit -m "feat(marketplace-builder): rung tasks link briefs, add deadline_days

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Engine — deadline_days → Todoist deadline_date (create-only)

**Files:**
- Modify: `src/templates.py` (Template `:42-58`, ResolvedTemplate `:61-74`, `_load_one_file` `:98-163`, `resolve_variables` `:244-283`)
- Modify: `src/todoist.py:166-180` (create body)
- Test: `tests/test_templates.py`, `tests/test_todoist.py` (append)

**Interfaces:**
- Consumes: `deadline_days: int` yaml field (Task 5).
- Produces: `Template.deadline_days: int | None`, `ResolvedTemplate.deadline_date: str` (ISO `YYYY-MM-DD`, empty = no deadline), request body key `deadline_date`. Part B's `lw status` reads `deadline_days` from the same yaml.

- [ ] **Step 1: Failing template test** — append to `tests/test_templates.py`:

```python
def test_deadline_days_resolves_to_iso_date(make_state, make_config):
    from datetime import date
    from src.templates import Template, resolve_variables

    t = Template(
        id="rung-1", title="Rung 1", description="d", due="today at 18:30",
        labels=[], cadence="once-per-module", deadline_days=14,
    )
    resolved = resolve_variables(t, make_state(), make_config(), date(2026, 8, 5))
    assert resolved.deadline_date == "2026-08-19"


def test_no_deadline_days_means_empty_deadline_date(make_state, make_config):
    from datetime import date
    from src.templates import Template, resolve_variables

    t = Template(
        id="x", title="T", description="d", due="", labels=[], cadence="weekly",
    )
    resolved = resolve_variables(t, make_state(), make_config(), date(2026, 8, 5))
    assert resolved.deadline_date == ""
```

  (If `tests/test_templates.py` builds State/Config differently — no `make_state`/`make_config` fixtures — mirror whatever the nearest existing `resolve_variables` test does for construction; the assertions stay the same.)

- [ ] **Step 2: Run, verify failure**

Run: `python -m pytest tests/test_templates.py -k deadline -v`
Expected: FAIL — `Template.__init__() got an unexpected keyword argument 'deadline_days'`.

- [ ] **Step 3: Implement in `src/templates.py`:**
  - `Template`: add field `deadline_days: int | None = None` (after `module_number`).
  - `_load_one_file`: after the `module_number` block add:

```python
        deadline_days = entry.get("deadline_days")
        if deadline_days is not None:
            deadline_days = int(deadline_days)
```
  and pass `deadline_days=deadline_days,` in the `Template(...)` construction.
  - `ResolvedTemplate`: add field `deadline_date: str = ""`.
  - `resolve_variables`: add `from datetime import timedelta` usage and pass:

```python
            deadline_date=(
                (today + timedelta(days=template.deadline_days)).isoformat()
                if template.deadline_days
                else ""
            ),
```
  (`timedelta` import goes at the top of the file with the existing `date` import.)

- [ ] **Step 4: Template tests pass**

Run: `python -m pytest tests/test_templates.py -k deadline -v`
Expected: PASS.

- [ ] **Step 5: Failing todoist test** — append to `tests/test_todoist.py`, mirroring the file's existing create-body test pattern (fake/recorded POST): build a resolved template with `deadline_date="2026-08-19"`, call the client's create path, assert the captured body has `body["deadline_date"] == "2026-08-19"`; and a second case with `deadline_date=""` asserting `"deadline_date" not in body`.

- [ ] **Step 6: Run, verify failure**

Run: `python -m pytest tests/test_todoist.py -k deadline -v`
Expected: FAIL (`deadline_date` missing from body).

- [ ] **Step 7: Implement in `src/todoist.py`** — in the body construction at `:166-180`, after the `due_string` block:

```python
        if getattr(template, "deadline_date", ""):
            body["deadline_date"] = template.deadline_date
```

- [ ] **Step 8: Full suite green** (golden fixtures may need the same only-expected-diff treatment as Task 5)

Run: `python -m pytest`
Expected: all pass.

- [ ] **Step 9: Commit and push everything**

```bash
git add src/templates.py src/todoist.py tests/
git commit -m "feat(engine): stamp Todoist deadline_date from deadline_days (create-only)

Client stays write-only; deadlines set at creation, never updated.
Extensions are tracked repo-side (spec: 2026-08-05 design).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
gh auth switch -u SauravSuresh
git pull --rebase origin main && git push origin main
```

---

## Self-review notes

- Spec coverage (Part A scope): stub-path fix ✓ (Task 1), misfiled-file cleanup ✓ (Task 1 step 5 — spec said separate commit, folded into the fix commit as same-bug fallout), 48 briefs ✓ (Tasks 2–4), description shrink + links ✓ (Task 5), deadline stamping ✓ (Task 6). CLI, review deadline-gate, cron-probe retirement → Part B plan.
- Fixture caveat: `make_state`/`make_config` fixture names are a guess; Step 1 of Task 6 says to mirror the file's real construction pattern — assertions are the contract.
- Golden tests snapshot descriptions; Tasks 5/6 include the only-expected-diff rule instead of blind regeneration.
