"""Tests for validator rules 14-17 (tracks + gated_by)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.curriculum_validator import CurriculumError, validate


_SYLLABUS_BASE = """
meta:
  name: "Test"
  start_month_index: 1
phases:
  - number: 1
    name: "P1"
    months: [1, 12]
books:
  - title: "B1"
    author: "A"
    phase: 1
    months: [1, 3]
    role: primary
primary_book_by_month:
  1: "B1"
modules:
  - number: 1
    name: "M1"
    phase: 1
"""

_MANIFEST = """
ritual_times_required: [morning_reading]
placeholders_used: []
"""

_MODULES = """
- id: m1-onboarding
  title: "M1"
  description: ""
  due: "today"
  labels: []
  cadence: once-per-module
  module_number: 1
"""


def _setup(tmp_path: Path, *, syllabus_extra: str = "", weekly_yaml: str = "") -> Path:
    (tmp_path / "syllabus.yaml").write_text(_SYLLABUS_BASE + syllabus_extra)
    (tmp_path / "manifest.yaml").write_text(_MANIFEST)
    (tmp_path / "modules.yaml").write_text(_MODULES)
    rituals = tmp_path / "rituals"
    rituals.mkdir()
    if weekly_yaml:
        (rituals / "weekly.yaml").write_text(weekly_yaml)
    return tmp_path


def test_rule14_state_track_not_declared(tmp_path: Path):
    _setup(tmp_path)
    with pytest.raises(CurriculumError) as exc:
        validate(
            tmp_path,
            ritual_times={"morning_reading": "06:00"},
            state_learning_tracks={"Courses": {"X": "current"}},
        )
    assert "no matching declaration" in str(exc.value)


def test_rule14_skipped_when_state_absent(tmp_path: Path):
    _setup(tmp_path)
    validate(tmp_path, ritual_times={"morning_reading": "06:00"})


def test_rule15_duplicate_track(tmp_path: Path):
    extra = """
tracks:
  - { title: X, category: Courses, phase: 1 }
  - { title: X, category: Courses, phase: 1 }
"""
    _setup(tmp_path, syllabus_extra=extra)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    assert "duplicate track declaration" in str(exc.value)


def test_rule15_track_unknown_phase(tmp_path: Path):
    extra = """
tracks:
  - { title: X, category: Courses, phase: 99 }
"""
    _setup(tmp_path, syllabus_extra=extra)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    assert "unknown phase 99" in str(exc.value)


def test_rule16_months_out_of_range(tmp_path: Path):
    extra = """
tracks:
  - { title: X, category: Courses, phase: 1, months: [1, 99] }
"""
    _setup(tmp_path, syllabus_extra=extra)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    assert "out of range" in str(exc.value)


def test_rule16_months_start_after_end(tmp_path: Path):
    extra = """
tracks:
  - { title: X, category: Courses, phase: 1, months: [5, 3] }
"""
    _setup(tmp_path, syllabus_extra=extra)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    assert "start (5) > end (3)" in str(exc.value)


def test_rule17_unknown_gate_type(tmp_path: Path):
    weekly = """
- id: gated-tpl
  title: "T"
  description: ""
  due: ""
  labels: []
  cadence: weekly
  day_of_week: monday
  gated_by:
    - { type: phase_eq, value: 1 }
"""
    _setup(tmp_path, weekly_yaml=weekly)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    assert "unknown type 'phase_eq'" in str(exc.value)


def test_rule17_track_gate_references_undeclared(tmp_path: Path):
    weekly = """
- id: gated-tpl
  title: "T"
  description: ""
  due: ""
  labels: []
  cadence: weekly
  day_of_week: monday
  gated_by:
    - { type: track, category: Courses, item: "ghost" }
"""
    _setup(tmp_path, weekly_yaml=weekly)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    assert "undeclared track" in str(exc.value)


def test_rule17_unknown_lifecycle_state(tmp_path: Path):
    extra = """
tracks:
  - { title: X, category: Courses, phase: 1 }
"""
    weekly = """
- id: gated-tpl
  title: "T"
  description: ""
  due: ""
  labels: []
  cadence: weekly
  day_of_week: monday
  gated_by:
    - { type: track, category: Courses, item: X, states: [maybe] }
"""
    _setup(tmp_path, syllabus_extra=extra, weekly_yaml=weekly)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    assert "unknown state 'maybe'" in str(exc.value)


def test_rule17_module_gate_requires_int(tmp_path: Path):
    weekly = """
- id: gated-tpl
  title: "T"
  description: ""
  due: ""
  labels: []
  cadence: weekly
  day_of_week: monday
  gated_by:
    - { type: module_eq, value: "five" }
"""
    _setup(tmp_path, weekly_yaml=weekly)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    assert "requires integer 'value'" in str(exc.value)


def test_passing_track_and_gate(tmp_path: Path):
    extra = """
tracks:
  - { title: X, category: Courses, phase: 1, months: [3, 5] }
"""
    weekly = """
- id: gated-tpl
  title: "T"
  description: ""
  due: ""
  labels: []
  cadence: weekly
  day_of_week: monday
  gated_by:
    - { type: track, category: Courses, item: X, states: [current] }
    - { type: module_gte, value: 1 }
"""
    _setup(tmp_path, syllabus_extra=extra, weekly_yaml=weekly)
    validate(
        tmp_path,
        ritual_times={"morning_reading": "06:00"},
        state_learning_tracks={"Courses": {"X": "current"}},
    )
