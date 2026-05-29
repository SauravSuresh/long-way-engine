# Multi-syllabus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class support for running N syllabuses concurrently from one repo, with per-syllabus state / Todoist project / streak / pause / dashboard card, plus a local timetable visualizer and one-shot migration script.

**Architecture:** Top-level `config.yaml` declares a `priority_order` list and a `syllabuses` map; each entry points at a `curricula/<name>/` bundle, a `state/<name>.yaml` slice, and a Todoist project. A separate `state/shared.yaml` carries user-life-wide fields (timezone, manual_counters, notes). The engine loop iterates the enabled syllabuses in priority order; existing modules (`scheduler`, `templates`, `todoist`, `cache`, `state_review`, `state_mutations`, `reflections`, `streaks`, `dashboard`) are refactored to take an explicit syllabus context. A migration script splits the existing `state.yaml` and renames `curriculum/` → `curricula/long-way/` byte-for-byte safely; a visualizer prints the resolved weekly timetable and flags slot collisions.

**Tech Stack:** Python 3.11, PyYAML, pytest, dataclasses, pathlib. No new dependencies.

**Spec:** [`docs/superpowers/specs/2026-05-28-multi-syllabus-design.md`](../specs/2026-05-28-multi-syllabus-design.md)

---

## Task ordering rationale

Tasks 1–4 add new types and a migration script without disturbing existing engine paths (parallel implementation). Task 5 runs the migration on the repo itself, after which the new file shapes exist. Tasks 6–13 swap engine call sites from the old single-syllabus types to the new per-syllabus context, one module at a time, with the test suite green at the end of each task. Tasks 14–16 are tooling, golden-test retrofit, and docs.

If at any task an existing test fails because it was written against single-syllabus assumptions, update the test in the same commit; if a *golden* fixture fails, do not edit it yet — it will be retrofitted en bloc in Task 15.

---

## Task 1: SharedState + SyllabusState dataclasses and loaders

**Files:**
- Modify: `src/state.py`
- Test: `tests/test_state.py` (existing), plus new file `tests/test_shared_state.py`

The current `State` dataclass conflates user-life-wide fields (timezone, manual_counters, notes) and per-syllabus fields (current_module, current_book, etc.). Split into `SharedState` and `SyllabusState`. Keep the old `State` and its loader temporarily as a thin facade that composes the two — Task 12 removes it.

- [ ] **Step 1: Write the failing test for SharedState loading**

```python
# tests/test_shared_state.py
from pathlib import Path
from zoneinfo import ZoneInfo

from src.state import SharedState, load_shared_state


def test_load_shared_state_basic(tmp_path: Path):
    p = tmp_path / "shared.yaml"
    p.write_text(
        "timezone: Asia/Kolkata\n"
        "manual_counters:\n"
        "  anki_card_count: 42\n"
        "  prs_opened: 3\n"
        "  traces_completed: 1\n"
        "  lineage_detours_done: []\n"
        "notes: |\n"
        "  hello\n"
    )
    s = load_shared_state(p)
    assert isinstance(s, SharedState)
    assert s.timezone == ZoneInfo("Asia/Kolkata")
    assert s.manual_counters["anki_card_count"] == 42
    assert s.manual_counters["prs_opened"] == 3
    assert s.notes.strip() == "hello"


def test_load_shared_state_defaults(tmp_path: Path):
    p = tmp_path / "shared.yaml"
    p.write_text("timezone: UTC\n")
    s = load_shared_state(p)
    assert s.manual_counters == {}
    assert s.notes == ""


def test_load_shared_state_missing_file(tmp_path: Path):
    import pytest

    p = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError):
        load_shared_state(p)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_shared_state.py -v`
Expected: FAIL with `ImportError: cannot import name 'SharedState'`.

- [ ] **Step 3: Implement SharedState + loader in `src/state.py`**

Add near the top of `src/state.py`, before the existing `State`:

```python
@dataclass
class SharedState:
    timezone: ZoneInfo
    manual_counters: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


def load_shared_state(path: Path) -> SharedState:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    tz_str = str(raw.get("timezone", "UTC"))
    return SharedState(
        timezone=ZoneInfo(tz_str),
        manual_counters=dict(raw.get("manual_counters") or {}),
        notes=str(raw.get("notes", "") or ""),
    )
```

- [ ] **Step 4: Run the SharedState tests, expect pass**

Run: `pytest tests/test_shared_state.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Write the failing tests for SyllabusState loading**

Add to a new file `tests/test_syllabus_state.py`:

```python
from datetime import date
from pathlib import Path

from src.state import SyllabusState, load_syllabus_state


YAML = """
start_date: 2026-05-05
phase: 1
month: 1
current_module: 1
current_book: "Computer Systems: A Programmer's Perspective"
completed_modules: []
books_state:
  Computer Systems\\: A Programmer's Perspective: current
learning_tracks:
  Courses:
    "boot.dev": current
paused: false
paused_since: null
pause_history: []
"""


def test_load_syllabus_state_basic(tmp_path: Path):
    p = tmp_path / "long-way.yaml"
    p.write_text(YAML)
    s = load_syllabus_state(p)
    assert isinstance(s, SyllabusState)
    assert s.start_date == date(2026, 5, 5)
    assert s.phase == 1
    assert s.current_module == 1
    assert s.current_book.startswith("Computer Systems")
    assert s.paused is False
    assert s.learning_tracks["Courses"]["boot.dev"] == "current"
    assert s.books_state["Computer Systems: A Programmer's Perspective"] == "current"


def test_load_syllabus_state_missing_required(tmp_path: Path):
    import pytest

    p = tmp_path / "bad.yaml"
    p.write_text("phase: 1\n")  # missing start_date, current_module, current_book
    with pytest.raises(KeyError):
        load_syllabus_state(p)
```

- [ ] **Step 6: Verify failure**

Run: `pytest tests/test_syllabus_state.py -v`
Expected: FAIL with `ImportError: cannot import name 'SyllabusState'`.

- [ ] **Step 7: Implement SyllabusState + loader in `src/state.py`**

Add (above the existing `State`):

```python
@dataclass
class SyllabusState:
    start_date: date
    phase: int
    month: int
    current_module: int
    current_book: str
    completed_modules: list[int] = field(default_factory=list)
    active_branches: list[str] = field(default_factory=list)
    paused: bool = False
    paused_since: date | None = None
    paused_until: date | None = None
    pause_history: list[PauseInterval] = field(default_factory=list)
    books_state: dict[str, str] = field(default_factory=dict)
    learning_tracks: dict[str, dict[str, str]] = field(default_factory=dict)


def load_syllabus_state(path: Path) -> SyllabusState:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    # Required keys — raise KeyError on absence.
    start_date_raw = raw["start_date"]
    current_module = raw["current_module"]
    current_book = raw["current_book"]
    pause_history_raw = raw.get("pause_history") or []
    pause_history = [
        PauseInterval(
            start=pi["start"],
            end=pi["end"],
            reason=str(pi.get("reason", "")),
        )
        for pi in pause_history_raw
    ]
    return SyllabusState(
        start_date=_coerce_date(start_date_raw),
        phase=int(raw.get("phase", 1)),
        month=int(raw.get("month", 1)),
        current_module=int(current_module),
        current_book=str(current_book),
        completed_modules=list(raw.get("completed_modules") or []),
        active_branches=list(raw.get("active_branches") or []),
        paused=bool(raw.get("paused", False)),
        paused_since=_coerce_optional_date(raw.get("paused_since")),
        paused_until=_coerce_optional_date(raw.get("paused_until")),
        pause_history=pause_history,
        books_state=dict(raw.get("books_state") or {}),
        learning_tracks=dict(raw.get("learning_tracks") or {}),
    )


def _coerce_date(v):
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _coerce_optional_date(v):
    if v is None or v == "":
        return None
    return _coerce_date(v)
```

If `PauseInterval`'s `start`/`end` fields are typed as `date` in the existing dataclass, ensure `_coerce_date` is applied. Look at the existing `State` loader for the date-coercion idiom and mirror it exactly.

- [ ] **Step 8: Verify SyllabusState tests pass and the existing state suite still passes**

Run: `pytest tests/test_shared_state.py tests/test_syllabus_state.py tests/test_state.py -v`
Expected: PASS for the new tests; existing `tests/test_state.py` unchanged (still passes — `State` and `load_state` are untouched).

- [ ] **Step 9: Commit**

```bash
git add src/state.py tests/test_shared_state.py tests/test_syllabus_state.py
git commit -m "feat(state): add SharedState and SyllabusState dataclasses + loaders"
```

---

## Task 2: Multi-syllabus Config dataclass + loader with override merging and slot-collision detection

**Files:**
- Modify: `src/config.py`
- Test: `tests/test_config.py` (extend) plus `tests/test_multi_syllabus_config.py` (new)

Add a new `MultiSyllabusConfig` dataclass loaded from the new `config.yaml` shape. Keep the old `Config` and `load_config` in place for now — Task 12 removes them.

- [ ] **Step 1: Write the failing tests for multi-syllabus config loading**

```python
# tests/test_multi_syllabus_config.py
from pathlib import Path

import pytest

from src.config import (
    MultiSyllabusConfig,
    SyllabusEntry,
    SlotCollisionError,
    load_multi_syllabus_config,
)


BASE_YAML = """
ritual_times:
  morning_reading: "06:00"
  anki: "08:30"
  evening_hands_on: "19:00"
  weekly_state_review: "10:00"
priority_order:
  - long-way
syllabuses:
  long-way:
    path: curricula/long-way
    todoist_project_id: "111"
    state_file: state/long-way.yaml
    enabled: true
sunday_off: true
dashboard:
  github_username: "foo"
  repo_name: "long-way-engine"
"""


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content)
    env = tmp_path / ".env"
    env.write_text("TODOIST_TOKEN=abc\n")
    return p


def test_load_single_syllabus(tmp_path: Path):
    p = _write(tmp_path, BASE_YAML)
    cfg = load_multi_syllabus_config(p, tmp_path / ".env")
    assert isinstance(cfg, MultiSyllabusConfig)
    assert cfg.priority_order == ["long-way"]
    assert "long-way" in cfg.syllabuses
    sy = cfg.syllabuses["long-way"]
    assert isinstance(sy, SyllabusEntry)
    assert sy.todoist_project_id == "111"
    assert sy.enabled is True
    # Effective ritual_times = top-level when no override.
    assert sy.ritual_times["morning_reading"] == "06:00"


def test_per_syllabus_override_merges_with_top_level(tmp_path: Path):
    yaml = BASE_YAML + """\
"""
    yaml = BASE_YAML.replace(
        "    enabled: true\n",
        "    enabled: true\n    ritual_times:\n      morning_reading: \"13:00\"\n",
    )
    p = _write(tmp_path, yaml)
    cfg = load_multi_syllabus_config(p, tmp_path / ".env")
    sy = cfg.syllabuses["long-way"]
    assert sy.ritual_times["morning_reading"] == "13:00"  # overridden
    assert sy.ritual_times["anki"] == "08:30"             # inherited


def test_priority_order_must_match_enabled_set(tmp_path: Path):
    # priority_order names a syllabus that isn't declared.
    yaml = BASE_YAML.replace(
        "  - long-way\n",
        "  - long-way\n  - ghost\n",
    )
    p = _write(tmp_path, yaml)
    with pytest.raises(ValueError, match="priority_order"):
        load_multi_syllabus_config(p, tmp_path / ".env")


def test_slot_collision_errors(tmp_path: Path):
    # Two syllabuses both at morning_reading 06:00, neither allows overlap.
    yaml = (BASE_YAML
        .replace("  - long-way\n", "  - long-way\n  - job-readiness\n")
        .replace(
            "  long-way:\n    path: curricula/long-way\n    todoist_project_id: \"111\"\n    state_file: state/long-way.yaml\n    enabled: true\n",
            "  long-way:\n    path: curricula/long-way\n    todoist_project_id: \"111\"\n    state_file: state/long-way.yaml\n    enabled: true\n"
            "  job-readiness:\n    path: curricula/job-readiness\n    todoist_project_id: \"222\"\n    state_file: state/job-readiness.yaml\n    enabled: true\n",
        )
    )
    p = _write(tmp_path, yaml)
    with pytest.raises(SlotCollisionError):
        load_multi_syllabus_config(p, tmp_path / ".env")


def test_slot_collision_suppressed_by_allow_slot_overlap(tmp_path: Path):
    yaml = (BASE_YAML
        .replace("  - long-way\n", "  - long-way\n  - job-readiness\n")
        .replace(
            "    enabled: true\n",
            "    enabled: true\n    allow_slot_overlap: true\n",
            1,  # only on the first occurrence (long-way)
        )
        .replace(
            "  long-way:\n",
            "  job-readiness:\n    path: curricula/job-readiness\n    todoist_project_id: \"222\"\n    state_file: state/job-readiness.yaml\n    enabled: true\n  long-way:\n",
        )
    )
    p = _write(tmp_path, yaml)
    cfg = load_multi_syllabus_config(p, tmp_path / ".env")  # must not raise
    assert "job-readiness" in cfg.syllabuses


def test_disabled_syllabus_skipped_for_collisions(tmp_path: Path):
    yaml = (BASE_YAML
        .replace("  - long-way\n", "  - long-way\n")  # priority lists only long-way
        .replace(
            "  long-way:\n",
            "  job-readiness:\n    path: curricula/job-readiness\n    todoist_project_id: \"222\"\n    state_file: state/job-readiness.yaml\n    enabled: false\n  long-way:\n",
        )
    )
    p = _write(tmp_path, yaml)
    cfg = load_multi_syllabus_config(p, tmp_path / ".env")  # must not raise
    assert cfg.syllabuses["job-readiness"].enabled is False
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_multi_syllabus_config.py -v`
Expected: FAIL with `ImportError` on `MultiSyllabusConfig` / `SyllabusEntry` / `SlotCollisionError`.

- [ ] **Step 3: Implement in `src/config.py`**

Add (after existing dataclasses):

```python
@dataclass
class SyllabusEntry:
    key: str
    path: Path
    todoist_project_id: str
    state_file: Path
    enabled: bool
    ritual_times: dict[str, str]
    allow_slot_overlap: bool = False


@dataclass
class MultiSyllabusConfig:
    ritual_times: dict[str, str]
    priority_order: list[str]
    syllabuses: dict[str, SyllabusEntry]
    sunday_off: bool
    pair_day: str | None
    dashboard: DashboardConfig
    todoist_token: str


class SlotCollisionError(ValueError):
    """Two enabled syllabuses claim the same (ritual_times_key, clock_time)."""


def load_multi_syllabus_config(yaml_path: Path, env_path: Path) -> MultiSyllabusConfig:
    with yaml_path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    top_rt = dict(raw.get("ritual_times") or {})
    priority_order = list(raw.get("priority_order") or [])
    syllabuses_raw = dict(raw.get("syllabuses") or {})

    syllabuses: dict[str, SyllabusEntry] = {}
    for key, block in syllabuses_raw.items():
        rt = dict(top_rt)
        rt.update(dict(block.get("ritual_times") or {}))
        syllabuses[key] = SyllabusEntry(
            key=key,
            path=Path(block["path"]),
            todoist_project_id=str(block["todoist_project_id"]),
            state_file=Path(block["state_file"]),
            enabled=bool(block.get("enabled", True)),
            ritual_times=rt,
            allow_slot_overlap=bool(block.get("allow_slot_overlap", False)),
        )

    # priority_order must equal the set of enabled syllabuses.
    enabled_keys = {k for k, s in syllabuses.items() if s.enabled}
    if set(priority_order) != enabled_keys:
        raise ValueError(
            f"priority_order {sorted(priority_order)} must equal the set of enabled "
            f"syllabuses {sorted(enabled_keys)}"
        )

    # Slot-collision check: (slot, clock_time) unique across enabled syllabuses
    # unless at least one party has allow_slot_overlap=True.
    seen: dict[tuple[str, str], str] = {}
    for key in priority_order:
        sy = syllabuses[key]
        for slot, when in sy.ritual_times.items():
            existing = seen.get((slot, when))
            if existing is None:
                seen[(slot, when)] = key
                continue
            other = syllabuses[existing]
            if sy.allow_slot_overlap or other.allow_slot_overlap:
                continue
            raise SlotCollisionError(
                f"slot collision: {existing}:{slot}@{when} and {key}:{slot}@{when} "
                f"— change one clock time or set allow_slot_overlap on one side"
            )

    dashboard_raw = raw["dashboard"]
    dashboard = DashboardConfig(
        github_username=str(dashboard_raw["github_username"]),
        repo_name=str(dashboard_raw["repo_name"]),
    )
    pair_day = raw.get("pair_day")
    if pair_day is not None:
        pair_day = str(pair_day).lower()

    return MultiSyllabusConfig(
        ritual_times=top_rt,
        priority_order=priority_order,
        syllabuses=syllabuses,
        sunday_off=bool(raw.get("sunday_off", True)),
        pair_day=pair_day,
        dashboard=dashboard,
        todoist_token=_read_token(env_path),
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_multi_syllabus_config.py tests/test_config.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_multi_syllabus_config.py
git commit -m "feat(config): add MultiSyllabusConfig loader with override merge + slot-collision detection"
```

---

## Task 3: Cache namespacing by syllabus

**Files:**
- Modify: `src/cache.py`
- Test: `tests/test_cache.py` (extend)

The cache is currently a flat `dict[external_id, record]`. Wrap it under a per-syllabus key. Provide a one-shot migration helper that takes a flat cache and lifts it under a given syllabus key (used by the migration script in Task 4).

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/test_cache.py
from src.cache import (
    NamespacedCache,
    lift_flat_cache_under_syllabus,
    load_namespaced_cache,
    save_namespaced_cache,
)


def test_lift_flat_cache_under_syllabus():
    flat = {"ext-1": {"todoist_id": "100"}, "ext-2": {"todoist_id": "101"}}
    namespaced = lift_flat_cache_under_syllabus(flat, "long-way")
    assert namespaced == {"long-way": flat}


def test_load_namespaced_cache_existing(tmp_path):
    import json
    p = tmp_path / "task_cache.json"
    p.write_text(json.dumps({"long-way": {"ext-1": {"todoist_id": "100"}}}))
    nc = load_namespaced_cache(p)
    assert isinstance(nc, NamespacedCache)
    assert nc.get("long-way", "ext-1") == {"todoist_id": "100"}
    assert nc.get("long-way", "ext-missing") is None
    assert nc.get("missing-syllabus", "ext-1") is None


def test_load_namespaced_cache_flat_legacy(tmp_path):
    """Legacy flat cache (no syllabus layer) is detected and rejected — migrate first."""
    import json
    import pytest
    p = tmp_path / "task_cache.json"
    p.write_text(json.dumps({"ext-1": {"todoist_id": "100"}}))
    with pytest.raises(ValueError, match="legacy flat cache"):
        load_namespaced_cache(p)


def test_save_and_round_trip(tmp_path):
    p = tmp_path / "task_cache.json"
    nc = NamespacedCache(data={"long-way": {"ext-1": {"todoist_id": "100"}}})
    nc.set("long-way", "ext-2", {"todoist_id": "101"})
    save_namespaced_cache(p, nc)
    nc2 = load_namespaced_cache(p)
    assert nc2.get("long-way", "ext-1") == {"todoist_id": "100"}
    assert nc2.get("long-way", "ext-2") == {"todoist_id": "101"}


def test_load_missing_file_returns_empty(tmp_path):
    nc = load_namespaced_cache(tmp_path / "absent.json")
    assert nc.get("any", "ext-1") is None
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_cache.py -v`
Expected: FAIL on missing symbols.

- [ ] **Step 3: Implement in `src/cache.py`**

Add (do not remove the existing `load_cache`/`save_cache` — Task 12 retires them):

```python
@dataclass
class NamespacedCache:
    data: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)

    def get(self, syllabus: str, external_id: str) -> dict[str, Any] | None:
        return self.data.get(syllabus, {}).get(external_id)

    def set(self, syllabus: str, external_id: str, record: dict[str, Any]) -> None:
        self.data.setdefault(syllabus, {})[external_id] = record

    def for_syllabus(self, syllabus: str) -> dict[str, dict[str, Any]]:
        return self.data.setdefault(syllabus, {})


def _looks_like_flat_cache(d: dict[str, Any]) -> bool:
    """A flat (legacy) cache has values that are records (dicts with 'todoist_id')
    rather than per-syllabus sub-dicts.
    """
    if not d:
        return False
    for v in d.values():
        if isinstance(v, dict) and "todoist_id" in v:
            return True
        if isinstance(v, dict) and all(isinstance(vv, dict) and "todoist_id" not in vv for vv in v.values()):
            return False
    return False


def load_namespaced_cache(path: Path) -> NamespacedCache:
    if not path.exists():
        return NamespacedCache()
    with path.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return NamespacedCache()
    if not isinstance(data, dict):
        return NamespacedCache()
    if _looks_like_flat_cache(data):
        raise ValueError(
            "legacy flat cache detected; run scripts/migrate_to_multi_syllabus.py first"
        )
    return NamespacedCache(data={k: dict(v) for k, v in data.items()})


def save_namespaced_cache(path: Path, nc: NamespacedCache) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(nc.data, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def lift_flat_cache_under_syllabus(
    flat: dict[str, dict[str, Any]], syllabus_key: str
) -> dict[str, dict[str, dict[str, Any]]]:
    return {syllabus_key: dict(flat)}
```

Add `from dataclasses import dataclass, field` and `import json` at top if not already imported.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_cache.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/cache.py tests/test_cache.py
git commit -m "feat(cache): add NamespacedCache + legacy flat-cache detector"
```

---

## Task 4: Migration script `scripts/migrate_to_multi_syllabus.py`

**Files:**
- Create: `scripts/migrate_to_multi_syllabus.py`
- Test: `tests/test_migrate_to_multi_syllabus.py` (new)

The script reads the *current* repo layout (`curriculum/`, `state.yaml`, `config.yaml`, `.task_cache.json`, `.completion_cache.json`, `reflections/`) and produces the new layout. Idempotent: if the new layout already exists and the old does not, it exits 0 with a "nothing to do" message.

Behavior:
1. Choose syllabus key from CLI flag (`--name long-way`, default `long-way`).
2. Move `curriculum/` → `curricula/<name>/` via `git mv`-style operations (use `shutil.move` if git not present in test fixtures; production migration uses `git mv` in the README docs).
3. Split `state.yaml` into `state/shared.yaml` + `state/<name>.yaml`.
4. Rewrite `config.yaml` to the new shape.
5. Wrap `.task_cache.json` + `.completion_cache.json` under `<name>` top-level key.
6. Move `reflections/<file>` → `reflections/<name>/<cadence>/<file>` (cadence inferred from filename — weekly: `YYYY-W##`, monthly: `YYYY-MM`, quarterly: `YYYY-Q#`, annual: `YYYY`).
7. Print a summary and exit 0; on any error, leave partial state in place but emit a clear rollback hint.

- [ ] **Step 1: Write failing tests covering the core split-and-rewrite logic**

```python
# tests/test_migrate_to_multi_syllabus.py
from pathlib import Path
import json
import yaml

from scripts.migrate_to_multi_syllabus import (
    split_state_yaml,
    rewrite_config_yaml,
    wrap_cache,
    classify_reflection,
)


def test_split_state_yaml_basic():
    old = {
        "start_date": "2026-05-05",
        "timezone": "Asia/Kolkata",
        "phase": 1,
        "month": 1,
        "current_module": 7,
        "current_book": "CS:APP",
        "completed_modules": [1, 2],
        "books_state": {"CS:APP": "current"},
        "learning_tracks": {"Courses": {"boot.dev": "current"}},
        "paused": False,
        "paused_since": None,
        "pause_history": [],
        "manual_counters": {"anki_card_count": 99, "prs_opened": 3},
        "notes": "hello",
    }
    shared, syllabus = split_state_yaml(old)
    assert shared == {
        "timezone": "Asia/Kolkata",
        "manual_counters": {"anki_card_count": 99, "prs_opened": 3},
        "notes": "hello",
    }
    assert syllabus == {
        "start_date": "2026-05-05",
        "phase": 1,
        "month": 1,
        "current_module": 7,
        "current_book": "CS:APP",
        "completed_modules": [1, 2],
        "books_state": {"CS:APP": "current"},
        "learning_tracks": {"Courses": {"boot.dev": "current"}},
        "paused": False,
        "paused_since": None,
        "pause_history": [],
    }


def test_rewrite_config_yaml_basic():
    old = {
        "todoist": {"project_id": "ABC", "labels": {"daily": "daily-ritual"}},
        "ritual_times": {"morning_reading": "06:00", "anki": "08:30"},
        "sunday_off": True,
        "pair_day": "thursday",
        "curriculum_dir": "curriculum",
        "dashboard": {"github_username": "foo", "repo_name": "bar"},
    }
    new = rewrite_config_yaml(old, syllabus_name="long-way")
    assert new["priority_order"] == ["long-way"]
    assert new["syllabuses"]["long-way"] == {
        "path": "curricula/long-way",
        "todoist_project_id": "ABC",
        "state_file": "state/long-way.yaml",
        "enabled": True,
    }
    # Top-level ritual_times preserved.
    assert new["ritual_times"]["morning_reading"] == "06:00"
    # dashboard, pair_day, sunday_off preserved.
    assert new["dashboard"] == {"github_username": "foo", "repo_name": "bar"}
    assert new["pair_day"] == "thursday"
    assert new["sunday_off"] is True
    # Old top-level keys gone.
    assert "todoist" not in new
    assert "curriculum_dir" not in new


def test_wrap_cache_namespaces():
    flat = {"ext-1": {"todoist_id": "100"}}
    wrapped = wrap_cache(flat, "long-way")
    assert wrapped == {"long-way": {"ext-1": {"todoist_id": "100"}}}


def test_wrap_cache_idempotent_if_already_wrapped():
    already = {"long-way": {"ext-1": {"todoist_id": "100"}}}
    assert wrap_cache(already, "long-way") == already


def test_classify_reflection_weekly():
    assert classify_reflection("2026-W21.md") == "weekly"


def test_classify_reflection_monthly():
    assert classify_reflection("2026-04.md") == "monthly"


def test_classify_reflection_quarterly():
    assert classify_reflection("2026-Q2.md") == "quarterly"


def test_classify_reflection_annual():
    assert classify_reflection("2026.md") == "annual"


def test_classify_reflection_unknown_returns_none():
    assert classify_reflection("notes.md") is None
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_migrate_to_multi_syllabus.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `scripts/migrate_to_multi_syllabus.py`**

```python
"""One-shot migration: single-syllabus repo -> multi-syllabus repo.

Idempotent. Run with --dry-run to see what would change without writing.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml


SHARED_KEYS = {"timezone", "manual_counters", "notes"}
SYLLABUS_KEYS = {
    "start_date",
    "phase",
    "month",
    "current_module",
    "current_book",
    "completed_modules",
    "active_branches",
    "books_state",
    "learning_tracks",
    "paused",
    "paused_since",
    "paused_until",
    "pause_history",
}


def split_state_yaml(old: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    shared = {k: old[k] for k in SHARED_KEYS if k in old}
    syllabus = {k: old[k] for k in SYLLABUS_KEYS if k in old}
    return shared, syllabus


def rewrite_config_yaml(old: dict[str, Any], *, syllabus_name: str) -> dict[str, Any]:
    new: dict[str, Any] = {}
    if "ritual_times" in old:
        new["ritual_times"] = dict(old["ritual_times"])
    new["priority_order"] = [syllabus_name]
    new["syllabuses"] = {
        syllabus_name: {
            "path": f"curricula/{syllabus_name}",
            "todoist_project_id": str(old["todoist"]["project_id"]),
            "state_file": f"state/{syllabus_name}.yaml",
            "enabled": True,
        }
    }
    if "sunday_off" in old:
        new["sunday_off"] = bool(old["sunday_off"])
    if "pair_day" in old:
        new["pair_day"] = old["pair_day"]
    if "dashboard" in old:
        new["dashboard"] = dict(old["dashboard"])
    return new


def wrap_cache(content: dict[str, Any], syllabus_name: str) -> dict[str, Any]:
    if not content:
        return {}
    # Already wrapped? Heuristic: the top-level value is itself a dict of records.
    first_val = next(iter(content.values()))
    if (
        isinstance(first_val, dict)
        and first_val
        and isinstance(next(iter(first_val.values()), {}), dict)
        and "todoist_id" not in first_val
    ):
        return content
    return {syllabus_name: dict(content)}


_WEEKLY = re.compile(r"^\d{4}-W\d{2}\.md$")
_MONTHLY = re.compile(r"^\d{4}-\d{2}\.md$")
_QUARTERLY = re.compile(r"^\d{4}-Q[1-4]\.md$")
_ANNUAL = re.compile(r"^\d{4}\.md$")


def classify_reflection(name: str) -> str | None:
    if _WEEKLY.match(name):
        return "weekly"
    if _MONTHLY.match(name):
        return "monthly"
    if _QUARTERLY.match(name):
        return "quarterly"
    if _ANNUAL.match(name):
        return "annual"
    return None


def _read_yaml(p: Path) -> dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_yaml(p: Path, data: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def run_migration(repo_root: Path, *, syllabus_name: str, dry_run: bool) -> int:
    plan: list[str] = []

    old_curriculum = repo_root / "curriculum"
    new_curriculum = repo_root / "curricula" / syllabus_name
    if old_curriculum.exists() and not new_curriculum.exists():
        plan.append(f"move {old_curriculum} -> {new_curriculum}")

    old_state = repo_root / "state.yaml"
    new_shared = repo_root / "state" / "shared.yaml"
    new_syllabus = repo_root / "state" / f"{syllabus_name}.yaml"
    if old_state.exists() and not new_shared.exists():
        plan.append(f"split {old_state} -> {new_shared} + {new_syllabus}")

    old_config = repo_root / "config.yaml"
    if old_config.exists():
        raw = _read_yaml(old_config)
        if "syllabuses" not in raw:
            plan.append(f"rewrite {old_config}")

    for cache_name in (".task_cache.json", ".completion_cache.json"):
        p = repo_root / cache_name
        if not p.exists():
            continue
        content = json.loads(p.read_text() or "{}")
        if content and syllabus_name not in content:
            plan.append(f"wrap {p} under '{syllabus_name}'")

    old_refl = repo_root / "reflections"
    if old_refl.exists():
        for entry in old_refl.iterdir():
            if entry.is_file() and entry.suffix == ".md":
                cadence = classify_reflection(entry.name)
                if cadence:
                    target = old_refl / syllabus_name / cadence / entry.name
                    if not target.exists():
                        plan.append(f"move {entry} -> {target}")

    if not plan:
        print("nothing to do — repo is already migrated")
        return 0

    print("Plan:")
    for step in plan:
        print(f"  {step}")

    if dry_run:
        print("\n--dry-run: no changes made")
        return 0

    # Execute.
    if old_curriculum.exists() and not new_curriculum.exists():
        new_curriculum.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_curriculum), str(new_curriculum))

    if old_state.exists() and not new_shared.exists():
        old = _read_yaml(old_state)
        shared, syllabus = split_state_yaml(old)
        _write_yaml(new_shared, shared)
        _write_yaml(new_syllabus, syllabus)
        old_state.unlink()

    raw = _read_yaml(old_config)
    if "syllabuses" not in raw:
        new_cfg = rewrite_config_yaml(raw, syllabus_name=syllabus_name)
        _write_yaml(old_config, new_cfg)

    for cache_name in (".task_cache.json", ".completion_cache.json"):
        p = repo_root / cache_name
        if not p.exists():
            continue
        content = json.loads(p.read_text() or "{}")
        if content and syllabus_name not in content:
            wrapped = wrap_cache(content, syllabus_name)
            p.write_text(json.dumps(wrapped, indent=2, sort_keys=True) + "\n")

    if old_refl.exists():
        for entry in list(old_refl.iterdir()):
            if entry.is_file() and entry.suffix == ".md":
                cadence = classify_reflection(entry.name)
                if cadence:
                    target = old_refl / syllabus_name / cadence / entry.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(entry), str(target))

    print("\nmigration complete")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Migrate single-syllabus repo to multi-syllabus layout")
    ap.add_argument("--name", default="long-way", help="syllabus key (default: long-way)")
    ap.add_argument("--dry-run", action="store_true", help="show plan without writing")
    ap.add_argument("--repo-root", type=Path, default=Path("."), help="repo root (default: cwd)")
    args = ap.parse_args(argv)
    return run_migration(args.repo_root, syllabus_name=args.name, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
```

Add `scripts/__init__.py` if it doesn't exist (empty file) so the test imports work.

- [ ] **Step 4: Run all migration tests**

Run: `pytest tests/test_migrate_to_multi_syllabus.py -v`
Expected: all pass.

- [ ] **Step 5: Add an end-to-end test that exercises `run_migration` against a fake repo**

Append to `tests/test_migrate_to_multi_syllabus.py`:

```python
def test_run_migration_end_to_end(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "curriculum").mkdir()
    (repo / "curriculum" / "syllabus.yaml").write_text("meta:\n  name: x\n")
    (repo / "state.yaml").write_text(
        "start_date: 2026-05-05\n"
        "timezone: Asia/Kolkata\n"
        "phase: 1\n"
        "month: 1\n"
        "current_module: 1\n"
        "current_book: foo\n"
        "manual_counters:\n  anki_card_count: 0\n"
        "notes: hi\n"
    )
    (repo / "config.yaml").write_text(
        "todoist:\n  project_id: ABC\n"
        "ritual_times:\n  morning_reading: '06:00'\n"
        "sunday_off: true\n"
        "curriculum_dir: curriculum\n"
        "dashboard:\n  github_username: u\n  repo_name: r\n"
    )
    (repo / ".task_cache.json").write_text(json.dumps({"ext-1": {"todoist_id": "100"}}))
    (repo / "reflections").mkdir()
    (repo / "reflections" / "2026-W21.md").write_text("week stub")

    from scripts.migrate_to_multi_syllabus import run_migration
    rc = run_migration(repo, syllabus_name="long-way", dry_run=False)
    assert rc == 0
    assert (repo / "curricula" / "long-way" / "syllabus.yaml").exists()
    assert (repo / "state" / "shared.yaml").exists()
    assert (repo / "state" / "long-way.yaml").exists()
    assert not (repo / "state.yaml").exists()
    new_cfg = yaml.safe_load((repo / "config.yaml").read_text())
    assert new_cfg["priority_order"] == ["long-way"]
    assert new_cfg["syllabuses"]["long-way"]["todoist_project_id"] == "ABC"
    cache = json.loads((repo / ".task_cache.json").read_text())
    assert cache == {"long-way": {"ext-1": {"todoist_id": "100"}}}
    assert (repo / "reflections" / "long-way" / "weekly" / "2026-W21.md").exists()


def test_run_migration_idempotent(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "curricula" / "long-way").mkdir(parents=True)
    (repo / "state").mkdir()
    (repo / "state" / "shared.yaml").write_text("timezone: UTC\n")
    (repo / "state" / "long-way.yaml").write_text("start_date: 2026-05-05\ncurrent_module: 1\ncurrent_book: x\n")
    (repo / "config.yaml").write_text(
        "ritual_times:\n  morning_reading: '06:00'\n"
        "priority_order: [long-way]\n"
        "syllabuses:\n  long-way:\n    path: curricula/long-way\n    todoist_project_id: ABC\n    state_file: state/long-way.yaml\n    enabled: true\n"
        "dashboard:\n  github_username: u\n  repo_name: r\n"
    )
    from scripts.migrate_to_multi_syllabus import run_migration
    rc = run_migration(repo, syllabus_name="long-way", dry_run=False)
    assert rc == 0  # exits cleanly with "nothing to do"
```

- [ ] **Step 6: Run all migration tests**

Run: `pytest tests/test_migrate_to_multi_syllabus.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add scripts/migrate_to_multi_syllabus.py scripts/__init__.py tests/test_migrate_to_multi_syllabus.py
git commit -m "feat(scripts): add migrate_to_multi_syllabus.py with idempotent end-to-end migration"
```

---

## Task 5: Run the migration on the actual repo

This is a one-shot transformation of the repo's working tree. After this task, the rest of the plan operates against the new layout.

- [ ] **Step 1: Stage a dry-run preview**

Run: `python -m scripts.migrate_to_multi_syllabus --dry-run`
Expected: prints a plan listing the file moves and the config rewrite.

- [ ] **Step 2: Execute the migration**

Run: `python -m scripts.migrate_to_multi_syllabus`
Expected: "migration complete".

- [ ] **Step 3: Sanity-check the working tree**

Run:
```bash
ls curricula/long-way/
ls state/
cat config.yaml | head -25
ls reflections/long-way/ 2>/dev/null
```
Expected: `curricula/long-way/{syllabus,manifest,modules}.yaml` etc.; `state/shared.yaml` + `state/long-way.yaml`; new `config.yaml` shape; reflections nested under `long-way/<cadence>/`.

- [ ] **Step 4: Verify the new config loads cleanly**

Run: `python -c "from src.config import load_multi_syllabus_config; from pathlib import Path; print(load_multi_syllabus_config(Path('config.yaml'), Path('.env')))"`
Expected: prints a `MultiSyllabusConfig(...)` repr with one entry for `long-way`. (`.env` may need to be present with a fake token for local runs; using an existing `.env` is fine.)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -x`
Expected: many failures — existing call sites still reference the old `curriculum/` path and the old `state.yaml`. These are addressed in Tasks 6–13. Note: golden-test failures are expected; do not edit them yet.

- [ ] **Step 6: Commit the migrated tree**

```bash
git add -A
git commit -m "chore(repo): run migration to multi-syllabus layout"
```

---

## Task 6: Refactor `src/syllabus.py` to take an explicit syllabus path

**Files:**
- Modify: `src/syllabus.py`
- Test: `tests/test_syllabus.py` (extend)

Current `load_syllabus` takes a path; verify it already accepts an arbitrary directory (it should). Add a thin helper `load_syllabus_for_entry(entry: SyllabusEntry)` that returns the same parsed `Syllabus` from `entry.path`.

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_syllabus.py
from pathlib import Path
from src.config import SyllabusEntry
from src.syllabus import load_syllabus_for_entry


def test_load_syllabus_for_entry_returns_parsed():
    entry = SyllabusEntry(
        key="long-way",
        path=Path("curricula/long-way"),
        todoist_project_id="X",
        state_file=Path("state/long-way.yaml"),
        enabled=True,
        ritual_times={},
    )
    sy = load_syllabus_for_entry(entry)
    assert sy.meta.name  # parsed without error
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_syllabus.py::test_load_syllabus_for_entry_returns_parsed -v`
Expected: FAIL on import.

- [ ] **Step 3: Implement**

Add to `src/syllabus.py`:

```python
def load_syllabus_for_entry(entry: "SyllabusEntry") -> "Syllabus":
    from src.config import SyllabusEntry  # local to avoid circular import at module top
    assert isinstance(entry, SyllabusEntry)
    return load_syllabus(entry.path)
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_syllabus.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/syllabus.py tests/test_syllabus.py
git commit -m "feat(syllabus): add load_syllabus_for_entry helper"
```

---

## Task 7: Refactor `src/scheduler.py` to carry syllabus_key on emitted tasks

**Files:**
- Modify: `src/scheduler.py`, `src/templates.py` (only the ResolvedTemplate dataclass), `src/todoist.py`
- Test: `tests/test_scheduler.py` (extend)

Emitted tasks need to carry a `syllabus_key` so downstream consumers (Todoist client, state-mutation parser) can route correctly.

- [ ] **Step 1: Inspect `ResolvedTemplate`**

Run: `grep -n "class ResolvedTemplate" src/templates.py`
Expected: a dataclass; note the existing fields.

- [ ] **Step 2: Write the failing test**

```python
# Append to tests/test_scheduler.py
def test_resolved_template_carries_syllabus_key():
    from src.templates import ResolvedTemplate
    # Construct one; the field must exist on the class.
    fields = {f.name for f in __import__("dataclasses").fields(ResolvedTemplate)}
    assert "syllabus_key" in fields
```

- [ ] **Step 3: Verify failure**

Run: `pytest tests/test_scheduler.py::test_resolved_template_carries_syllabus_key -v`
Expected: FAIL.

- [ ] **Step 4: Add `syllabus_key` to `ResolvedTemplate`**

In `src/templates.py`, find the `ResolvedTemplate` dataclass and add:

```python
syllabus_key: str = ""  # set by the scheduler when a syllabus context is provided
```

- [ ] **Step 5: Propagate `syllabus_key` from the scheduler**

In `src/scheduler.py`, find where `ResolvedTemplate` instances are constructed inside `should_create_today` (or wherever resolution happens) and accept a `syllabus_key` argument; set it on every resolved template. Signature:

```python
def should_create_today(
    *,
    template,
    today,
    state,
    syllabus,
    config,
    syllabus_key: str = "",
) -> ResolvedTemplate | None:
    ...
    return ResolvedTemplate(..., syllabus_key=syllabus_key)
```

Update call sites in `src/main.py` and any tests to pass `syllabus_key`. For now, default to the empty string; Task 12 fills it from the loop context.

- [ ] **Step 6: Verify the targeted test and the full scheduler suite pass**

Run: `pytest tests/test_scheduler.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/templates.py src/scheduler.py tests/test_scheduler.py
git commit -m "feat(scheduler): thread syllabus_key through ResolvedTemplate"
```

---

## Task 8: Refactor `src/todoist.py` to route by syllabus_key

**Files:**
- Modify: `src/todoist.py`
- Test: `tests/test_todoist.py` (extend)

The Todoist client currently takes a single `project_id` at construction. Change `TodoistClient.create()` (or equivalent) to accept either an explicit `project_id` argument per call, or look it up from a `syllabus_key -> project_id` map provided at construction.

Pick the simpler API: a `project_router: dict[str, str]` passed to the constructor; `create()` takes the resolved template and reads `project_router[template.syllabus_key]`. Also add a `syllabus:<key>` label to every created task.

- [ ] **Step 1: Write failing test**

```python
# Append to tests/test_todoist.py
def test_todoist_client_routes_by_syllabus_key(monkeypatch):
    captured = {}

    class FakeSession:
        def post(self, url, json, headers, timeout):
            captured["json"] = json
            class R:
                status_code = 200
                def json(self_inner):
                    return {"id": "999"}
            return R()

    from src.todoist import TodoistClient
    client = TodoistClient(
        token="t",
        project_router={"long-way": "PROJ-A", "job-readiness": "PROJ-B"},
        session=FakeSession(),
    )
    from src.templates import ResolvedTemplate
    rt = ResolvedTemplate(
        id="x", external_id="ext-1", content="hi", description="",
        labels=["daily-ritual"], due_string="today",
        syllabus_key="job-readiness",
    )
    client.create(rt)
    assert captured["json"]["project_id"] == "PROJ-B"
    assert "syllabus:job-readiness" in captured["json"]["labels"]
```

(Adjust `ResolvedTemplate` field set to match your actual dataclass; only `syllabus_key` is new.)

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_todoist.py::test_todoist_client_routes_by_syllabus_key -v`
Expected: FAIL.

- [ ] **Step 3: Refactor `TodoistClient.__init__` and `.create()`**

In `src/todoist.py`, replace the single `project_id` constructor parameter with a `project_router: dict[str, str]`. In `create()`, look up `self._project_router[template.syllabus_key]` and add `f"syllabus:{template.syllabus_key}"` to the labels list (only if `syllabus_key` is non-empty).

Update all call sites in `src/main.py` to build a `project_router` from `MultiSyllabusConfig.syllabuses[key].todoist_project_id`.

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_todoist.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/todoist.py tests/test_todoist.py src/main.py
git commit -m "feat(todoist): route create() by syllabus_key + tag with syllabus:<key> label"
```

---

## Task 9: Refactor `src/state_review.py` + `src/state_mutations.py` per syllabus

**Files:**
- Modify: `src/state_review.py`, `src/state_mutations.py`
- Test: `tests/test_state_review.py`, `tests/test_state_mutations.py` (extend)

Each enabled syllabus now produces its own weekly state-review task. Each state-review Todoist task carries the `syllabus:<key>` label (from Task 8). The mutation parser reads the label and writes back to the matching `state/<key>.yaml`. Shared mutations (anki_card_count, prs_opened, traces_completed, lineage_detours_done) write to `state/shared.yaml`.

- [ ] **Step 1: Write failing test for label-driven routing in `state_mutations`**

```python
# Append to tests/test_state_mutations.py
def test_mutation_routes_to_correct_syllabus_state(tmp_path):
    from src.state_mutations import apply_review_mutations
    from src.state import SyllabusState, SharedState
    from datetime import date
    from zoneinfo import ZoneInfo

    long_way = SyllabusState(
        start_date=date(2026, 1, 1), phase=1, month=1,
        current_module=2, current_book="A",
    )
    job_rdy = SyllabusState(
        start_date=date(2026, 5, 1), phase=1, month=1,
        current_module=1, current_book="B",
    )
    shared = SharedState(timezone=ZoneInfo("UTC"))

    syllabus_states = {"long-way": long_way, "job-readiness": job_rdy}

    mutations = [
        {"syllabus_key": "job-readiness", "kind": "advance_module"},
        {"syllabus_key": "long-way", "kind": "advance_module"},
        {"syllabus_key": None, "kind": "increment_anki", "by": 5},
    ]
    apply_review_mutations(mutations, syllabus_states=syllabus_states, shared=shared)

    assert long_way.current_module == 3
    assert job_rdy.current_module == 2
    assert shared.manual_counters["anki_card_count"] == 5
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_state_mutations.py::test_mutation_routes_to_correct_syllabus_state -v`
Expected: FAIL.

- [ ] **Step 3: Refactor `apply_review_mutations`**

Change its signature to:

```python
def apply_review_mutations(
    mutations: list[dict],
    *,
    syllabus_states: dict[str, SyllabusState],
    shared: SharedState,
) -> None:
    for m in mutations:
        kind = m["kind"]
        if m.get("syllabus_key") is None:
            _apply_shared(shared, m)
        else:
            sy = syllabus_states[m["syllabus_key"]]
            _apply_per_syllabus(sy, m)


def _apply_per_syllabus(sy: SyllabusState, m: dict) -> None:
    kind = m["kind"]
    if kind == "advance_module":
        sy.completed_modules.append(sy.current_module)
        sy.current_module += 1
    elif kind == "pause":
        sy.paused = True
        sy.paused_since = m["date"]
    elif kind == "transition_book":
        sy.books_state[m["title"]] = m["to"]
        if m["to"] == "current":
            sy.current_book = m["title"]
    elif kind == "revert":
        # whatever revert means in the existing parser (likely undo last advance)
        ...


def _apply_shared(shared: SharedState, m: dict) -> None:
    kind = m["kind"]
    if kind == "increment_anki":
        shared.manual_counters["anki_card_count"] = (
            shared.manual_counters.get("anki_card_count", 0) + int(m["by"])
        )
    elif kind == "increment_counter":
        # generic prs_opened / traces_completed bump
        ...
```

Before writing the bodies above, open `src/state_mutations.py` and `tests/test_state_mutations.py` to enumerate the complete mutation vocabulary the existing parser supports (advance_module, pause, unpause, transition_book, increment_anki, revert, etc.). Implement every existing kind, routed to per-syllabus or shared per the partition in the spec (Anki + manual_counters → shared; everything that touches module/book/learning_tracks/pause → per-syllabus). The test below covers three representative kinds; add a parametrized test asserting every existing kind is still handled after the refactor.

Update the parser (`parse_review_checkboxes` or equivalent) to read `syllabus_key` from the Todoist task's labels (`syllabus:<key>`). The shared-only mutations (Anki etc.) have `syllabus_key=None`.

- [ ] **Step 4: In `src/state_review.py`, emit one state-review template per syllabus**

The state-review-firing code currently loads one weekly-state-review template; it must now iterate enabled syllabuses and emit one per syllabus, each with `syllabus_key` set so it picks up the right Todoist project (Task 8) and the right state slice (this task's parser).

- [ ] **Step 5: Verify pass on both test files**

Run: `pytest tests/test_state_mutations.py tests/test_state_review.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/state_review.py src/state_mutations.py tests/test_state_review.py tests/test_state_mutations.py
git commit -m "feat(state-review): per-syllabus state-review tasks + label-routed mutations"
```

---

## Task 10: Per-syllabus reflection paths + per-syllabus streak

**Files:**
- Modify: `src/reflections.py`, `src/streaks.py`
- Test: `tests/test_reflections.py`, `tests/test_streaks.py` (extend)

Reflection stubs now write under `reflections/<syllabus_key>/<cadence>/<file>.md`. Streaks compute from the per-syllabus `SyllabusState.pause_history` + that syllabus's completion record.

- [ ] **Step 1: Write failing test for reflections path**

```python
# Append to tests/test_reflections.py
def test_create_stub_writes_under_syllabus_folder(tmp_path):
    from src.reflections import create_stub
    out = create_stub(
        repo_root=tmp_path,
        syllabus_key="job-readiness",
        cadence="weekly",
        period="2026-W21",
        template_text="# Week {period}\n",
    )
    assert out.path == tmp_path / "reflections" / "job-readiness" / "weekly" / "2026-W21.md"
    assert out.path.read_text().startswith("# Week 2026-W21")
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_reflections.py::test_create_stub_writes_under_syllabus_folder -v`
Expected: FAIL (signature mismatch or wrong path).

- [ ] **Step 3: Refactor `create_stub` signature**

```python
@dataclass
class StubResult:
    path: Path
    created: bool


def create_stub(
    *,
    repo_root: Path,
    syllabus_key: str,
    cadence: str,
    period: str,
    template_text: str,
) -> StubResult:
    target = repo_root / "reflections" / syllabus_key / cadence / f"{period}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return StubResult(path=target, created=False)
    rendered = template_text.replace("{period}", period)
    target.write_text(rendered)
    return StubResult(path=target, created=True)
```

Update call sites in `src/main.py` to pass `syllabus_key` from the outer loop.

- [ ] **Step 4: Write failing test for per-syllabus streak**

```python
# Append to tests/test_streaks.py
def test_streak_computed_from_syllabus_state_only():
    from src.streaks import compute_streak
    from src.state import SyllabusState
    from datetime import date

    sy = SyllabusState(
        start_date=date(2026, 5, 1), phase=1, month=1,
        current_module=1, current_book="x",
        pause_history=[],
    )
    completion_dates = {date(2026, 5, 20), date(2026, 5, 21), date(2026, 5, 22)}
    s = compute_streak(syllabus=sy, completion_dates=completion_dates, today=date(2026, 5, 22))
    assert s.length == 3
```

- [ ] **Step 5: Verify failure, then refactor `compute_streak`**

Run: `pytest tests/test_streaks.py::test_streak_computed_from_syllabus_state_only -v`
Expected: FAIL.

In `src/streaks.py`, change `compute_streak` to take a `SyllabusState` instead of the legacy `State`. The function body is otherwise unchanged — it walks completion dates from `today` backwards, treating Sundays + pause-history dates as skip days.

- [ ] **Step 6: Verify pass**

Run: `pytest tests/test_reflections.py tests/test_streaks.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/reflections.py src/streaks.py tests/test_reflections.py tests/test_streaks.py src/main.py
git commit -m "feat(reflections,streaks): per-syllabus paths and per-syllabus streak computation"
```

---

## Task 11: Refactor `src/dashboard.py` for shared header + per-syllabus cards

**Files:**
- Modify: `src/dashboard.py`, `docs/assets/style.css` (small additions)
- Test: `tests/test_dashboard.py`, `tests/test_render_dashboard.py` (extend)

The dashboard now renders:
- A top header band with `timezone`, `manual_counters.anki_card_count`, `manual_counters.prs_opened`.
- One card per enabled syllabus in `priority_order`, each showing phase/month/module, current_book, books_state summary, learning_tracks summary, streak length, paused state, recent reflection links.

`docs/assets/data.json` becomes `{ shared, syllabuses: { <key>: {...} }, priority_order }`.

- [ ] **Step 1: Write failing test for the new data shape**

```python
# Append to tests/test_dashboard.py
def test_render_data_has_shared_and_per_syllabus_sections(tmp_path):
    from src.dashboard import build_data
    from src.state import SyllabusState, SharedState
    from datetime import date
    from zoneinfo import ZoneInfo

    shared = SharedState(timezone=ZoneInfo("Asia/Kolkata"),
                         manual_counters={"anki_card_count": 100, "prs_opened": 2})
    syllabus_states = {
        "long-way": SyllabusState(
            start_date=date(2026, 5, 5), phase=1, month=1,
            current_module=1, current_book="CS:APP",
        ),
    }
    priority_order = ["long-way"]
    data = build_data(
        shared=shared,
        syllabus_states=syllabus_states,
        priority_order=priority_order,
        completion_by_syllabus={"long-way": set()},
        syllabus_metadata={"long-way": {"phases": [], "books": []}},
        today=date(2026, 5, 28),
    )
    assert data["shared"]["anki_card_count"] == 100
    assert data["priority_order"] == ["long-way"]
    assert "long-way" in data["syllabuses"]
    assert data["syllabuses"]["long-way"]["current_module"] == 1
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_dashboard.py::test_render_data_has_shared_and_per_syllabus_sections -v`
Expected: FAIL.

- [ ] **Step 3: Implement `build_data` (new top-level function in `src/dashboard.py`)**

Extract the existing render logic (which currently builds a flat dict against `State`) into a `_build_syllabus_card(...)` helper, then wrap with a top-level builder that emits:

```python
def build_data(*, shared, syllabus_states, priority_order, completion_by_syllabus,
               syllabus_metadata, today) -> dict:
    return {
        "shared": {
            "timezone": str(shared.timezone),
            "anki_card_count": shared.manual_counters.get("anki_card_count", 0),
            "prs_opened": shared.manual_counters.get("prs_opened", 0),
            "manual_counters": dict(shared.manual_counters),
        },
        "priority_order": list(priority_order),
        "syllabuses": {
            key: _build_syllabus_card(
                key=key,
                state=syllabus_states[key],
                completion=completion_by_syllabus.get(key, set()),
                metadata=syllabus_metadata.get(key, {}),
                today=today,
            )
            for key in priority_order
        },
    }
```

`_build_syllabus_card` returns roughly the keys the current renderer expects per state: `current_phase_name`, `month`, `current_module`, `current_book`, `streak`, `paused`, `paused_since`, `books_state_summary`, `learning_tracks_summary`, `reflections`.

- [ ] **Step 4: Update the HTML renderer**

Update the function that builds `docs/index.html` to walk `data["priority_order"]` and emit a card per syllabus inside `<section class="syllabus-card">`, with a `<header>` band consuming `data["shared"]`. Add minimal CSS to `docs/assets/style.css` for `.syllabus-card`.

- [ ] **Step 5: Verify pass on the dashboard test suites**

Run: `pytest tests/test_dashboard.py tests/test_render_dashboard.py -v`
Expected: PASS.

- [ ] **Step 6: Render the dashboard locally and eyeball it**

Run: `python -m scripts.render_dashboard --output /tmp/idx.html`
(If `scripts/render_dashboard.py` doesn't accept `--output`, just run it and inspect `docs/index.html` directly.)
Open in a browser. Expected: a single page with header band on top and one Long Way card below; second card visibly missing only because there's no second syllabus configured yet.

- [ ] **Step 7: Commit**

```bash
git add src/dashboard.py docs/assets/style.css tests/test_dashboard.py tests/test_render_dashboard.py
git commit -m "feat(dashboard): shared header + per-syllabus cards"
```

---

## Task 12: Refactor `src/main.py` to loop over syllabuses, retire single-syllabus call sites

**Files:**
- Modify: `src/main.py`, `src/config.py` (remove old `Config`/`load_config` once unused)
- Test: `tests/test_main.py`, `tests/test_main_cli.py` (extend)

This task wires the new types together. The daily loop becomes:

```python
def run(...):
    cfg = load_multi_syllabus_config(yaml_path, env_path)
    shared = load_shared_state(Path("state/shared.yaml"))
    nc = load_namespaced_cache(Path(".task_cache.json"))
    project_router = {k: s.todoist_project_id for k, s in cfg.syllabuses.items()}
    todoist = TodoistClient(token=cfg.todoist_token, project_router=project_router)
    syllabus_states: dict[str, SyllabusState] = {}
    for key in cfg.priority_order:
        entry = cfg.syllabuses[key]
        sy_state = load_syllabus_state(entry.state_file)
        syllabus_states[key] = sy_state
        syllabus = load_syllabus_for_entry(entry)
        templates = load_templates(entry.path / "rituals", entry.path / "modules.yaml")
        for tpl in templates:
            rt = should_create_today(template=tpl, today=today, state=sy_state,
                                     syllabus=syllabus, config=cfg, syllabus_key=key)
            if rt is None:
                continue
            if nc.get(key, rt.external_id) is not None:
                continue
            result = todoist.create(rt)
            nc.set(key, rt.external_id, {"todoist_id": result.todoist_id, ...})
    save_namespaced_cache(Path(".task_cache.json"), nc)
    # then: dashboard render with build_data over priority_order
```

- [ ] **Step 1: Update the daily entrypoint**

Replace the body of `src/main.run()` (or the `main()` function — whichever is the orchestrator) per the sketch above. Keep CLI flags compatible (`--dry-run`, `--cache-file`, `--cleanup-project`, `--skip-dashboard`, etc.). For `--dry-run`, do not call Todoist or write caches; for `--cache-file`, read/write the supplied path instead of `.task_cache.json`.

- [ ] **Step 2: Update all imports in `src/main.py`**

Remove old `from src.config import Config, load_config`; replace with `from src.config import MultiSyllabusConfig, load_multi_syllabus_config`.

- [ ] **Step 3: Delete `Config`, `load_config`, and the legacy single-state path**

In `src/config.py` remove the old `Config` dataclass and `load_config` function. In `src/state.py` remove the old `State` dataclass and `load_state`/`save_state` if all consumers now use `SharedState` + `SyllabusState`. Search for stragglers:

```bash
grep -rn "load_config\|from src.config import Config\b" src/ tests/ scripts/
grep -rn "load_state\b\|from src.state import State\b" src/ tests/ scripts/
```

Any remaining hits in `src/` are bugs; fix them. Hits in `tests/` for tests of the *removed* loader can be deleted; hits in tests of unrelated paths must migrate to the new types.

- [ ] **Step 4: Run the full test suite (excluding golden, which is Task 15)**

Run: `pytest --ignore=tests/test_golden.py -v`
Expected: all pass. Existing tests that referenced `State`/`Config` must now use `SyllabusState`/`MultiSyllabusConfig`. If a test fixture is now unreachable, delete it.

- [ ] **Step 5: Manual smoke test — daily run in dry mode**

Run: `python -m src.main --dry-run --frozen-date 2026-05-28`
(Or whatever flag the engine uses to freeze the clock — check `src/clock.py`.)
Expected: completes cleanly; logs show templates evaluated for the `long-way` syllabus; no Todoist calls.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(main): loop over syllabuses, retire legacy Config/State"
```

---

## Task 13: Cross-cutting validator checks in `src/curriculum_validator.py`

**Files:**
- Modify: `src/curriculum_validator.py`
- Test: `tests/test_curriculum_validator.py` (extend)

Add new cross-syllabus validation that runs at engine startup (called from `src/main.py` after config + state load, before any Todoist call). Existing per-syllabus checks unchanged.

Checks to add:
1. Every entry in `priority_order` resolves to an existing `curricula/<key>/` directory.
2. Every entry's `state_file` exists on disk.
3. Every entry's `todoist_project_id` is a non-empty string.
4. Every entry's `path/reflection_templates/` exists if `path/rituals/<weekly|monthly|quarterly|annual>.yaml` declares a stub-creating template.

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/test_curriculum_validator.py
def test_validator_errors_when_syllabus_path_missing(tmp_path, monkeypatch):
    from src.curriculum_validator import validate_multi_syllabus
    from src.config import SyllabusEntry
    entry = SyllabusEntry(
        key="long-way",
        path=tmp_path / "does-not-exist",
        todoist_project_id="X",
        state_file=tmp_path / "state.yaml",
        enabled=True,
        ritual_times={},
    )
    errs = validate_multi_syllabus({"long-way": entry}, repo_root=tmp_path)
    assert any("path" in e for e in errs)


def test_validator_errors_when_state_file_missing(tmp_path):
    from src.curriculum_validator import validate_multi_syllabus
    from src.config import SyllabusEntry
    (tmp_path / "curricula" / "long-way").mkdir(parents=True)
    entry = SyllabusEntry(
        key="long-way",
        path=tmp_path / "curricula" / "long-way",
        todoist_project_id="X",
        state_file=tmp_path / "state" / "long-way.yaml",
        enabled=True,
        ritual_times={},
    )
    errs = validate_multi_syllabus({"long-way": entry}, repo_root=tmp_path)
    assert any("state_file" in e for e in errs)


def test_validator_errors_on_empty_project_id(tmp_path):
    from src.curriculum_validator import validate_multi_syllabus
    from src.config import SyllabusEntry
    (tmp_path / "curricula" / "long-way").mkdir(parents=True)
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "long-way.yaml").write_text("start_date: 2026-01-01\ncurrent_module: 1\ncurrent_book: x\n")
    entry = SyllabusEntry(
        key="long-way",
        path=tmp_path / "curricula" / "long-way",
        todoist_project_id="",
        state_file=tmp_path / "state" / "long-way.yaml",
        enabled=True,
        ritual_times={},
    )
    errs = validate_multi_syllabus({"long-way": entry}, repo_root=tmp_path)
    assert any("todoist_project_id" in e for e in errs)
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_curriculum_validator.py -v -k validate_multi_syllabus`
Expected: FAIL on import.

- [ ] **Step 3: Implement**

Add to `src/curriculum_validator.py`:

```python
def validate_multi_syllabus(
    syllabuses: dict[str, "SyllabusEntry"], *, repo_root: Path
) -> list[str]:
    errors: list[str] = []
    for key, entry in syllabuses.items():
        if not entry.path.exists() or not entry.path.is_dir():
            errors.append(f"syllabus '{key}': path {entry.path} does not exist")
        if not entry.state_file.exists():
            errors.append(f"syllabus '{key}': state_file {entry.state_file} does not exist")
        if not entry.todoist_project_id.strip():
            errors.append(f"syllabus '{key}': todoist_project_id is empty")
    return errors
```

Wire it into `src/main.py`'s startup sequence so a non-empty `errors` list aborts the run with a multi-line summary (matching the existing per-syllabus validator's behavior).

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_curriculum_validator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/curriculum_validator.py tests/test_curriculum_validator.py src/main.py
git commit -m "feat(validator): add cross-syllabus startup checks"
```

---

## Task 14: Timetable visualizer `scripts/show_timetable.py`

**Files:**
- Create: `scripts/show_timetable.py`
- Test: `tests/test_show_timetable.py` (new)

A CLI that loads `config.yaml`, resolves each enabled syllabus's effective `ritual_times` and the cadence for each ritual (read from each syllabus's `rituals/*.yaml`), and prints a weekly grid. Read-only; never touches Todoist or state. Exit code 0 if no collisions, non-zero otherwise.

- [ ] **Step 1: Write failing tests for the core data-shaping function**

```python
# tests/test_show_timetable.py
from pathlib import Path
from datetime import time

import pytest


def test_build_rows_collision_detected(tmp_path):
    from scripts.show_timetable import TimetableRow, build_rows, find_collisions
    rows = [
        TimetableRow(time="10:00", weekdays={"Sat"}, syllabus="long-way", ritual="weekly_state_review"),
        TimetableRow(time="10:00", weekdays={"Sat"}, syllabus="job-readiness", ritual="weekly_state_review"),
    ]
    cols = find_collisions(rows)
    assert len(cols) == 1
    assert cols[0].time == "10:00"
    assert cols[0].weekday == "Sat"


def test_build_rows_no_collision_different_times():
    from scripts.show_timetable import TimetableRow, find_collisions
    rows = [
        TimetableRow(time="06:00", weekdays={"Mon", "Tue"}, syllabus="long-way", ritual="morning_reading"),
        TimetableRow(time="13:00", weekdays={"Mon", "Tue"}, syllabus="job-readiness", ritual="morning_reading"),
    ]
    assert find_collisions(rows) == []


def test_main_exits_nonzero_on_collision(tmp_path, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "ritual_times:\n  weekly_state_review: '10:00'\n"
        "priority_order: [a, b]\n"
        "syllabuses:\n"
        "  a:\n    path: curricula/a\n    todoist_project_id: '1'\n    state_file: state/a.yaml\n    enabled: true\n"
        "  b:\n    path: curricula/b\n    todoist_project_id: '2'\n    state_file: state/b.yaml\n    enabled: true\n"
        "dashboard:\n  github_username: u\n  repo_name: r\n"
    )
    (tmp_path / ".env").write_text("TODOIST_TOKEN=x\n")
    (tmp_path / "curricula" / "a" / "rituals").mkdir(parents=True)
    (tmp_path / "curricula" / "b" / "rituals").mkdir(parents=True)
    (tmp_path / "curricula" / "a" / "rituals" / "weekly.yaml").write_text(
        "- id: weekly-state-review\n  cadence: weekly\n  weekday: saturday\n  ritual_time: weekly_state_review\n  title: x\n"
    )
    (tmp_path / "curricula" / "b" / "rituals" / "weekly.yaml").write_text(
        "- id: weekly-state-review\n  cadence: weekly\n  weekday: saturday\n  ritual_time: weekly_state_review\n  title: y\n"
    )
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "a.yaml").write_text("start_date: 2026-01-01\ncurrent_module: 1\ncurrent_book: x\n")
    (tmp_path / "state" / "b.yaml").write_text("start_date: 2026-01-01\ncurrent_module: 1\ncurrent_book: y\n")

    from scripts.show_timetable import main
    rc = main(["--config", str(cfg), "--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc != 0
    assert "COLLISION" in out or "collision" in out.lower()
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_show_timetable.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `scripts/show_timetable.py`**

```python
"""Preview the resolved weekly timetable across all enabled syllabuses.

Loads config.yaml + each syllabus's rituals/*.yaml. For every ritual template
that has a `ritual_time` slot, resolves the effective clock time (per-syllabus
override or top-level inheritance), figures out which weekdays it fires on
(from cadence + weekday/skip rules), and prints a grid. Surfaces (slot, time)
collisions across enabled syllabuses.

Read-only. Never calls Todoist. Never reads or writes caches or state files
beyond their declared paths (and only for path validation if --strict).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.config import load_multi_syllabus_config


WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_BY_NAME = {
    "monday": "Mon", "tuesday": "Tue", "wednesday": "Wed", "thursday": "Thu",
    "friday": "Fri", "saturday": "Sat", "sunday": "Sun",
}


@dataclass
class TimetableRow:
    time: str
    weekdays: set[str]
    syllabus: str
    ritual: str


@dataclass
class Collision:
    time: str
    weekday: str
    rows: list[TimetableRow] = field(default_factory=list)


def _weekdays_for_template(tpl: dict, *, sunday_off: bool) -> set[str]:
    cadence = tpl.get("cadence", "daily")
    if cadence == "daily":
        days = set(WEEKDAYS)
        if sunday_off:
            days.discard("Sun")
        skip = tpl.get("skip", []) or []
        if isinstance(skip, str):
            skip = [skip]
        for s in skip:
            if s in WEEKDAY_BY_NAME:
                days.discard(WEEKDAY_BY_NAME[s])
        return days
    if cadence == "weekly":
        wd = tpl.get("weekday")
        return {WEEKDAY_BY_NAME[wd]} if wd in WEEKDAY_BY_NAME else set()
    # monthly / quarterly / annual: not displayed in weekly view; collapse to
    # whatever weekday they declare, else empty.
    wd = tpl.get("weekday")
    return {WEEKDAY_BY_NAME[wd]} if wd in WEEKDAY_BY_NAME else set()


def build_rows(cfg, repo_root: Path) -> list[TimetableRow]:
    rows: list[TimetableRow] = []
    for key in cfg.priority_order:
        entry = cfg.syllabuses[key]
        rituals_dir = repo_root / entry.path / "rituals"
        if not rituals_dir.exists():
            continue
        for yaml_file in sorted(rituals_dir.glob("*.yaml")):
            with yaml_file.open() as f:
                items = yaml.safe_load(f) or []
            for tpl in items:
                slot = tpl.get("ritual_time")
                if not slot:
                    continue
                time = entry.ritual_times.get(slot)
                if not time:
                    continue
                rows.append(TimetableRow(
                    time=time,
                    weekdays=_weekdays_for_template(tpl, sunday_off=cfg.sunday_off),
                    syllabus=key,
                    ritual=slot,
                ))
    return rows


def find_collisions(rows: list[TimetableRow]) -> list[Collision]:
    bucket: dict[tuple[str, str], list[TimetableRow]] = {}
    for r in rows:
        for wd in r.weekdays:
            bucket.setdefault((r.time, wd), []).append(r)
    out: list[Collision] = []
    for (time, wd), rs in bucket.items():
        syllabuses = {r.syllabus for r in rs}
        if len(syllabuses) > 1:
            out.append(Collision(time=time, weekday=wd, rows=rs))
    return out


def render(rows: list[TimetableRow], collisions: list[Collision]) -> str:
    rows = sorted(rows, key=lambda r: (r.time, r.syllabus))
    coll_keys = {(c.time, c.weekday) for c in collisions}
    lines = []
    lines.append(f"  Time   {'  '.join(WEEKDAYS):<35}  Syllabus       Ritual")
    lines.append(f"  ────   {'  '.join('───' for _ in WEEKDAYS):<35}  ──────────     ─────────────────")
    for r in rows:
        cells = []
        coll_in_row = False
        for wd in WEEKDAYS:
            if wd in r.weekdays:
                cells.append("●  ")
                if (r.time, wd) in coll_keys:
                    coll_in_row = True
            else:
                cells.append("-  ")
        marker = "  ⚠ COLLISION" if coll_in_row else ""
        lines.append(
            f"  {r.time}  {''.join(cells):<35}  {r.syllabus:<13}  {r.ritual}{marker}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Preview the resolved weekly timetable across all syllabuses")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--env", default=".env")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--syllabus", default=None, help="filter to one syllabus")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_multi_syllabus_config(Path(args.config), Path(args.env))
    repo_root = Path(args.repo_root)
    rows = build_rows(cfg, repo_root)
    if args.syllabus:
        rows = [r for r in rows if r.syllabus == args.syllabus]
    cols = find_collisions(rows)

    if args.json:
        import json
        print(json.dumps({
            "rows": [{"time": r.time, "weekdays": sorted(r.weekdays),
                      "syllabus": r.syllabus, "ritual": r.ritual} for r in rows],
            "collisions": [{"time": c.time, "weekday": c.weekday,
                            "rows": [{"syllabus": r.syllabus, "ritual": r.ritual} for r in c.rows]}
                           for c in cols],
        }, indent=2))
    else:
        print(f"Effective schedule (priority_order: {', '.join(cfg.priority_order)})\n")
        print(render(rows, cols))
        if cols:
            print(f"\nCollisions: {len(cols)}")
            for c in cols:
                names = ", ".join(f"{r.syllabus}:{r.ritual}" for r in c.rows)
                print(f"  {c.time} {c.weekday} — {names}")
            print("  Resolve: change clock time on one, OR set allow_slot_overlap: true on one")

    return 1 if cols else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run all visualizer tests**

Run: `pytest tests/test_show_timetable.py -v`
Expected: all pass.

- [ ] **Step 5: Run visualizer against the live repo**

Run: `python -m scripts.show_timetable`
Expected: a printed grid with all `long-way` rituals; no collisions; exit code 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/show_timetable.py tests/test_show_timetable.py
git commit -m "feat(scripts): add show_timetable.py timetable visualizer with collision detection"
```

---

## Task 15: Retrofit golden test fixtures + add multi-syllabus fixtures

**Files:**
- Modify: every file under `tests/golden/*.json`, `tests/test_golden.py`
- Add: `tests/golden/multi-syllabus-*.json` (two new fixtures)

The golden tests pin the exact set of tasks the engine produces on each date. Existing fixtures need a `syllabus_key: "long-way"` field on every task entry. Two new fixtures lock in two-syllabus behavior — one without collisions (clean priority order) and one with an `allow_slot_overlap` escape hatch.

- [ ] **Step 1: Inspect one fixture and the test that consumes it**

Run:
```bash
cat tests/golden/2026-05-22.json | head -40
grep -n "" tests/test_golden.py | head -80
```
Expected: each fixture is a JSON array (or object) of task records. Note the exact record shape — `external_id`, `content`, `labels`, etc. — and how `tests/test_golden.py` loads and asserts on it.

- [ ] **Step 2: Decide regeneration vs in-place edit**

Search for a regenerator: `grep -rn "golden" scripts/ tests/`. If there is a writer (e.g., `tests/test_golden.py` has a function gated behind `pytest --update-goldens` or a `scripts/regenerate_goldens.py`), use it. Otherwise, run this one-shot script from the repo root:

```python
# regen.py — local helper, not committed
import json
from pathlib import Path
for p in Path("tests/golden").glob("*.json"):
    data = json.loads(p.read_text())
    # If data is a list of task records:
    if isinstance(data, list):
        for rec in data:
            rec.setdefault("syllabus_key", "long-way")
    # If data is {"tasks": [...]} or similar, adapt accordingly.
    elif isinstance(data, dict) and "tasks" in data:
        for rec in data["tasks"]:
            rec.setdefault("syllabus_key", "long-way")
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
```

Run it once: `python regen.py`. Delete the helper after.

- [ ] **Step 3: Update `tests/test_golden.py` to assert `syllabus_key` on each task**

Add an assertion in the test loop that confirms every task in each fixture carries a non-empty `syllabus_key`:

```python
for task in tasks_in_fixture:
    assert task.get("syllabus_key"), f"task {task.get('external_id')} missing syllabus_key"
```

This guards against future drift.

- [ ] **Step 4: Add two new multi-syllabus fixtures**

Create `tests/golden/multi-syllabus-clean-2026-06-01.json` and `tests/golden/multi-syllabus-overlap-2026-06-01.json` exercising:

- Two syllabuses, no slot collisions, both fire their morning_reading.
- Two syllabuses, one slot collision suppressed via `allow_slot_overlap: true` on one side.

Generate them by running the engine in `--dry-run` mode with a temporary `config.yaml` that declares both syllabuses, capturing the JSON output. If the engine does not emit JSON directly, add a small `--emit-golden <path>` flag for this purpose (one-line addition to `src/main.py`'s dry-run branch) or write a helper test that loads fixtures, runs `should_create_today` over a curated date, and dumps the resulting `ResolvedTemplate` list as JSON. Whichever approach you choose, commit the resulting fixtures plus the corresponding test entries (`tests/test_golden.py` typically parameterizes over `tests/golden/*.json` — verify both new fixtures get picked up).

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all pass, including golden tests.

- [ ] **Step 6: Commit**

```bash
git add tests/golden/ tests/test_golden.py
git commit -m "test(golden): add syllabus_key to existing fixtures + two multi-syllabus fixtures"
```

---

## Task 16: Documentation — README, AGENTS.md, FORKING.md

**Files:**
- Modify: `README.md`, `AGENTS.md`, `docs/FORKING.md`

- [ ] **Step 1: Rewrite the README's "What it does" + "Local setup" + add "Local tooling" + "Adding another syllabus" sections**

The README currently describes a single-curriculum repo. Update the structural prose:

- Replace references to `curriculum/` with `curricula/<name>/`.
- Replace references to `state.yaml` with `state/shared.yaml` + `state/<name>.yaml`.
- Add a new section after "What it does" titled **"Multiple syllabuses"** explaining that the engine runs N syllabuses in parallel from `curricula/<name>/`, with per-syllabus Todoist projects, streaks, pauses, and dashboard cards, ordered by `priority_order` in `config.yaml`.
- Add a new section **"Local tooling"** with:
  - `scripts/show_timetable.py` — preview the resolved schedule and flag slot collisions.
  - `scripts/migrate_to_multi_syllabus.py` — one-shot migration for existing single-syllabus forks. Document the `--dry-run` and `--name` flags.
- Add a new section **"Adding another syllabus"** with a step-by-step: create `curricula/<new>/` (recommended: copy from `examples/`), create `state/<new>.yaml`, add a block to `syllabuses:` in `config.yaml`, add `<new>` to `priority_order`, run `python -m scripts.show_timetable` to verify the schedule, commit.

- [ ] **Step 2: Update `AGENTS.md`**

The interview script must now ask "single syllabus or multiple?" up front (default: single). Output layout is always `curricula/<name>/` even for single-syllabus forks so users do not migrate again later. Update Step 1 of the interview accordingly. Update the file-layout diagram in Section 2 to show `curricula/<name>/`.

- [ ] **Step 3: Update `docs/FORKING.md`**

Replace path references (`curriculum/` → `curricula/<name>/`, `state.yaml` → `state/<name>.yaml`).

- [ ] **Step 4: Sanity-check renders**

Run: `python -m scripts.show_timetable && python -m src.main --dry-run --frozen-date 2026-05-28`
Expected: clean output from both.

- [ ] **Step 5: Commit**

```bash
git add README.md AGENTS.md docs/FORKING.md
git commit -m "docs: rewrite README/AGENTS/FORKING for multi-syllabus layout"
```

---

## Done criteria

- All tests pass (`pytest -v`).
- `python -m scripts.show_timetable` prints a grid with zero collisions for the current `long-way` config.
- `python -m src.main --dry-run --frozen-date 2026-05-28` completes cleanly.
- A second syllabus can be added by:
  - creating `curricula/<new>/`,
  - creating `state/<new>.yaml`,
  - appending a `syllabuses.<new>` block in `config.yaml`,
  - adding `<new>` to `priority_order`,
  - running the timetable visualizer to confirm no collisions.
- The dashboard at `docs/index.html` renders a shared header band + one card per enabled syllabus in priority order.

---

## Spec coverage check

| Spec section | Implementing tasks |
|---|---|
| Repo layout (`curricula/`, `state/`, `reflections/<key>/`) | T4 (script), T5 (execution) |
| `config.yaml` new shape | T2 (loader), T4 (migration), T5 (execution) |
| `state/shared.yaml`, `state/<name>.yaml` | T1 (loaders), T4–T5 (split + execution) |
| Engine loop changes (config, state, scheduler, templates, todoist, cache, state_review, state_mutations, reflections, streaks, dashboard, validator, main) | T1, T3, T6, T7, T8, T9, T10, T11, T12, T13 |
| Per-syllabus Todoist routing + `syllabus:<key>` label | T8 |
| Cache namespacing | T3, T12 |
| Per-syllabus reflections + streaks | T10 |
| Dashboard shared header + per-syllabus cards | T11 |
| Cross-cutting validator checks | T13 |
| Slot-collision detection | T2 (config-level), T14 (visualizer) |
| Migration script | T4, T5 |
| Timetable visualizer | T14 |
| Golden test retrofit + new multi-syllabus fixtures | T15 |
| README / AGENTS.md / FORKING.md updates | T16 |
