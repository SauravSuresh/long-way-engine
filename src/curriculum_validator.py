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
    for p in phases:
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
