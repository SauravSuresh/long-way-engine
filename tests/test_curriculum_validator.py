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
