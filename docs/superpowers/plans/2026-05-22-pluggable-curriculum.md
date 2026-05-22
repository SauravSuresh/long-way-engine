# Pluggable curriculum — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all forker-editable curriculum data into `curriculum/`, derive shape (phase/month/module counts) from YAML, ship `AGENTS.md` + two example curricula. Owner's `state.yaml` and Todoist cache stay byte-identical.

**Architecture:** New `curriculum/` directory owns all data. `src/syllabus.py` becomes a thin YAML loader with a `Syllabus` dataclass. New `src/curriculum_validator.py` runs fail-fast checks at startup. Dashboard derives all counts from the loaded syllabus. Cadence engine stays code-defined — forkers author templates only.

**Tech Stack:** Python 3.11+, PyYAML, pytest. Existing engine; no new deps.

**Spec:** `docs/superpowers/specs/2026-05-22-pluggable-curriculum-design.md`

---

## Phase A — Safety net (golden output baseline)

The contract for "no progress affected" is byte-identical task generation. Capture the baseline against the CURRENT code first, before touching anything.

### Task 1: Build the golden-capture helper

**Files:**
- Create: `tests/golden/__init__.py`
- Create: `tests/golden/capture.py`

- [ ] **Step 1: Create the golden directory**

```bash
mkdir -p /Users/sauravsuresh/long-way-engine/tests/golden
touch /Users/sauravsuresh/long-way-engine/tests/golden/__init__.py
```

- [ ] **Step 2: Write the capture helper**

Create `tests/golden/capture.py`:

```python
"""Golden-output capture: serialize run() decisions + dashboard data
for a given date into a stable, diffable JSON form.

Used twice: once before the refactor (pinned in tests/golden/<date>.json),
once after (test asserts the new output matches byte-for-byte).
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any

from src.cache import load_cache
from src.clock import Clock
from src.config import load_config
from src.scheduler import should_create_today
from src.state import load_state
from src.templates import load_templates, resolve_variables

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _serialize(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_serialize(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def capture(
    today: date,
    config_path: Path = REPO_ROOT / "config.yaml",
    state_path: Path = REPO_ROOT / "state.yaml",
    env_path: Path = REPO_ROOT / ".env",
    templates_dir: Path | None = None,
) -> dict[str, Any]:
    """Return a stable snapshot of every decision the engine makes for `today`.

    Captures: which templates fire, which skip (and why), resolved
    variables in titles, due strings, descriptions. Excludes: Todoist
    API state (network), cache writes (filesystem), wall-clock now().
    """
    config = load_config(config_path, env_path)
    state = load_state(state_path)
    if templates_dir is None:
        templates_dir = REPO_ROOT / "task_templates"
    templates = load_templates(templates_dir)

    out: dict[str, Any] = {"date": today.isoformat(), "templates": []}

    for tpl in templates:
        entry: dict[str, Any] = {"id": tpl.id, "cadence": tpl.cadence}
        try:
            fires = should_create_today(tpl, today, state, config)
        except NotImplementedError as e:
            entry["fires"] = False
            entry["error"] = str(e)
            out["templates"].append(entry)
            continue
        entry["fires"] = fires
        if fires:
            resolved = resolve_variables(tpl, state, config, today)
            if resolved is None:
                entry["error"] = "variable resolution failed"
            else:
                entry["title"] = resolved.title
                entry["description"] = resolved.description
                entry["due"] = resolved.due
                entry["labels"] = list(resolved.labels)
        out["templates"].append(entry)

    return out


def write_golden(today: date, out_dir: Path) -> Path:
    snapshot = capture(today)
    path = out_dir / f"{today.isoformat()}.json"
    path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    import sys
    iso = sys.argv[1]
    y, m, d = (int(x) for x in iso.split("-"))
    out = capture(date(y, m, d))
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
```

- [ ] **Step 3: Smoke-test the helper**

Run:

```bash
cd /Users/sauravsuresh/long-way-engine
python -m tests.golden.capture 2026-05-22 | head -30
```

Expected: JSON output starting with `"date": "2026-05-22"` and `"templates": [...]`. No errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add tests/golden/__init__.py tests/golden/capture.py
git commit -m "test: add golden-output capture helper for refactor safety net"
```

---

### Task 2: Capture baseline goldens against current code

**Files:**
- Create: `tests/golden/2026-05-19.json` (Tuesday — regular weekday)
- Create: `tests/golden/2026-05-22.json` (Friday — weekly review fires)
- Create: `tests/golden/2026-05-23.json` (Saturday — deep block fires)
- Create: `tests/golden/2026-05-30.json` (last Saturday of May — monthly retrieval + review, deep block skipped)
- Create: `tests/golden/2026-05-21.json` (Thursday — pair_day, evening hands-on skipped)
- Create: `tests/golden/2026-05-24.json` (Sunday — global block)
- Create: `tests/golden/2026-07-01.json` (Q3 boundary — quarterly fires)
- Create: `tests/golden/2027-01-01.json` (year boundary — quarterly + annual + monthly)
- Create: `tests/golden/2026-06-01.json` (1st of month — monthly blog post)

- [ ] **Step 1: Capture each date**

Run from repo root:

```bash
cd /Users/sauravsuresh/long-way-engine
for d in 2026-05-19 2026-05-22 2026-05-23 2026-05-30 2026-05-21 2026-05-24 2026-07-01 2027-01-01 2026-06-01; do
  python -c "
from datetime import date
from tests.golden.capture import write_golden
from pathlib import Path
y, m, dd = '$d'.split('-')
write_golden(date(int(y), int(m), int(dd)), Path('tests/golden'))
print('captured', '$d')
"
done
```

Expected output: nine `captured YYYY-MM-DD` lines, nine files in `tests/golden/`.

- [ ] **Step 2: Eyeball one capture**

Run:

```bash
cd /Users/sauravsuresh/long-way-engine
head -40 tests/golden/2026-05-22.json
```

Expected: a Friday — `weekly-friday-review` has `"fires": true`, `daily-evening-hands-on` has `"fires": true` (not pair day), etc. Sanity-check a few entries.

- [ ] **Step 3: Commit the baseline**

```bash
cd /Users/sauravsuresh/long-way-engine
git add tests/golden/*.json
git commit -m "test: pin golden baseline outputs for 9 representative dates"
```

**This commit is the safety net. Every subsequent refactor task must keep these files producing identical output.**

---

### Task 3: Wire golden assertion into the test suite

**Files:**
- Create: `tests/test_golden.py`

- [ ] **Step 1: Write the golden assertion test**

Create `tests/test_golden.py`:

```python
"""Golden-output regression test.

For each pinned date in tests/golden/, re-run capture() against the
CURRENT codebase and assert byte-identical output. Any divergence
means the refactor changed task generation for some date.

These tests bypass the autouse path-isolation fixture in conftest.py
because they intentionally read the real config.yaml + state.yaml +
task_templates/ — they're testing the live engine output, not a
sandboxed run().
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from tests.golden.capture import capture

GOLDEN_DIR = Path(__file__).parent / "golden"

# Discover every pinned date by listing the golden directory.
GOLDEN_DATES = sorted(
    p.stem for p in GOLDEN_DIR.glob("*.json") if p.stem != "__init__"
)


@pytest.mark.parametrize("iso_date", GOLDEN_DATES)
def test_golden_matches(iso_date: str) -> None:
    """The capture for `iso_date` must match the pinned JSON byte-for-byte."""
    y, m, d = (int(x) for x in iso_date.split("-"))
    actual = capture(date(y, m, d))
    expected = json.loads((GOLDEN_DIR / f"{iso_date}.json").read_text())
    assert actual == expected, (
        f"Golden mismatch for {iso_date}. "
        f"Re-run tests/golden/capture.py to inspect diff."
    )
```

- [ ] **Step 2: Run the test**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest tests/test_golden.py -v
```

Expected: 9 PASSED. (Capture against current code matches pinned files, since both came from current code.)

- [ ] **Step 3: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add tests/test_golden.py
git commit -m "test: assert pinned goldens match live capture (refactor safety net)"
```

---

## Phase B — Move files (no code logic change)

### Task 4: Move task_templates → curriculum/

**Files:**
- Move: `task_templates/{daily,weekly,monthly,quarterly,annual,practices}.yaml` → `curriculum/rituals/*.yaml`
- Move: `task_templates/modules.yaml` → `curriculum/modules.yaml`

- [ ] **Step 1: Create the curriculum directory**

```bash
cd /Users/sauravsuresh/long-way-engine
mkdir -p curriculum/rituals
```

- [ ] **Step 2: git-move the ritual templates**

```bash
cd /Users/sauravsuresh/long-way-engine
git mv task_templates/daily.yaml curriculum/rituals/daily.yaml
git mv task_templates/weekly.yaml curriculum/rituals/weekly.yaml
git mv task_templates/monthly.yaml curriculum/rituals/monthly.yaml
git mv task_templates/quarterly.yaml curriculum/rituals/quarterly.yaml
git mv task_templates/annual.yaml curriculum/rituals/annual.yaml
git mv task_templates/practices.yaml curriculum/rituals/practices.yaml
git mv task_templates/modules.yaml curriculum/modules.yaml
```

- [ ] **Step 3: Remove the now-empty task_templates dir**

```bash
cd /Users/sauravsuresh/long-way-engine
rmdir task_templates
```

- [ ] **Step 4: Update `src/main.py` path constants and load_templates call**

Open `src/main.py`. Find line 51:

```python
TEMPLATES_DIR = REPO_ROOT / "task_templates"
```

Replace with:

```python
CURRICULUM_DIR = REPO_ROOT / "curriculum"
RITUALS_DIR = CURRICULUM_DIR / "rituals"
MODULES_PATH = CURRICULUM_DIR / "modules.yaml"
```

Find the `load_templates(templates_dir)` call near line 302. The current signature `load_templates(directory: Path)` globs `*.yaml` in one directory. We now need to load from BOTH `rituals/` (glob) AND the single `modules.yaml`. Update `src/templates.py`:

Open `src/templates.py`, find:

```python
def load_templates(directory: Path) -> list[Template]:
    """Load every *.yaml in the directory, in lexical order."""
```

Replace this function with:

```python
def load_templates(paths: list[Path]) -> list[Template]:
    """Load every *.yaml in the given list of paths.

    `paths` is a flat list of yaml files OR directories. Directories
    are globbed for *.yaml (non-recursive). Output preserves caller
    order; within a directory, files are loaded in lexical order.
    """
    out: list[Template] = []
    for p in paths:
        if p.is_dir():
            for yaml_path in sorted(p.glob("*.yaml")):
                out.extend(_load_one_file(yaml_path))
        else:
            out.extend(_load_one_file(p))
    return out


def _load_one_file(path: Path) -> list[Template]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [_parse_template(d) for d in raw]
```

Then find the existing body that does the per-file YAML parsing and extract it into `_load_one_file` if it isn't already a helper. (Read the current function body; whatever it does per-file goes into `_load_one_file`.) The contract: `_load_one_file(path)` returns a `list[Template]` from one YAML file.

In `src/main.py`, find the `load_templates(templates_dir)` call (line 302) and replace with:

```python
templates = load_templates([RITUALS_DIR, MODULES_PATH])
```

Find every other reference to `TEMPLATES_DIR` in `src/main.py` (search for `TEMPLATES_DIR`). Around line 796 in the `__main__` block:

```python
summary = run(
    config,
    state,
    today,
    TEMPLATES_DIR,
    ...
```

Update the `run()` signature so it takes a list of paths instead of a single dir. Find `def run(` around line 260:

```python
def run(
    config: Config,
    state: State,
    today: date,
    templates_dir: Path,
    ...
```

Change `templates_dir: Path` to `template_paths: list[Path]`. Update the call to `load_templates` inside `run()` accordingly:

```python
templates = load_templates(template_paths)
```

And update the `__main__` call site:

```python
summary = run(
    config,
    state,
    today,
    [RITUALS_DIR, MODULES_PATH],
    ...
```

- [ ] **Step 5: Update `tests/golden/capture.py`**

Open `tests/golden/capture.py`. Find:

```python
if templates_dir is None:
    templates_dir = REPO_ROOT / "task_templates"
templates = load_templates(templates_dir)
```

Replace with:

```python
if templates_dir is None:
    template_paths = [
        REPO_ROOT / "curriculum" / "rituals",
        REPO_ROOT / "curriculum" / "modules.yaml",
    ]
else:
    template_paths = [templates_dir]
templates = load_templates(template_paths)
```

Also update the function signature parameter name from `templates_dir` to `template_paths_override` if you want, or leave the name alone — it's a private detail.

- [ ] **Step 6: Update other test call sites of `load_templates`**

Search for callers:

```bash
cd /Users/sauravsuresh/long-way-engine
grep -rn "load_templates(" tests src
```

For every caller in `tests/`, wrap the directory argument into a list: `load_templates([the_dir])`. Any test that passes a single yaml file as if it were a directory now needs `load_templates([that_file])` — which works because the new signature accepts files in the list too.

- [ ] **Step 7: Run the golden tests**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest tests/test_golden.py -v
```

Expected: 9 PASSED. (File location changed, content didn't — output must be identical.)

- [ ] **Step 8: Run the full test suite**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest -q
```

Expected: all green. If any test fails because it hardcoded `task_templates/`, update it to `curriculum/rituals/` or `curriculum/modules.yaml`.

- [ ] **Step 9: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add -A
git commit -m "refactor: move task_templates/ into curriculum/{rituals,modules.yaml}"
```

---

### Task 5: Move reflection_templates → curriculum/reflection_templates

**Files:**
- Move: `reflection_templates/{weekly,monthly,quarterly,annual}.md` → `curriculum/reflection_templates/`

- [ ] **Step 1: git-move the directory**

```bash
cd /Users/sauravsuresh/long-way-engine
git mv reflection_templates curriculum/reflection_templates
```

- [ ] **Step 2: Update `src/main.py`**

Open `src/main.py`. Find line 55:

```python
REFLECTION_TEMPLATES_DIR = REPO_ROOT / "reflection_templates"
```

Replace with:

```python
REFLECTION_TEMPLATES_DIR = CURRICULUM_DIR / "reflection_templates"
```

- [ ] **Step 3: Update `tests/conftest.py`**

Open `tests/conftest.py`. The autouse fixture creates a tmp `reflection_templates/` dir at line 52. No path change needed — it's a tmp_path, just a fixture mock. Verify no hardcoded reference to the real path.

- [ ] **Step 4: Run all tests + goldens**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest -q
```

Expected: all green. Goldens still match (reflection templates don't affect task generation — they affect reflection stub paths, which are captured separately when a template fires with reflection.create_stub).

- [ ] **Step 5: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add -A
git commit -m "refactor: move reflection_templates/ into curriculum/"
```

---

## Phase C — Schema files (YAML)

### Task 6: Write the migration script

**Files:**
- Create: `scripts/migrate_syllabus.py` (deleted at end of plan)

- [ ] **Step 1: Create scripts dir if missing**

```bash
cd /Users/sauravsuresh/long-way-engine
mkdir -p scripts
```

- [ ] **Step 2: Write the migration script**

Create `scripts/migrate_syllabus.py`:

```python
"""One-time migration: generate curriculum/syllabus.yaml from existing sources.

Reads:
  - src/syllabus.py PRIMARY_BOOK_BY_MONTH (the dict)
  - the-long-way.md (regex parsed for full book list)
  - curriculum/modules.yaml (module numbers + onboarding task titles)

Writes:
  - curriculum/syllabus.yaml

Deleted at the end of the plan. Not part of the shipped engine.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.syllabus import PRIMARY_BOOK_BY_MONTH, parse_books_from_file

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "curriculum" / "syllabus.yaml"
MODULES_PATH = REPO_ROOT / "curriculum" / "modules.yaml"


PHASES = [
    {"number": 1, "name": "Foundations",
     "months": [1, 12]},
    {"number": 2, "name": "Go & the Backend Toolkit",
     "months": [13, 20]},
    {"number": 3, "name": "Distributed Systems & Booking",
     "months": [21, 30]},
    {"number": 4, "name": "Kubernetes, Observability, Synthesis",
     "months": [31, 39]},
]


def _extract_module_name(title: str) -> str:
    """Turn 'Module 4: C & Memory Management — start' into 'C & Memory Management'."""
    m = re.match(r"^Module \d+:\s*(.+?)(?:\s+—\s+start)?$", title.strip())
    return m.group(1).strip() if m else title.strip()


def build_modules() -> list[dict]:
    raw = yaml.safe_load(MODULES_PATH.read_text(encoding="utf-8")) or []
    by_number: dict[int, dict] = {}
    for entry in raw:
        if entry.get("cadence") != "once-per-module":
            continue
        mod_num = entry.get("module_number")
        if mod_num is None:
            continue
        # Only the onboarding task per module (id ends with -onboarding).
        if not entry["id"].endswith("-onboarding"):
            continue
        name = _extract_module_name(entry["title"])
        # Phase derived from PHASES table by month — modules don't carry
        # their own month, but we can infer phase from existing PHASES
        # by looking at the module number's typical phase boundaries.
        # Hand-map (mirrors the current modules.yaml comments):
        if mod_num <= 11:
            phase = 1
        elif mod_num <= 16:
            phase = 2
        elif mod_num <= 20:
            phase = 3
        else:
            phase = 4
        by_number[mod_num] = {
            "number": mod_num,
            "name": name,
            "phase": phase,
        }
    return [by_number[k] for k in sorted(by_number)]


def build_books() -> list[dict]:
    """Pull books from the regex parser over the-long-way.md."""
    parsed = parse_books_from_file()
    out: list[dict] = []
    for b in parsed:
        entry: dict = {
            "title": b.title,
            "author": b.author,
            "phase": b.phase,
        }
        if b.start_month is not None:
            entry["months"] = [b.start_month, b.end_month]
        entry["role"] = "primary"  # default; reviewer adjusts secondary/reference by hand
        out.append(entry)
    return out


def main() -> None:
    syllabus = {
        "meta": {
            "name": "The Long Way",
            "total_months": 39,
            "start_month_index": 1,
        },
        "phases": PHASES,
        "books": build_books(),
        "primary_book_by_month": dict(sorted(PRIMARY_BOOK_BY_MONTH.items())),
        "modules": build_modules(),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        yaml.safe_dump(syllabus, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Commit the migration script**

```bash
cd /Users/sauravsuresh/long-way-engine
git add scripts/migrate_syllabus.py
git commit -m "chore: add one-time syllabus migration script"
```

---

### Task 7: Generate syllabus.yaml and hand-correct book roles

**Files:**
- Create: `curriculum/syllabus.yaml`

- [ ] **Step 1: Run the migration script**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m scripts.migrate_syllabus
```

Expected: `wrote /Users/sauravsuresh/long-way-engine/curriculum/syllabus.yaml`.

- [ ] **Step 2: Open the generated file and hand-correct book roles**

Open `curriculum/syllabus.yaml`. The script defaults every book to `role: primary`. Walk through `the-long-way.md`'s "Phase X reading" sections and update each book's role to one of:

- `primary` — the main long read for its month span (e.g., CSAPP for Phase 1 months 1–6, Networking for 7–10, Go Programming Language for Phase 2)
- `secondary` — a shorter complementary read with a specific month span (e.g., Debugging in month 2, Building Microservices overlap)
- `reference` — listed without a month span; consulted ad hoc

Specifically: every book whose `title` appears in `primary_book_by_month` should be `role: primary` for the month spans it covers. Books like Debugging, APoSD, CLRS that are weekend reads or reference get the appropriate non-primary role.

- [ ] **Step 3: Verify primary_book_by_month invariant by eye**

For each entry in `primary_book_by_month`, confirm there's a book in `books:` with that title. (The validator will enforce this in Task 11; do a quick eyeball now to catch typos.)

- [ ] **Step 4: Run the existing test suite — must still pass**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest -q
```

Expected: all green. (`syllabus.yaml` exists but nothing reads it yet — engine still uses the Python dict.)

- [ ] **Step 5: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add curriculum/syllabus.yaml
git commit -m "feat: add curriculum/syllabus.yaml (generated + hand-tuned book roles)"
```

---

### Task 8: Write curriculum/manifest.yaml

**Files:**
- Create: `curriculum/manifest.yaml`

- [ ] **Step 1: Write the manifest**

Create `curriculum/manifest.yaml`:

```yaml
# Declares which ritual_time slots and template placeholders this
# curriculum requires from the engine. Engine validates at startup
# that config.yaml provides every ritual_times_required key.

ritual_times_required:
  - morning_reading
  - anki
  - evening_hands_on
  - friday_review
  - saturday_deep_block
  - sunday_trace

placeholders_used:
  - current_book
  - current_module
  - iso_year
  - iso_week
  - year
  - month
  - quarter

config_flags:
  pair_day: thursday
  sunday_off: true
```

- [ ] **Step 2: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add curriculum/manifest.yaml
git commit -m "feat: add curriculum/manifest.yaml declaring ritual_times + placeholders"
```

---

## Phase D — New code: Syllabus loader + validator + config plumbing

### Task 9: Add `curriculum_dir` to Config

**Files:**
- Modify: `src/config.py`
- Modify: `config.yaml`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Open `tests/test_config.py`. Add at the end:

```python
def test_config_curriculum_dir_default(tmp_path: Path) -> None:
    """Config defaults curriculum_dir to 'curriculum' when omitted."""
    cfg_yaml = tmp_path / "config.yaml"
    cfg_yaml.write_text(
        "todoist:\n"
        "  project_id: x\n"
        "ritual_times: {}\n"
        "dashboard:\n"
        "  github_username: u\n"
        "  repo_name: r\n",
        encoding="utf-8",
    )
    env = tmp_path / ".env"
    env.write_text("TODOIST_TOKEN=abc\n", encoding="utf-8")
    cfg = load_config(cfg_yaml, env)
    assert cfg.curriculum_dir == Path("curriculum")


def test_config_curriculum_dir_explicit(tmp_path: Path) -> None:
    cfg_yaml = tmp_path / "config.yaml"
    cfg_yaml.write_text(
        "todoist:\n"
        "  project_id: x\n"
        "ritual_times: {}\n"
        "dashboard:\n"
        "  github_username: u\n"
        "  repo_name: r\n"
        "curriculum_dir: examples/ml-engineer-12mo\n",
        encoding="utf-8",
    )
    env = tmp_path / ".env"
    env.write_text("TODOIST_TOKEN=abc\n", encoding="utf-8")
    cfg = load_config(cfg_yaml, env)
    assert cfg.curriculum_dir == Path("examples/ml-engineer-12mo")
```

Make sure `from pathlib import Path` is imported at the top of the test file (it should already be).

- [ ] **Step 2: Run the test, verify failure**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest tests/test_config.py::test_config_curriculum_dir_default -v
```

Expected: FAIL — `Config` has no attribute `curriculum_dir`.

- [ ] **Step 3: Add field to Config and load it**

Open `src/config.py`. Find the `Config` dataclass:

```python
@dataclass
class Config:
    todoist: TodoistConfig
    ritual_times: dict[str, str]
    sunday_off: bool
    dashboard: DashboardConfig
    todoist_token: str
    pair_day: str | None = None
```

Add a field at the end:

```python
    curriculum_dir: Path = field(default_factory=lambda: Path("curriculum"))
```

Update the `__repr__` to include it:

```python
    def __repr__(self) -> str:
        return (
            f"Config(todoist={self.todoist!r}, "
            f"ritual_times={self.ritual_times!r}, "
            f"sunday_off={self.sunday_off!r}, "
            f"pair_day={self.pair_day!r}, "
            f"dashboard={self.dashboard!r}, "
            f"curriculum_dir={self.curriculum_dir!r}, "
            f"todoist_token='***REDACTED***')"
        )
```

In `load_config()`, after the `pair_day = ...` block, add:

```python
    curriculum_dir = raw.get("curriculum_dir", "curriculum")
    curriculum_dir = Path(curriculum_dir)
```

And include it in the `Config(...)` call:

```python
    return Config(
        todoist=todoist,
        ritual_times=dict(raw.get("ritual_times", {})),
        sunday_off=bool(raw.get("sunday_off", True)),
        dashboard=dashboard,
        todoist_token=_read_token(env_path),
        pair_day=pair_day,
        curriculum_dir=curriculum_dir,
    )
```

- [ ] **Step 4: Verify tests pass**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest tests/test_config.py -v
```

Expected: all PASS.

- [ ] **Step 5: Add the field to the live config.yaml (optional but explicit)**

Open `config.yaml` and add after the `pair_day` line:

```yaml
# Pluggable curriculum bundle directory. Default: "curriculum".
# Forkers point this at their own bundle, or at one of examples/*.
curriculum_dir: curriculum
```

- [ ] **Step 6: Run all tests + goldens**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest -q
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add src/config.py tests/test_config.py config.yaml
git commit -m "feat(config): add curriculum_dir field (defaults to curriculum/)"
```

---

### Task 10: `Syllabus` dataclass + `load_syllabus()`

**Files:**
- Modify: `src/syllabus.py`
- Modify: `tests/test_syllabus.py`

- [ ] **Step 1: Write the failing test**

Open `tests/test_syllabus.py`. At the bottom of the file, add:

```python
def test_load_syllabus_from_curriculum_dir(tmp_path: Path) -> None:
    """load_syllabus reads curriculum/syllabus.yaml into a Syllabus dataclass."""
    cdir = tmp_path / "curriculum"
    cdir.mkdir()
    (cdir / "syllabus.yaml").write_text(
        "meta:\n"
        "  name: Tiny\n"
        "  start_month_index: 1\n"
        "phases:\n"
        "  - number: 1\n"
        "    name: Foundations\n"
        "    months: [1, 3]\n"
        "books:\n"
        "  - title: Book A\n"
        "    author: Author\n"
        "    phase: 1\n"
        "    months: [1, 3]\n"
        "    role: primary\n"
        "primary_book_by_month:\n"
        "  1: Book A\n"
        "  2: Book A\n"
        "  3: Book A\n"
        "modules:\n"
        "  - number: 1\n"
        "    name: Mod One\n"
        "    phase: 1\n",
        encoding="utf-8",
    )
    from src.syllabus import load_syllabus
    syl = load_syllabus(cdir)
    assert syl.meta["name"] == "Tiny"
    assert len(syl.phases) == 1
    assert syl.phases[0].name == "Foundations"
    assert syl.phases[0].months == (1, 3)
    assert len(syl.books) == 1
    assert syl.primary_book_by_month == {1: "Book A", 2: "Book A", 3: "Book A"}
    assert len(syl.modules) == 1
    assert syl.modules[0].name == "Mod One"


def test_current_book_with_syllabus(tmp_path: Path) -> None:
    """current_book(month, syllabus) does table lookup with carry-forward."""
    from src.syllabus import Syllabus, Phase, Book as SylBook, Module, current_book
    syl = Syllabus(
        meta={"name": "T", "start_month_index": 1},
        phases=[Phase(number=1, name="P1", months=(1, 5))],
        books=[SylBook(title="A", author="x", phase=1, months=(1, 3), role="primary")],
        primary_book_by_month={1: "A", 2: "A", 3: "A"},
        modules=[Module(number=1, name="M1", phase=1)],
    )
    assert current_book(1, syl) == "A"
    assert current_book(3, syl) == "A"
    assert current_book(4, syl) == "A"   # carry-forward
    assert current_book(0, syl) == ""     # no prior
```

- [ ] **Step 2: Run, verify failure**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest tests/test_syllabus.py::test_load_syllabus_from_curriculum_dir -v
```

Expected: FAIL (import error for `load_syllabus`).

- [ ] **Step 3: Add the new types and loader**

Open `src/syllabus.py`. Add the following AFTER the existing `Book` dataclass (do NOT delete `Book`, `parse_books`, `PRIMARY_BOOK_BY_MONTH`, `current_book` yet — those go in Task 14):

```python
# --- new loader (Phase D) -----------------------------------------------------

@dataclass(frozen=True)
class Phase:
    number: int
    name: str
    months: tuple[int, int]  # inclusive [start, end]


@dataclass(frozen=True)
class Module:
    number: int
    name: str
    phase: int


@dataclass(frozen=True)
class Syllabus:
    meta: dict
    phases: list[Phase]
    books: list[Book]
    primary_book_by_month: dict[int, str]
    modules: list[Module]


def load_syllabus(curriculum_dir: Path) -> Syllabus:
    """Parse curriculum/syllabus.yaml into a Syllabus dataclass.

    Validation lives in src/curriculum_validator.py — this loader is
    intentionally permissive so the validator can collect every error
    in one pass.
    """
    import yaml
    raw = yaml.safe_load(
        (curriculum_dir / "syllabus.yaml").read_text(encoding="utf-8")
    )
    phases = [
        Phase(number=p["number"], name=p["name"],
              months=(p["months"][0], p["months"][1]))
        for p in raw.get("phases", [])
    ]
    books: list[Book] = []
    for b in raw.get("books", []):
        months = b.get("months")
        start, end = (months[0], months[1]) if months else (None, None)
        books.append(Book(
            phase=b["phase"], title=b["title"], author=b["author"],
            start_month=start, end_month=end,
        ))
    modules = [
        Module(number=m["number"], name=m["name"], phase=m["phase"])
        for m in raw.get("modules", [])
    ]
    primary = {int(k): str(v) for k, v in (raw.get("primary_book_by_month") or {}).items()}
    return Syllabus(
        meta=raw.get("meta", {}),
        phases=phases,
        books=books,
        primary_book_by_month=primary,
        modules=modules,
    )
```

Then ADD an overload of `current_book` that takes a Syllabus. Replace the existing `current_book(month)` function with:

```python
def current_book(month: int, syllabus: "Syllabus | None" = None) -> str:
    """Primary book for `month` with carry-forward to the most recent mapped month.

    When `syllabus` is provided, look up in syllabus.primary_book_by_month.
    When `syllabus` is None (legacy callers), fall back to the module-level
    PRIMARY_BOOK_BY_MONTH dict. Returns "" only when no prior month is mapped.
    """
    table = syllabus.primary_book_by_month if syllabus is not None else PRIMARY_BOOK_BY_MONTH
    if month in table:
        return table[month]
    for m in range(month - 1, 0, -1):
        if m in table:
            return table[m]
    return ""
```

- [ ] **Step 4: Run the new tests**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest tests/test_syllabus.py -v
```

Expected: all green, including pre-existing tests (legacy callers still work, table-based dict is untouched).

- [ ] **Step 5: Run the full suite + goldens**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add src/syllabus.py tests/test_syllabus.py
git commit -m "feat(syllabus): add Syllabus dataclass and load_syllabus() (YAML)"
```

---

### Task 11: `curriculum_validator.py`

**Files:**
- Create: `src/curriculum_validator.py`
- Create: `tests/test_curriculum_validator.py`

- [ ] **Step 1: Write failing tests for every validator rule**

Create `tests/test_curriculum_validator.py`:

```python
"""Validator must aggregate every violation into one CurriculumError.

Each test sets up a deliberately-broken curriculum fixture and asserts
the validator raises with that specific message.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def _write_minimal_curriculum(root: Path, *, syllabus_overrides=None,
                              modules_yaml: str | None = None,
                              manifest_yaml: str | None = None,
                              rituals: dict[str, str] | None = None) -> Path:
    """Build a curriculum dir with sane defaults, then apply overrides."""
    cdir = root / "curriculum"
    (cdir / "rituals").mkdir(parents=True)

    syllabus = {
        "meta": {"name": "T", "start_month_index": 1, "total_months": 3},
        "phases": [{"number": 1, "name": "P1", "months": [1, 3]}],
        "books": [
            {"title": "A", "author": "x", "phase": 1,
             "months": [1, 3], "role": "primary"},
        ],
        "primary_book_by_month": {1: "A", 2: "A", 3: "A"},
        "modules": [{"number": 1, "name": "M1", "phase": 1}],
    }
    if syllabus_overrides:
        syllabus.update(syllabus_overrides)
    (cdir / "syllabus.yaml").write_text(
        yaml.safe_dump(syllabus, sort_keys=False), encoding="utf-8",
    )

    if manifest_yaml is None:
        manifest_yaml = (
            "ritual_times_required: [morning]\n"
            "placeholders_used: [current_book]\n"
            "config_flags: {sunday_off: true}\n"
        )
    (cdir / "manifest.yaml").write_text(manifest_yaml, encoding="utf-8")

    if modules_yaml is None:
        modules_yaml = (
            "- id: module-01-onboarding\n"
            "  module_number: 1\n"
            "  title: M1 start\n"
            "  description: x\n"
            "  due: today\n"
            "  labels: [module-work]\n"
            "  cadence: once-per-module\n"
        )
    (cdir / "modules.yaml").write_text(modules_yaml, encoding="utf-8")

    if rituals is None:
        rituals = {
            "daily.yaml": (
                "- id: daily-x\n"
                "  title: x\n"
                "  description: x\n"
                "  due: today\n"
                "  labels: [daily-ritual]\n"
                "  cadence: daily\n"
            ),
        }
    for fname, contents in rituals.items():
        (cdir / "rituals" / fname).write_text(contents, encoding="utf-8")

    return cdir


def _validate(cdir: Path, ritual_times=None):
    from src.curriculum_validator import validate, CurriculumError
    return validate(cdir, ritual_times=ritual_times or {"morning": "06:00"})


def test_passes_on_minimal_valid_curriculum(tmp_path: Path) -> None:
    cdir = _write_minimal_curriculum(tmp_path)
    _validate(cdir)  # no exception


def test_check1_primary_book_not_in_books(tmp_path: Path) -> None:
    cdir = _write_minimal_curriculum(tmp_path, syllabus_overrides={
        "primary_book_by_month": {1: "GHOST", 2: "A", 3: "A"},
    })
    from src.curriculum_validator import CurriculumError
    with pytest.raises(CurriculumError, match="GHOST"):
        _validate(cdir)


def test_check2_phases_not_contiguous(tmp_path: Path) -> None:
    cdir = _write_minimal_curriculum(tmp_path, syllabus_overrides={
        "phases": [
            {"number": 1, "name": "P1", "months": [1, 3]},
            {"number": 2, "name": "P2", "months": [5, 7]},  # gap at 4
        ],
    })
    from src.curriculum_validator import CurriculumError
    with pytest.raises(CurriculumError, match="contiguous|gap"):
        _validate(cdir)


def test_check3_module_phase_unknown(tmp_path: Path) -> None:
    cdir = _write_minimal_curriculum(tmp_path, syllabus_overrides={
        "modules": [{"number": 1, "name": "M1", "phase": 99}],
    })
    from src.curriculum_validator import CurriculumError
    with pytest.raises(CurriculumError, match="phase 99"):
        _validate(cdir)


def test_check4_module_numbers_not_dense(tmp_path: Path) -> None:
    cdir = _write_minimal_curriculum(tmp_path, syllabus_overrides={
        "modules": [
            {"number": 1, "name": "M1", "phase": 1},
            {"number": 3, "name": "M3", "phase": 1},  # missing 2
        ],
    })
    from src.curriculum_validator import CurriculumError
    with pytest.raises(CurriculumError, match="dense|gap"):
        _validate(cdir)


def test_check5_module_missing_onboarding_task(tmp_path: Path) -> None:
    """A syllabus.module without a matching once-per-module task is invalid."""
    cdir = _write_minimal_curriculum(
        tmp_path,
        syllabus_overrides={
            "modules": [
                {"number": 1, "name": "M1", "phase": 1},
                {"number": 2, "name": "M2", "phase": 1},
            ],
        },
        # modules.yaml only has the task for module 1
    )
    from src.curriculum_validator import CurriculumError
    with pytest.raises(CurriculumError, match="module 2"):
        _validate(cdir)


def test_check6_manifest_missing_ritual_time(tmp_path: Path) -> None:
    cdir = _write_minimal_curriculum(tmp_path, manifest_yaml=(
        "ritual_times_required: [morning, dawn]\n"
    ))
    from src.curriculum_validator import CurriculumError
    with pytest.raises(CurriculumError, match="dawn"):
        _validate(cdir, ritual_times={"morning": "06:00"})


def test_check8_unknown_cadence(tmp_path: Path) -> None:
    cdir = _write_minimal_curriculum(tmp_path, rituals={
        "daily.yaml": (
            "- id: weird\n"
            "  title: x\n  description: x\n  due: today\n"
            "  labels: []\n  cadence: biweekly\n"
        ),
    })
    from src.curriculum_validator import CurriculumError
    with pytest.raises(CurriculumError, match="biweekly"):
        _validate(cdir)


def test_check9_unknown_skip_if(tmp_path: Path) -> None:
    cdir = _write_minimal_curriculum(tmp_path, rituals={
        "daily.yaml": (
            "- id: bad-skip\n"
            "  title: x\n  description: x\n  due: today\n"
            "  labels: []\n  cadence: daily\n"
            "  skip_if: [moonday]\n"
        ),
    })
    from src.curriculum_validator import CurriculumError
    with pytest.raises(CurriculumError, match="moonday"):
        _validate(cdir)


def test_check10_duplicate_template_ids(tmp_path: Path) -> None:
    cdir = _write_minimal_curriculum(tmp_path, rituals={
        "daily.yaml": (
            "- id: dup\n  title: a\n  description: a\n  due: today\n"
            "  labels: []\n  cadence: daily\n"
            "- id: dup\n  title: b\n  description: b\n  due: today\n"
            "  labels: []\n  cadence: daily\n"
        ),
    })
    from src.curriculum_validator import CurriculumError
    with pytest.raises(CurriculumError, match="duplicate"):
        _validate(cdir)


def test_aggregates_multiple_violations(tmp_path: Path) -> None:
    cdir = _write_minimal_curriculum(tmp_path, syllabus_overrides={
        "primary_book_by_month": {1: "GHOST", 2: "A", 3: "A"},
        "modules": [{"number": 1, "name": "M1", "phase": 99}],
    })
    from src.curriculum_validator import CurriculumError
    with pytest.raises(CurriculumError) as exc_info:
        _validate(cdir)
    msg = str(exc_info.value)
    assert "GHOST" in msg
    assert "phase 99" in msg
```

- [ ] **Step 2: Run tests, verify all fail**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest tests/test_curriculum_validator.py -v
```

Expected: collection error or 11 FAIL (validator module doesn't exist yet).

- [ ] **Step 3: Implement the validator**

Create `src/curriculum_validator.py`:

```python
"""Fail-fast validation for a curriculum bundle.

Every check returns a list[str] of violations. validate() aggregates
all of them and raises CurriculumError with the joined message. No
short-circuit on first failure — forkers see every problem at once.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from src.syllabus import load_syllabus

SUPPORTED_CADENCES = {
    "daily", "weekly", "monthly", "quarterly", "annual", "once-per-module",
}
SUPPORTED_SKIP_IFS = {"sunday", "pair_day", "last-saturday-of-month"}


class CurriculumError(Exception):
    """Raised when a curriculum bundle has any validation violation."""


def validate(
    curriculum_dir: Path,
    *,
    ritual_times: dict[str, str] | None = None,
    state_current_module: int | None = None,
    state_month: int | None = None,
) -> None:
    """Validate every aspect of a curriculum bundle.

    ritual_times: config.ritual_times to cross-check the manifest against.
    state_current_module / state_month: from state.yaml; if provided,
    we check they fall within the syllabus' ranges.

    Raises CurriculumError listing every violation. No-op on success.
    """
    syllabus = load_syllabus(curriculum_dir)
    manifest = _load_manifest(curriculum_dir)
    ritual_templates = _load_yaml_files(curriculum_dir / "rituals")
    module_templates = _load_yaml_one(curriculum_dir / "modules.yaml")
    all_templates = ritual_templates + module_templates

    errors: list[str] = []
    errors += _check_primary_books_match(syllabus)
    errors += _check_phases_contiguous(syllabus)
    errors += _check_modules_phase(syllabus)
    errors += _check_modules_dense(syllabus)
    errors += _check_module_onboarding_tasks(syllabus, module_templates)
    errors += _check_manifest_ritual_times(manifest, ritual_times or {})
    errors += _check_state_vs_syllabus(syllabus, state_current_module, state_month)
    errors += _check_cadences(all_templates)
    errors += _check_skip_ifs(all_templates)
    errors += _check_unique_ids(all_templates)

    if errors:
        joined = "\n  - ".join([""] + errors)
        raise CurriculumError(
            f"Curriculum at {curriculum_dir} has {len(errors)} violation(s):"
            + joined
        )


# --- per-check helpers --------------------------------------------------------

def _check_primary_books_match(syllabus) -> list[str]:
    book_titles = {b.title for b in syllabus.books}
    return [
        f"primary_book_by_month[{m}] = {title!r} has no matching books[].title"
        for m, title in syllabus.primary_book_by_month.items()
        if title not in book_titles
    ]


def _check_phases_contiguous(syllabus) -> list[str]:
    if not syllabus.phases:
        return ["no phases defined"]
    phases = sorted(syllabus.phases, key=lambda p: p.number)
    expected_start = syllabus.meta.get("start_month_index", 1)
    errors: list[str] = []
    for i, p in enumerate(phases):
        if p.months[0] != expected_start:
            errors.append(
                f"phase {p.number} months[0]={p.months[0]} but expected "
                f"{expected_start} (gap or overlap)"
            )
        if p.months[1] < p.months[0]:
            errors.append(
                f"phase {p.number} months range [{p.months[0]}, {p.months[1]}] is empty"
            )
        expected_start = p.months[1] + 1
    return errors


def _check_modules_phase(syllabus) -> list[str]:
    phase_numbers = {p.number for p in syllabus.phases}
    return [
        f"module {m.number} ({m.name!r}) references unknown phase {m.phase}"
        for m in syllabus.modules
        if m.phase not in phase_numbers
    ]


def _check_modules_dense(syllabus) -> list[str]:
    numbers = sorted(m.number for m in syllabus.modules)
    errors: list[str] = []
    if numbers and numbers[0] != 1:
        errors.append(f"modules must start at 1, got {numbers[0]} (gap)")
    for i in range(1, len(numbers)):
        if numbers[i] == numbers[i - 1]:
            errors.append(f"duplicate module number {numbers[i]}")
        elif numbers[i] != numbers[i - 1] + 1:
            errors.append(
                f"modules not dense: jump from {numbers[i - 1]} to {numbers[i]} (gap)"
            )
    return errors


def _check_module_onboarding_tasks(syllabus, module_templates) -> list[str]:
    onboarding_module_numbers: set[int] = set()
    for t in module_templates:
        if t.get("cadence") == "once-per-module" and "module_number" in t:
            onboarding_module_numbers.add(int(t["module_number"]))
    return [
        f"module {m.number} ({m.name!r}) has no once-per-module task in modules.yaml"
        for m in syllabus.modules
        if m.number not in onboarding_module_numbers
    ]


def _check_manifest_ritual_times(manifest: dict, ritual_times: dict) -> list[str]:
    required = manifest.get("ritual_times_required") or []
    available = set(ritual_times.keys())
    return [
        f"manifest requires ritual_time {name!r} but config has no such key"
        for name in required
        if name not in available
    ]


def _check_state_vs_syllabus(syllabus, current_module, month) -> list[str]:
    errors: list[str] = []
    if current_module is not None and current_module > len(syllabus.modules):
        errors.append(
            f"state.current_module={current_module} exceeds syllabus modules "
            f"({len(syllabus.modules)})"
        )
    if month is not None and syllabus.primary_book_by_month:
        max_m = max(syllabus.primary_book_by_month)
        if month > max_m:
            errors.append(
                f"state.month={month} exceeds syllabus max month ({max_m})"
            )
    return errors


def _check_cadences(templates: list[dict]) -> list[str]:
    return [
        f"template {t.get('id', '?')!r} has unknown cadence {t.get('cadence')!r} "
        f"(supported: {sorted(SUPPORTED_CADENCES)})"
        for t in templates
        if t.get("cadence") not in SUPPORTED_CADENCES
    ]


def _check_skip_ifs(templates: list[dict]) -> list[str]:
    errors: list[str] = []
    for t in templates:
        skip = t.get("skip_if")
        if skip is None:
            continue
        if isinstance(skip, str):
            skip = [skip]
        for rule in skip:
            if rule not in SUPPORTED_SKIP_IFS:
                errors.append(
                    f"template {t.get('id', '?')!r} has unknown skip_if rule {rule!r} "
                    f"(supported: {sorted(SUPPORTED_SKIP_IFS)})"
                )
    return errors


def _check_unique_ids(templates: list[dict]) -> list[str]:
    seen: dict[str, int] = {}
    for t in templates:
        tid = t.get("id")
        if tid is None:
            continue
        seen[tid] = seen.get(tid, 0) + 1
    return [
        f"duplicate template id {tid!r} (appears {n} times)"
        for tid, n in sorted(seen.items())
        if n > 1
    ]


# --- raw YAML helpers ---------------------------------------------------------

def _load_manifest(curriculum_dir: Path) -> dict:
    path = curriculum_dir / "manifest.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_yaml_one(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def _load_yaml_files(directory: Path) -> list[dict]:
    out: list[dict] = []
    if not directory.exists():
        return out
    for p in sorted(directory.glob("*.yaml")):
        out.extend(_load_yaml_one(p))
    return out
```

- [ ] **Step 4: Run validator tests**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest tests/test_curriculum_validator.py -v
```

Expected: all 11 PASS.

- [ ] **Step 5: Run validator on the live curriculum (sanity check)**

```bash
cd /Users/sauravsuresh/long-way-engine
python -c "
from pathlib import Path
from src.curriculum_validator import validate
from src.config import load_config
from src.state import load_state
cfg = load_config(Path('config.yaml'), Path('.env'))
st = load_state(Path('state.yaml'))
validate(Path('curriculum'), ritual_times=cfg.ritual_times,
         state_current_module=st.current_module, state_month=st.month)
print('OK')
"
```

Expected: `OK`. If errors fire, fix `curriculum/syllabus.yaml` (most likely a book-title mismatch in `primary_book_by_month`) and re-run until green.

- [ ] **Step 6: Run full test suite**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest -q
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add src/curriculum_validator.py tests/test_curriculum_validator.py
git commit -m "feat: add curriculum_validator with 10 fail-fast checks"
```

---

### Task 12: Wire validator + load_syllabus into main.py

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Import and call validator at startup**

Open `src/main.py`. Add to the imports near line 36:

```python
from src.syllabus import load_syllabus, current_book as syllabus_current_book
from src.curriculum_validator import validate as validate_curriculum
```

(Keep the existing `from src.syllabus import parse_books_from_file` for now — we'll remove it in Task 14.)

In the `__main__` block near line 762, after `state = load_state(STATE_PATH)`, add:

```python
    syllabus = load_syllabus(config.curriculum_dir if config.curriculum_dir.is_absolute()
                              else REPO_ROOT / config.curriculum_dir)
    validate_curriculum(
        config.curriculum_dir if config.curriculum_dir.is_absolute()
        else REPO_ROOT / config.curriculum_dir,
        ritual_times=config.ritual_times,
        state_current_module=state.current_module,
        state_month=state.month,
    )
```

- [ ] **Step 2: Run main.py dry-run**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m src.main --dry-run --date 2026-05-22 2>&1 | tail -20
```

Expected: no validator error; same dry-run output as before (syllabus loaded but not yet wired into task generation).

- [ ] **Step 3: Run full test suite + goldens**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest -q
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add src/main.py
git commit -m "feat(main): load + validate curriculum at startup"
```

---

## Phase E — Refactor callers to use Syllabus

### Task 13: Migrate `current_book` resolution in templates.py

**Files:**
- Modify: `src/templates.py`
- Modify: `src/main.py`
- Modify: `tests/test_templates.py`

- [ ] **Step 1: Add syllabus parameter to resolve_variables**

Open `src/templates.py`. Find `def resolve_variables(...)`. Current signature:

```python
def resolve_variables(template, state, config, today):
```

Add a `syllabus` parameter at the end (default `None` for backward compat during the migration):

```python
def resolve_variables(template, state, config, today, syllabus=None):
```

Find the `current_book` handler around line 112:

```python
if name == "current_book":
    if state.current_book:
        return state.current_book
    return syllabus.current_book(state.month)
```

Wait — that already says `syllabus.current_book(...)`. Check what `syllabus` refers to there. It's `from src import syllabus` (module import) calling the legacy `current_book(month)`. Change it to the new signature passing the loaded Syllabus object:

```python
if name == "current_book":
    if state.current_book:
        return state.current_book
    from src.syllabus import current_book as _cb
    return _cb(state.month, syllabus)
```

The local `syllabus` parameter is now the Syllabus dataclass instance (or None). The `current_book(month, syllabus)` signature added in Task 10 handles both cases — falls back to module-level dict when syllabus is None.

- [ ] **Step 2: Update main.py to pass syllabus through**

Open `src/main.py`. Find every call to `resolve_variables(...)` (there's one near line 330):

```python
resolved = resolve_variables(tpl, state, config, today)
```

Change to:

```python
resolved = resolve_variables(tpl, state, config, today, syllabus=syllabus)
```

But `syllabus` isn't in scope inside `run()` yet. Update `run()`'s signature near line 260 to accept a `syllabus` argument:

```python
def run(
    config: Config,
    state: State,
    today: date,
    template_paths: list[Path],
    cache_path: Path,
    *,
    syllabus=None,
    ...
```

(`syllabus=None` kwarg so old test call sites keep working.)

Update the `__main__` block's `run(...)` call near line 792 to pass `syllabus=syllabus`.

- [ ] **Step 3: Update test_templates.py if it calls resolve_variables**

```bash
cd /Users/sauravsuresh/long-way-engine
grep -n "resolve_variables" tests/test_templates.py
```

For any caller that doesn't pass a syllabus, it just gets `None` — the legacy dict fallback still works. No changes needed unless a test specifically wants to test the new path.

- [ ] **Step 4: Run all tests + goldens**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest -q
```

Expected: all green. Goldens still match because syllabus.primary_book_by_month was generated from the same data as the legacy dict — resolution yields the same titles.

- [ ] **Step 5: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add src/templates.py src/main.py
git commit -m "refactor: pass Syllabus through to current_book resolution"
```

---

### Task 14: Replace `parse_books_from_file` with `syllabus.books` in dashboard

**Files:**
- Modify: `src/main.py`
- Modify: `src/dashboard.py`

- [ ] **Step 1: Replace the parse_books_from_file call in main.py**

Open `src/main.py`. Find around line 233:

```python
try:
    books = parse_books_from_file()
except OSError:
    books = []
```

Replace with:

```python
books = syllabus.books if syllabus is not None else []
```

`syllabus` reaches `_render_dashboard_summary` (or wherever this block lives) — trace the call chain. If the function doesn't currently take `syllabus` as a parameter, add it. Search:

```bash
cd /Users/sauravsuresh/long-way-engine
grep -n "parse_books_from_file\|def render_dashboard\|def _render" src/main.py
```

Add `syllabus=None` to the helper's signature and pass it from the `__main__` block.

- [ ] **Step 2: Remove the import of parse_books_from_file in main.py**

Open `src/main.py`. Find line 36:

```python
from src.syllabus import parse_books_from_file
```

Delete this line. Verify with:

```bash
cd /Users/sauravsuresh/long-way-engine
grep -n "parse_books_from_file" src/main.py
```

Expected: no results.

- [ ] **Step 3: Run all tests + goldens**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest -q
```

Expected: all green. The dashboard reading-list output is identical because `syllabus.books` was generated from the same `the-long-way.md` regex parse.

- [ ] **Step 4: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add src/main.py src/dashboard.py
git commit -m "refactor: dashboard reads books from Syllabus instead of regex"
```

---

### Task 15: Dashboard derives counts from Syllabus

**Files:**
- Modify: `src/dashboard.py`
- Modify: `src/main.py`

- [ ] **Step 1: Replace hardcoded module-level constants**

Open `src/dashboard.py`. Find lines 51–54:

```python
TOTAL_MONTHS = 39
TOTAL_MODULES = 23
PHASE_BOUNDARIES = (1, 13, 21, 31, 39)
```

These are module-level constants used by `_progress_bar`, `_module_trunk`, `_end_of_journey`, and the phase-tick rendering. We'll keep the names but compute them from syllabus inside `render_dashboard()` and pass them down via existing helper signatures.

Replace those three lines with:

```python
# Defaults — kept for any legacy caller that doesn't pass a Syllabus.
# render_dashboard() recomputes from the live syllabus and overrides
# locally before calling helpers.
DEFAULT_TOTAL_MONTHS = 39
DEFAULT_TOTAL_MODULES = 23
DEFAULT_PHASE_BOUNDARIES = (1, 13, 21, 31, 39)
```

Then add helper functions:

```python
def _phase_boundaries_from_syllabus(syllabus) -> tuple[int, ...]:
    """Phase tick positions: each phase's start_month, plus the final end_month."""
    if syllabus is None or not syllabus.phases:
        return DEFAULT_PHASE_BOUNDARIES
    phases = sorted(syllabus.phases, key=lambda p: p.number)
    return tuple([p.months[0] for p in phases] + [phases[-1].months[1]])


def _total_months_from_syllabus(syllabus) -> int:
    if syllabus is None or not syllabus.primary_book_by_month:
        return DEFAULT_TOTAL_MONTHS
    return max(syllabus.primary_book_by_month)


def _total_modules_from_syllabus(syllabus) -> int:
    if syllabus is None or not syllabus.modules:
        return DEFAULT_TOTAL_MODULES
    return len(syllabus.modules)
```

- [ ] **Step 2: Wire them through `render_dashboard`**

Find `def render_dashboard(...)` around line 673. Add `syllabus=None` to its kwargs. Inside the function body, near the top:

```python
total_months = _total_months_from_syllabus(syllabus)
total_modules = _total_modules_from_syllabus(syllabus)
phase_boundaries = _phase_boundaries_from_syllabus(syllabus)
```

Then everywhere in this file that references `TOTAL_MONTHS`, `TOTAL_MODULES`, or `PHASE_BOUNDARIES` (lines 52, 53, 59, 210, the phase-tick rendering around line 330), replace with the local variables.

Specifically for line 330 — the hardcoded phase-tick list:

```python
PHASE_TICK_LABELS = [
    (1, 12, "Phase 1 · Foundations"),
    (13, 20, "Phase 2 · Go & Backend"),
    (21, 30, "Phase 3 · Distributed Systems"),
    (31, 39, "Phase 4 · Synthesis"),
]
```

Build this dynamically from syllabus.phases:

```python
def _phase_tick_labels(syllabus, fallback):
    if syllabus is None or not syllabus.phases:
        return fallback
    phases = sorted(syllabus.phases, key=lambda p: p.number)
    return [
        (p.months[0], p.months[1], f"Phase {p.number} · {p.name}")
        for p in phases
    ]
```

Use it inside `render_dashboard()`.

For `_end_of_journey(start, months=TOTAL_MONTHS)`, update call sites in this file to pass `total_months` explicitly.

- [ ] **Step 3: Pass syllabus into render_dashboard call**

Open `src/main.py`. Find the `render_dashboard(...)` call (around line 237 in `_render_dashboard_summary` or similar). Add `syllabus=syllabus` to the kwargs.

- [ ] **Step 4: Run all tests + goldens**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest -q
```

Expected: all green. Dashboard HTML output should be byte-identical to current — same phase labels, same module count, same month-of-39, all derived from the same data.

- [ ] **Step 5: Eyeball the live dashboard output**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m src.main --dry-run --date 2026-05-22 2>&1 | grep -i "phase\|module\|of 39" | head -10
```

Expected: shows the same phase labels, "Month X of 39", "Module N of 23" as before.

- [ ] **Step 6: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add src/dashboard.py src/main.py
git commit -m "refactor(dashboard): derive phase/month/module counts from Syllabus"
```

---

## Phase F — Delete the regex parser and legacy dict

### Task 16: Remove `PRIMARY_BOOK_BY_MONTH`, regex parser, `the-long-way.md` parsing

**Files:**
- Modify: `src/syllabus.py`
- Modify: `tests/test_syllabus.py`

- [ ] **Step 1: Confirm no remaining callers**

```bash
cd /Users/sauravsuresh/long-way-engine
grep -rn "parse_books_from_file\|parse_books\|PRIMARY_BOOK_BY_MONTH\|SYLLABUS_PATH" src tests --include="*.py" | grep -v __pycache__
```

Expected: only `src/syllabus.py` itself, plus `tests/test_syllabus.py` for legacy drift tests. If any other file still imports these, fix it before continuing.

- [ ] **Step 2: Delete the legacy block from src/syllabus.py**

Open `src/syllabus.py`. Delete:

- `SYLLABUS_PATH` (line 34)
- `_PHASE_SECTION_RE`, `_BOOK_RE`, `_MONTHS_RE` (lines 53–68)
- `parse_books()` (lines 71–89)
- `parse_books_from_file()` (lines 92–93)
- `PRIMARY_BOOK_BY_MONTH` dict (lines 100–160)
- `normalize_for_drift_check()` (lines 183–191) and `_NON_ALNUM` (line 180)

Update `current_book(month, syllabus=None)` — it can no longer fall back to `PRIMARY_BOOK_BY_MONTH`. Replace with:

```python
def current_book(month: int, syllabus: "Syllabus") -> str:
    """Primary book for `month` with carry-forward.

    Returns "" only when no prior month is mapped.
    """
    table = syllabus.primary_book_by_month
    if month in table:
        return table[month]
    for m in range(month - 1, 0, -1):
        if m in table:
            return table[m]
    return ""
```

Update the module docstring at the top of `src/syllabus.py` to describe the new minimal surface area (just `load_syllabus`, `Syllabus`, `current_book`, `Book`, `Phase`, `Module`).

- [ ] **Step 3: Update tests/test_syllabus.py**

Open `tests/test_syllabus.py`. Find tests that import or reference `PRIMARY_BOOK_BY_MONTH`, `parse_books`, `parse_books_from_file`, `normalize_for_drift_check`. Delete those tests (the drift sanity test in particular is no longer meaningful — validator owns this).

Keep the two tests added in Task 10 (`test_load_syllabus_from_curriculum_dir`, `test_current_book_with_syllabus`). Adapt the second to pass a Syllabus mandatorily (no `None` fallback now):

```python
def test_current_book_with_syllabus(tmp_path: Path) -> None:
    from src.syllabus import Syllabus, Phase, Book as SylBook, Module, current_book
    syl = Syllabus(
        meta={"name": "T", "start_month_index": 1},
        phases=[Phase(number=1, name="P1", months=(1, 5))],
        books=[SylBook(title="A", author="x", phase=1, months=(1, 3), role="primary")],
        primary_book_by_month={1: "A", 2: "A", 3: "A"},
        modules=[Module(number=1, name="M1", phase=1)],
    )
    assert current_book(1, syl) == "A"
    assert current_book(3, syl) == "A"
    assert current_book(4, syl) == "A"
    assert current_book(0, syl) == ""
```

(The `Book` dataclass field name issue: in src/syllabus.py the existing `Book` has `start_month`/`end_month`. The new test fixture uses `months=(1, 3)`. Reconcile: the new schema has months as a tuple, the existing Book dataclass has start_month/end_month. Either rename the dataclass field for consistency, or keep Book using start_month/end_month and translate in load_syllabus. The Task 10 step 3 implementation already does this translation, so leave Book unchanged and update the test fixture to use `start_month=1, end_month=3`.)

Update the test:

```python
books=[SylBook(title="A", author="x", phase=1, start_month=1, end_month=3)],
```

(Drop the `months=` and `role=` kwargs that aren't fields of `Book`. The hand-written test fixture used the YAML schema; the dataclass uses the parsed form.)

- [ ] **Step 4: Run syllabus tests**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest tests/test_syllabus.py -v
```

Expected: all PASS.

- [ ] **Step 5: Run full suite + goldens**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest -q
```

Expected: all green. Goldens still match.

- [ ] **Step 6: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add src/syllabus.py tests/test_syllabus.py
git commit -m "refactor: remove regex parser and PRIMARY_BOOK_BY_MONTH dict from syllabus.py"
```

---

## Phase G — Forker docs + example curricula

### Task 17: Write AGENTS.md

**Files:**
- Create: `AGENTS.md`

- [ ] **Step 1: Write the file**

Create `AGENTS.md` in the repo root with the following exact content:

````markdown
# AGENTS.md — Building a curriculum for long-way-engine

This file tells an AI agent how to help a user build a curriculum
bundle that the long-way-engine can run. If you are an AI invoked by
a user in a fork of this repo, read this end-to-end before producing
files.

---

## 1. What this engine does

`long-way-engine` turns a multi-month learning plan into Todoist tasks
and a dashboard. Every day it:

- Loads the active curriculum from `curriculum/` (path configurable
  via `config.yaml`'s `curriculum_dir` key).
- Reads `state.yaml` for the user's current phase, month, and module.
- Walks every template in `curriculum/rituals/*.yaml` and
  `curriculum/modules.yaml`, decides which fire today based on cadence
  rules, resolves placeholder variables, and creates Todoist tasks
  (deduped via a local cache).
- Renders a static HTML dashboard from state + completion data.

Three pieces are pluggable; two are not.

**Pluggable (forker edits):**

- `curriculum/syllabus.yaml` — phases, months, books, modules
- `curriculum/rituals/*.yaml` — daily/weekly/monthly/quarterly/annual
  ritual + practice templates
- `curriculum/modules.yaml` — module onboarding tasks + lineage detours
- `curriculum/reflection_templates/*.md` — reflection stub templates
- `curriculum/manifest.yaml` — declares which ritual_times and
  placeholders the bundle needs

**Not pluggable (engine code defines):**

- Cadence vocabulary: `daily`, `weekly`, `monthly`, `quarterly`,
  `annual`, `once-per-module`
- Skip-rule vocabulary: `sunday`, `pair_day`, `last-saturday-of-month`
- Placeholder substitution syntax: `{current_book}`,
  `{ritual_times.X}`, `{iso_year}-W{iso_week:02d}`, `{year}`, `{month}`,
  `{quarter}`, `{current_module}`

---

## 2. File layout you will produce

```
curriculum/
├── syllabus.yaml
├── manifest.yaml
├── modules.yaml
├── rituals/
│   ├── daily.yaml
│   ├── weekly.yaml
│   ├── monthly.yaml
│   ├── quarterly.yaml
│   ├── annual.yaml
│   └── practices.yaml
└── reflection_templates/
    ├── weekly.md
    ├── monthly.md
    ├── quarterly.md
    └── annual.md
```

Required files: `syllabus.yaml`, `manifest.yaml`, `modules.yaml`, at
least one ritual yaml. Reflection templates are optional but
recommended.

---

## 3. Schema reference

### `syllabus.yaml`

```yaml
meta:
  name: string                     # display name
  total_months: int                # optional; derived from phases if omitted
  start_month_index: 1             # almost always 1

phases:
  - number: int                    # dense 1..N
    name: string
    months: [start, end]           # inclusive, contiguous across phases

books:
  - title: string                  # must match primary_book_by_month values
    author: string
    phase: int                     # must reference an existing phase
    months: [start, end]           # optional; omit for reference-only
    role: primary|secondary|reference

primary_book_by_month:
  1: "Book Title"                  # title must exist in books[]
  2: "Book Title"
  # gaps are OK — engine carries forward from prior month

modules:
  - number: int                    # dense 1..N, no gaps
    name: string
    phase: int                     # must reference an existing phase
    estimated_hours: int           # optional, dashboard-only
```

### `manifest.yaml`

```yaml
ritual_times_required:
  - morning_reading                # must exist in config.yaml ritual_times
  - evening_hands_on
  # ... etc

placeholders_used:
  - current_book
  - current_module
  - iso_year
  # ... etc — informational, not validated

config_flags:
  pair_day: thursday               # default; user overrides in config.yaml
  sunday_off: true
```

### `rituals/*.yaml`

Each file is a YAML list of templates. A template:

```yaml
- id: string                       # unique across the entire curriculum
  title: string                    # with placeholders like {current_book}
  description: |
    Multi-line. Same placeholder rules as title.
  due: "today at {ritual_times.morning_reading}"
  labels: [list, of, strings]
  cadence: daily|weekly|monthly|quarterly|annual|once-per-module
  skip_if:                         # optional; rules ANDed
    - sunday                       # global rest day
    - pair_day                     # config.pair_day weekday
    - last-saturday-of-month       # last Saturday of current month
  day_of_week: monday              # required for cadence: weekly
  day_of_month: 1                  # required for cadence: monthly
                                   # may be int 1..28, "last-day",
                                   # or "last-saturday"
  module_number: int               # required for cadence: once-per-module
  reflection:                      # optional
    create_stub: true
    stub_path: "reflections/weekly/{iso_year}-W{iso_week:02d}.md"
```

### `modules.yaml`

Same schema as rituals/*.yaml, but every entry has
`cadence: once-per-module` and a `module_number`. Each module in
syllabus.modules must have at least one onboarding task here. Multiple
tasks per module_number are allowed (e.g., lineage detours that fire
on the same module advance).

### `reflection_templates/*.md`

Markdown templates with `{date}`, `{week}`, `{year}`, `{month}`,
`{quarter}` placeholders. Loaded when a ritual template with
`reflection.create_stub: true` fires.

---

## 4. Validation rules the engine enforces at startup

`src/curriculum_validator.py` runs these checks. Failure aggregates
every violation into a single error message.

1. Every `primary_book_by_month` value exactly matches some
   `books[].title`.
2. `phases[*].months` are contiguous with no gaps; phase 1 starts at
   `meta.start_month_index`.
3. Every `modules[].phase` references an existing `phases[].number`.
4. `modules[].number` is dense 1..N with no gaps and no duplicates.
5. Every `syllabus.modules[].number` has at least one
   `cadence: once-per-module` task in `modules.yaml`.
6. Every `manifest.ritual_times_required` entry exists in
   `config.yaml`'s `ritual_times`.
7. `state.current_module ≤ len(modules)` and `state.month ≤
   max(primary_book_by_month)`.
8. Every `cadence` value is in the supported set.
9. Every `skip_if` rule is in the supported vocabulary.
10. Every template `id` is unique across the curriculum.

---

## 5. Interview protocol

When a user says "help me build a curriculum", run these seven steps.
Ask one question at a time. Confirm before moving on.

**Step 1 — Goal & duration.** Ask: "What are you trying to be able
to do, and over what time horizon?" Probe for concrete outcomes
("a deployable thing", not "understand X"). Pin a total month count.
Don't accept "a year-ish" — pick a number.

**Step 2 — Phase split.** Propose 2–4 phases that sequence skills.
Each phase ends with a demonstrable capability ("can write a basic
Go HTTP server", not "knows about Go"). Phases should be contiguous
month ranges. Confirm.

**Step 3 — Books / primary resources per month.** For each month,
pick ONE primary resource — usually a book, sometimes a course or a
project. Carry-forward is fine: if months 11–12 are project-only
with no new book, don't add entries for them; the engine carries
the month 10 entry forward.

**Step 4 — Modules.** Within each phase, define 2–8 modules
(~2–6 weeks each). Modules are discrete units the user advances
through one at a time (`state.current_module` only goes up). Give
each a `name` and an `estimated_hours`. Author one onboarding task
per module in `modules.yaml`.

**Step 5 — Rituals.** Use this recommended skeleton, adapt to the
user's life:

| Cadence | Suggested ritual |
|---|---|
| daily | morning study (~30 min) |
| daily | spaced-repetition review (~15 min) |
| daily | evening hands-on (~60–90 min) |
| weekly | end-of-week retrieval (~20 min) |
| weekly | deep block (~3–4 hours) |
| weekly | one active practice (rotates) |
| monthly | public write-up (1st of month) |
| monthly | retrieval (last Saturday) |
| monthly | retrospective (last Saturday) |
| quarterly | synthesis essay |
| annual | full review + plan revision |

Map each ritual to a `ritual_times` slot in `config.yaml`. Add those
slot names to `manifest.ritual_times_required`.

**Step 6 — Practices (optional).** Weekly cadence templates that
aren't routine — deliberate skill drills like "trace one system
end-to-end", "read real code", "pair with a senior". Use
`day_of_week` to spread them across the week so they don't all land
on Saturday.

**Step 7 — Write files, run validator, dry-run.** Produce all YAML
files. Run:

```bash
python -c "
from pathlib import Path
from src.curriculum_validator import validate
from src.config import load_config
from src.state import load_state
cfg = load_config(Path('config.yaml'), Path('.env'))
st = load_state(Path('state.yaml'))
validate(Path('curriculum'), ritual_times=cfg.ritual_times,
         state_current_module=st.current_module, state_month=st.month)
print('OK')
"
```

Fix every error until validator prints `OK`. Then:

```bash
python -m src.main --dry-run --date $(date +%Y-%m-%d)
```

Confirm a sensible task set fires for today. Done.

---

## 6. Anti-patterns

- **No artifact = no learning week.** A week of pure reading without
  a writeup, a commit, or a public note is forgotten. Every weekly
  ritual should produce something.
- **More than ~8 modules per phase.** If you need more, it's two
  phases.
- **Inventing cadences.** Don't author `every_other_wednesday`. Use
  what exists. Open an issue if a real new cadence is needed.
- **One primary book per unique month.** Carry-forward is the
  point. Long books span many months. Sparse `primary_book_by_month`
  is correct.
- **Templates without an `id`.** Always set one. Engine uses it as
  the Todoist dedupe key.

---

## 7. Examples

- `examples/ml-engineer-12mo/` — 12-month ML engineer path, 3 phases,
  ~9 modules
- `examples/frontend-craft-6mo/` — 6-month frontend deep-dive, 2
  phases, ~6 modules

Both validate cleanly via `python -m src.curriculum_validator`. Copy
one as a starting point.
````

- [ ] **Step 2: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add AGENTS.md
git commit -m "docs: add AGENTS.md describing pluggable curriculum + interview protocol"
```

---

### Task 18: Example curriculum — ml-engineer-12mo

**Files:**
- Create: `examples/ml-engineer-12mo/syllabus.yaml`
- Create: `examples/ml-engineer-12mo/manifest.yaml`
- Create: `examples/ml-engineer-12mo/modules.yaml`
- Create: `examples/ml-engineer-12mo/rituals/{daily,weekly,monthly}.yaml`
- Create: `examples/ml-engineer-12mo/reflection_templates/{weekly,monthly}.md`

- [ ] **Step 1: Create the directory tree**

```bash
cd /Users/sauravsuresh/long-way-engine
mkdir -p examples/ml-engineer-12mo/rituals examples/ml-engineer-12mo/reflection_templates
```

- [ ] **Step 2: Author the example syllabus**

Create `examples/ml-engineer-12mo/syllabus.yaml`:

```yaml
meta:
  name: "ML Engineer (12 months)"
  total_months: 12
  start_month_index: 1

phases:
  - number: 1
    name: "Foundations: Python + Math"
    months: [1, 4]
  - number: 2
    name: "Classical ML + Deep Learning"
    months: [5, 8]
  - number: 3
    name: "Systems + Productionization"
    months: [9, 12]

books:
  - title: "Fluent Python"
    author: "Luciano Ramalho"
    phase: 1
    months: [1, 2]
    role: primary
  - title: "Mathematics for Machine Learning"
    author: "Deisenroth, Faisal, Ong"
    phase: 1
    months: [3, 4]
    role: primary
  - title: "Hands-On Machine Learning"
    author: "Aurélien Géron"
    phase: 2
    months: [5, 6]
    role: primary
  - title: "Deep Learning"
    author: "Goodfellow, Bengio, Courville"
    phase: 2
    months: [7, 8]
    role: primary
  - title: "Designing Machine Learning Systems"
    author: "Chip Huyen"
    phase: 3
    months: [9, 10]
    role: primary
  - title: "Machine Learning Engineering"
    author: "Andriy Burkov"
    phase: 3
    months: [11, 12]
    role: primary

primary_book_by_month:
  1: "Fluent Python"
  2: "Fluent Python"
  3: "Mathematics for Machine Learning"
  4: "Mathematics for Machine Learning"
  5: "Hands-On Machine Learning"
  6: "Hands-On Machine Learning"
  7: "Deep Learning"
  8: "Deep Learning"
  9: "Designing Machine Learning Systems"
  10: "Designing Machine Learning Systems"
  11: "Machine Learning Engineering"
  12: "Machine Learning Engineering"

modules:
  - number: 1
    name: "Python Deep Dive"
    phase: 1
    estimated_hours: 60
  - number: 2
    name: "Linear Algebra & Probability"
    phase: 1
    estimated_hours: 80
  - number: 3
    name: "Calculus & Optimization"
    phase: 1
    estimated_hours: 60
  - number: 4
    name: "Classical ML: Regression, Trees, SVM"
    phase: 2
    estimated_hours: 80
  - number: 5
    name: "Neural Networks from Scratch"
    phase: 2
    estimated_hours: 80
  - number: 6
    name: "Transformers & Attention"
    phase: 2
    estimated_hours: 60
  - number: 7
    name: "Data Pipelines & Feature Stores"
    phase: 3
    estimated_hours: 60
  - number: 8
    name: "Model Serving & Monitoring"
    phase: 3
    estimated_hours: 60
  - number: 9
    name: "Capstone: End-to-End Production Model"
    phase: 3
    estimated_hours: 100
```

- [ ] **Step 3: Author the manifest**

Create `examples/ml-engineer-12mo/manifest.yaml`:

```yaml
ritual_times_required:
  - morning_reading
  - evening_hands_on
  - friday_review
  - saturday_deep_block

placeholders_used:
  - current_book
  - current_module
  - iso_year
  - iso_week
  - year
  - month

config_flags:
  sunday_off: true
```

- [ ] **Step 4: Author one onboarding task per module**

Create `examples/ml-engineer-12mo/modules.yaml`:

```yaml
- id: ml-module-01-onboarding
  module_number: 1
  title: "Module 1: Python Deep Dive — start"
  description: |
    60 hrs. Read Fluent Python cover-to-cover. Every example into a
    notebook. Skim chapters you know; do exercises for what you don't.
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: ml-module-02-onboarding
  module_number: 2
  title: "Module 2: Linear Algebra & Probability — start"
  description: |
    80 hrs. MIT 18.06 (Strang) + 3Blue1Brown Essence of LA. Hand-derive
    PCA at the end. Do every problem set.
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: ml-module-03-onboarding
  module_number: 3
  title: "Module 3: Calculus & Optimization — start"
  description: |
    60 hrs. Multivariable calc + gradient descent variants. Implement
    SGD, momentum, Adam from scratch.
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: ml-module-04-onboarding
  module_number: 4
  title: "Module 4: Classical ML — start"
  description: |
    80 hrs. Géron book + scikit-learn. Build five end-to-end pipelines
    on real tabular data (UCI, Kaggle).
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: ml-module-05-onboarding
  module_number: 5
  title: "Module 5: Neural Networks from Scratch — start"
  description: |
    80 hrs. Implement a multi-layer perceptron in NumPy with manual
    backprop. THEN switch to PyTorch. Karpathy's zero-to-hero series.
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: ml-module-06-onboarding
  module_number: 6
  title: "Module 6: Transformers & Attention — start"
  description: |
    60 hrs. Re-implement attention, build a small transformer from
    scratch, train it on a tiny dataset. "Attention Is All You Need"
    + Karpathy nanoGPT walkthrough.
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: ml-module-07-onboarding
  module_number: 7
  title: "Module 7: Data Pipelines & Feature Stores — start"
  description: |
    60 hrs. Build a Feast/Tecton-style feature store from scratch.
    DAG orchestration with Prefect or Dagster.
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: ml-module-08-onboarding
  module_number: 8
  title: "Module 8: Model Serving & Monitoring — start"
  description: |
    60 hrs. Serve a model behind FastAPI + GPU. Add Prometheus/Grafana.
    Detect drift.
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: ml-module-09-onboarding
  module_number: 9
  title: "Module 9: Capstone — start"
  description: |
    100 hrs. Pick one real problem. Ship end-to-end: ingestion, train,
    serve, monitor, retrain. Public repo + write-up.
  due: "today"
  labels: [module-work]
  cadence: once-per-module
```

- [ ] **Step 5: Author rituals**

Create `examples/ml-engineer-12mo/rituals/daily.yaml`:

```yaml
- id: ml-daily-morning-reading
  title: "Morning reading: {current_book}"
  description: |
    30 min. Paper book, paper notebook.
    Today's book: {current_book}.
  due: "today at {ritual_times.morning_reading}"
  labels: [daily-ritual]
  cadence: daily
  skip_if: sunday

- id: ml-daily-evening-build
  title: "Evening build (60–90 min)"
  description: |
    Work the current module. Code on the keyboard, not in your head.
  due: "today at {ritual_times.evening_hands_on}"
  labels: [daily-ritual]
  cadence: daily
  skip_if: sunday
```

Create `examples/ml-engineer-12mo/rituals/weekly.yaml`:

```yaml
- id: ml-weekly-friday-review
  title: "Friday review: 20-min retrieval"
  description: |
    Without looking at notes, write the 3 most important things from
    this week. Compare. The gap is your Anki for next week.
  due: "today at {ritual_times.friday_review}"
  labels: [weekly-ritual, reflection]
  cadence: weekly
  day_of_week: friday
  reflection:
    create_stub: true
    stub_path: "reflections/weekly/{iso_year}-W{iso_week:02d}.md"

- id: ml-weekly-saturday-deep-block
  title: "Saturday deep block (3–4 hr)"
  description: |
    Long uninterrupted block on the current module or the capstone.
  due: "today at {ritual_times.saturday_deep_block}"
  labels: [weekly-ritual]
  cadence: weekly
  day_of_week: saturday
```

Create `examples/ml-engineer-12mo/rituals/monthly.yaml`:

```yaml
- id: ml-monthly-writeup
  title: "Monthly write-up: ship a public artifact"
  description: |
    800–2000 words. Public, real name. Show your work — code,
    diagrams, real numbers.
  due: "today at {ritual_times.morning_reading}"
  labels: [monthly-ritual]
  cadence: monthly
  day_of_month: 1

- id: ml-monthly-review
  title: "Monthly review: what worked, what didn't"
  description: |
    End-of-month retrospective. The plan evolves at month boundaries.
  due: "today at {ritual_times.saturday_deep_block}"
  labels: [monthly-ritual, reflection]
  cadence: monthly
  day_of_month: last-saturday
  reflection:
    create_stub: true
    stub_path: "reflections/monthly/{year}-{month:02d}.md"
```

- [ ] **Step 6: Author reflection templates**

Create `examples/ml-engineer-12mo/reflection_templates/weekly.md`:

```markdown
# Week {week} — {date}

## Three things I learned

1.
2.
3.

## Where I struggled

## What's next week
```

Create `examples/ml-engineer-12mo/reflection_templates/monthly.md`:

```markdown
# {year}-{month:02d} review

## What worked

## What didn't

## Adjustments
```

- [ ] **Step 7: Validate the example loads cleanly**

```bash
cd /Users/sauravsuresh/long-way-engine
python -c "
from pathlib import Path
from src.curriculum_validator import validate
validate(Path('examples/ml-engineer-12mo'), ritual_times={
    'morning_reading': '06:00',
    'evening_hands_on': '19:00',
    'friday_review': '20:00',
    'saturday_deep_block': '09:00',
})
print('OK')
"
```

Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add examples/ml-engineer-12mo
git commit -m "feat: add ml-engineer-12mo example curriculum"
```

---

### Task 19: Example curriculum — frontend-craft-6mo

**Files:**
- Create: `examples/frontend-craft-6mo/syllabus.yaml`
- Create: `examples/frontend-craft-6mo/manifest.yaml`
- Create: `examples/frontend-craft-6mo/modules.yaml`
- Create: `examples/frontend-craft-6mo/rituals/{daily,weekly,monthly}.yaml`
- Create: `examples/frontend-craft-6mo/reflection_templates/{weekly,monthly}.md`

- [ ] **Step 1: Create directory tree**

```bash
cd /Users/sauravsuresh/long-way-engine
mkdir -p examples/frontend-craft-6mo/rituals examples/frontend-craft-6mo/reflection_templates
```

- [ ] **Step 2: Author syllabus.yaml**

Create `examples/frontend-craft-6mo/syllabus.yaml`:

```yaml
meta:
  name: "Frontend Craft (6 months)"
  total_months: 6
  start_month_index: 1

phases:
  - number: 1
    name: "Browser & TypeScript Fundamentals"
    months: [1, 3]
  - number: 2
    name: "Design Systems & Polish"
    months: [4, 6]

books:
  - title: "Eloquent JavaScript"
    author: "Marijn Haverbeke"
    phase: 1
    months: [1, 2]
    role: primary
  - title: "Programming TypeScript"
    author: "Boris Cherny"
    phase: 1
    months: [3, 3]
    role: primary
  - title: "Refactoring UI"
    author: "Adam Wathan & Steve Schoger"
    phase: 2
    months: [4, 4]
    role: primary
  - title: "Inclusive Components"
    author: "Heydon Pickering"
    phase: 2
    months: [5, 6]
    role: primary

primary_book_by_month:
  1: "Eloquent JavaScript"
  2: "Eloquent JavaScript"
  3: "Programming TypeScript"
  4: "Refactoring UI"
  5: "Inclusive Components"
  6: "Inclusive Components"

modules:
  - number: 1
    name: "Vanilla JS & the DOM"
    phase: 1
    estimated_hours: 60
  - number: 2
    name: "TypeScript End to End"
    phase: 1
    estimated_hours: 50
  - number: 3
    name: "React Fundamentals"
    phase: 1
    estimated_hours: 60
  - number: 4
    name: "Design Systems & Tokens"
    phase: 2
    estimated_hours: 50
  - number: 5
    name: "Accessibility Deep Dive"
    phase: 2
    estimated_hours: 50
  - number: 6
    name: "Capstone: Production-Grade UI"
    phase: 2
    estimated_hours: 80
```

- [ ] **Step 3: Author manifest.yaml**

Create `examples/frontend-craft-6mo/manifest.yaml`:

```yaml
ritual_times_required:
  - morning_reading
  - evening_hands_on
  - saturday_deep_block

placeholders_used:
  - current_book
  - current_module
  - iso_year
  - iso_week
  - year
  - month

config_flags:
  sunday_off: true
```

- [ ] **Step 4: Author modules.yaml (one onboarding task per module)**

Create `examples/frontend-craft-6mo/modules.yaml`:

```yaml
- id: fe-module-01-onboarding
  module_number: 1
  title: "Module 1: Vanilla JS & the DOM — start"
  description: |
    60 hrs. Eloquent JS first half. Build three vanilla-JS toys
    without any framework: a draggable kanban, a markdown previewer,
    a sortable table.
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: fe-module-02-onboarding
  module_number: 2
  title: "Module 2: TypeScript End to End — start"
  description: |
    50 hrs. Cherny + the official TS handbook. Convert one of your
    vanilla projects to strict TypeScript.
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: fe-module-03-onboarding
  module_number: 3
  title: "Module 3: React Fundamentals — start"
  description: |
    60 hrs. Build a real app — not todos. Routing, forms, optimistic
    updates, error boundaries.
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: fe-module-04-onboarding
  module_number: 4
  title: "Module 4: Design Systems & Tokens — start"
  description: |
    50 hrs. Refactoring UI cover-to-cover. Build a design token
    system. Ship a Storybook with 20+ components.
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: fe-module-05-onboarding
  module_number: 5
  title: "Module 5: Accessibility Deep Dive — start"
  description: |
    50 hrs. WAI-ARIA. Screen reader testing with VoiceOver/NVDA.
    Audit and fix one open-source project.
  due: "today"
  labels: [module-work]
  cadence: once-per-module

- id: fe-module-06-onboarding
  module_number: 6
  title: "Module 6: Capstone — start"
  description: |
    80 hrs. Ship one production-grade UI to a public URL. Real users,
    real metrics, real bug reports.
  due: "today"
  labels: [module-work]
  cadence: once-per-module
```

- [ ] **Step 5: Author rituals + reflection templates**

Create `examples/frontend-craft-6mo/rituals/daily.yaml`:

```yaml
- id: fe-daily-morning-reading
  title: "Morning reading: {current_book}"
  description: |
    30 min. Today: {current_book}.
  due: "today at {ritual_times.morning_reading}"
  labels: [daily-ritual]
  cadence: daily
  skip_if: sunday

- id: fe-daily-evening-build
  title: "Evening build"
  description: |
    Push pixels. Ship the current module.
  due: "today at {ritual_times.evening_hands_on}"
  labels: [daily-ritual]
  cadence: daily
  skip_if: sunday
```

Create `examples/frontend-craft-6mo/rituals/weekly.yaml`:

```yaml
- id: fe-weekly-saturday-deep-block
  title: "Saturday deep block: ship something visible"
  description: |
    3–4 hours. End the day with something a user could click.
  due: "today at {ritual_times.saturday_deep_block}"
  labels: [weekly-ritual]
  cadence: weekly
  day_of_week: saturday
```

Create `examples/frontend-craft-6mo/rituals/monthly.yaml`:

```yaml
- id: fe-monthly-writeup
  title: "Monthly write-up + screenshots"
  description: |
    Public post with before/after screenshots. Real numbers — Lighthouse
    scores, bundle size, accessibility violations fixed.
  due: "today at {ritual_times.morning_reading}"
  labels: [monthly-ritual]
  cadence: monthly
  day_of_month: 1
```

Create `examples/frontend-craft-6mo/reflection_templates/weekly.md`:

```markdown
# Week {week} — {date}

## What did I ship?

## What looked worse than I thought?

## Next week
```

Create `examples/frontend-craft-6mo/reflection_templates/monthly.md`:

```markdown
# {year}-{month:02d}

## Visual diff (before / after)

## Lighthouse

## Adjustments
```

- [ ] **Step 6: Validate the example**

```bash
cd /Users/sauravsuresh/long-way-engine
python -c "
from pathlib import Path
from src.curriculum_validator import validate
validate(Path('examples/frontend-craft-6mo'), ritual_times={
    'morning_reading': '06:00',
    'evening_hands_on': '19:00',
    'saturday_deep_block': '09:00',
})
print('OK')
"
```

Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add examples/frontend-craft-6mo
git commit -m "feat: add frontend-craft-6mo example curriculum"
```

---

### Task 20: Test that both examples validate in CI

**Files:**
- Create: `tests/test_examples.py`

- [ ] **Step 1: Write the test**

Create `tests/test_examples.py`:

```python
"""Each example curriculum must pass the validator with its own ritual_times."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.curriculum_validator import validate

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.mark.parametrize("example", sorted(p.name for p in EXAMPLES_DIR.iterdir()
                                            if p.is_dir()))
def test_example_validates(example: str) -> None:
    cdir = EXAMPLES_DIR / example
    manifest = yaml.safe_load((cdir / "manifest.yaml").read_text())
    required = manifest.get("ritual_times_required") or []
    fake_ritual_times = {name: "06:00" for name in required}
    validate(cdir, ritual_times=fake_ritual_times)
```

- [ ] **Step 2: Run test**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest tests/test_examples.py -v
```

Expected: 2 PASSED (one per example).

- [ ] **Step 3: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add tests/test_examples.py
git commit -m "test: validate each example curriculum in CI"
```

---

### Task 21: Update README.md with "Fork it for your own curriculum" section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README**

```bash
cd /Users/sauravsuresh/long-way-engine
head -60 README.md
```

- [ ] **Step 2: Append a new section**

Open `README.md`. Append at the end (or insert before any existing "Contributing" / "License" sections):

```markdown
## Fork it for your own curriculum

This repo runs my 39-month "long way" plan, but the engine is generic.
Forkers can replace `curriculum/` with their own bundle. See
[`AGENTS.md`](./AGENTS.md) for the full schema and a recommended
interview protocol you can run with an AI coding agent.

Two starter bundles in [`examples/`](./examples):

- `examples/ml-engineer-12mo/` — 12-month ML engineer path
- `examples/frontend-craft-6mo/` — 6-month frontend deep-dive

To use one: copy it to `curriculum/`, edit `config.yaml`'s
`curriculum_dir` if you put it elsewhere, then run
`python -m src.main --dry-run` to see what fires today.
```

- [ ] **Step 3: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git add README.md
git commit -m "docs: add fork-it section pointing at AGENTS.md and examples"
```

---

## Phase H — Cleanup

### Task 22: Delete the one-time migration script

**Files:**
- Delete: `scripts/migrate_syllabus.py`

- [ ] **Step 1: Remove the script**

```bash
cd /Users/sauravsuresh/long-way-engine
git rm scripts/migrate_syllabus.py
```

If `scripts/` is now empty, also:

```bash
cd /Users/sauravsuresh/long-way-engine
rmdir scripts 2>/dev/null || true
```

- [ ] **Step 2: Commit**

```bash
cd /Users/sauravsuresh/long-way-engine
git commit -m "chore: remove one-time syllabus migration script"
```

---

### Task 23: Final integration check

- [ ] **Step 1: Run the entire test suite**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m pytest -q
```

Expected: all green. Goldens still match.

- [ ] **Step 2: Run a live dry-run**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m src.main --dry-run --date 2026-05-22 2>&1 | tail -40
```

Expected: same dry-run output as before the refactor. Dashboard renders with "Month X of 39", "Module N of 23", correct phase labels.

- [ ] **Step 3: Run a dry-run for today**

```bash
cd /Users/sauravsuresh/long-way-engine
python -m src.main --dry-run --date $(date +%Y-%m-%d) 2>&1 | tail -40
```

Expected: today's task set fires correctly.

- [ ] **Step 4: Quick git status check**

```bash
cd /Users/sauravsuresh/long-way-engine
git status
git log --oneline -25
```

Expected: clean working tree. Commit history reads as a coherent refactor.

---

## Self-review notes

**Spec coverage check:**

- ✅ Move all forker-editable content into `curriculum/` — Tasks 4, 5
- ✅ `curriculum/syllabus.yaml` (phases, books, primary_book_by_month, modules) — Tasks 6, 7
- ✅ `curriculum/manifest.yaml` — Task 8
- ✅ `curriculum_dir` config key — Task 9
- ✅ `Syllabus` dataclass + `load_syllabus()` — Task 10
- ✅ All 10 validator rules (incl. unique IDs, phase contiguity) — Task 11
- ✅ Validator wired into main.py startup — Task 12
- ✅ `current_book(month, syllabus)` migration — Task 13
- ✅ Dashboard derives counts from Syllabus — Task 15
- ✅ Regex parser + dict deleted — Task 16
- ✅ AGENTS.md with schema + interview protocol — Task 17
- ✅ Two example curricula — Tasks 18, 19
- ✅ Examples validated in CI — Task 20
- ✅ README fork section — Task 21
- ✅ Golden-output acceptance test — Tasks 1, 2, 3 (and re-run at each phase)
- ✅ Owner's state.yaml + cache untouched — preserved by golden test gate

**Type/signature consistency:**

- `current_book(month, syllabus)` — added with `syllabus=None` default in Task 10, made mandatory in Task 16
- `load_templates(paths: list[Path])` — new signature in Task 4
- `resolve_variables(template, state, config, today, syllabus=None)` — new kwarg in Task 13
- `render_dashboard(..., syllabus=None)` — new kwarg in Task 15
- `Syllabus` / `Phase` / `Module` / `Book` dataclass field names consistent across all tasks (Book retains `start_month`/`end_month`, Phase uses `months: tuple`, Module uses `phase: int`)

**Placeholder scan:** no TBD/TODO/handwave content. Every code-changing step has the complete code.
