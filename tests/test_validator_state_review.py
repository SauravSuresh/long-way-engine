"""Tests for the three state-review validator rules (11, 12, 13)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.curriculum_validator import CurriculumError, validate


_SYLLABUS = """
meta:
  name: "Test"
  start_month_index: 1
phases:
  - number: 1
    name: "P1"
    months: [1, 3]
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
ritual_times_required:
  - morning_reading
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


def _setup(tmp_path: Path, weekly_yaml: str) -> Path:
    (tmp_path / "syllabus.yaml").write_text(_SYLLABUS)
    (tmp_path / "manifest.yaml").write_text(_MANIFEST)
    (tmp_path / "modules.yaml").write_text(_MODULES)
    rituals = tmp_path / "rituals"
    rituals.mkdir()
    (rituals / "weekly.yaml").write_text(weekly_yaml)
    return tmp_path


def test_check11_multiple_state_review_templates(tmp_path: Path):
    weekly = """
- id: review-a
  title: "A"
  description: ""
  due: ""
  labels: []
  cadence: weekly
  day_of_week: sunday
  state_review: true

- id: review-b
  title: "B"
  description: ""
  due: ""
  labels: []
  cadence: weekly
  day_of_week: sunday
  state_review: true
"""
    _setup(tmp_path, weekly)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    assert "multiple state_review templates" in str(exc.value)


def test_check12_state_review_must_be_weekly(tmp_path: Path):
    weekly = """
- id: review-bad
  title: "X"
  description: ""
  due: ""
  labels: []
  cadence: monthly
  day_of_month: 1
  state_review: true
"""
    _setup(tmp_path, weekly)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    msg = str(exc.value)
    assert "must be 'weekly'" in msg


def test_check12_state_review_requires_day_of_week(tmp_path: Path):
    weekly = """
- id: review-bad
  title: "X"
  description: ""
  due: ""
  labels: []
  cadence: weekly
  state_review: true
"""
    _setup(tmp_path, weekly)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    assert "must set day_of_week" in str(exc.value)


def test_check13_unknown_action_type(tmp_path: Path):
    weekly = """
- id: review-x
  title: "X"
  description: ""
  due: ""
  labels: []
  cadence: weekly
  day_of_week: sunday
  state_review: true
  sub_tasks:
    - title: "do thing"
      action: { type: do_thing }
"""
    _setup(tmp_path, weekly)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    assert "unknown action.type 'do_thing'" in str(exc.value)


def test_check13_unknown_show_if(tmp_path: Path):
    weekly = """
- id: review-x
  title: "X"
  description: ""
  due: ""
  labels: []
  cadence: weekly
  day_of_week: sunday
  state_review: true
  sub_tasks:
    - title: "advance"
      action: { type: advance_module }
      show_if: when_jupiter_aligns
"""
    _setup(tmp_path, weekly)
    with pytest.raises(CurriculumError) as exc:
        validate(tmp_path, ritual_times={"morning_reading": "06:00"})
    assert "unknown show_if 'when_jupiter_aligns'" in str(exc.value)


def test_state_review_passes_with_supported_vocabulary(tmp_path: Path):
    weekly = """
- id: review-ok
  title: "OK"
  description: ""
  due: ""
  labels: []
  cadence: weekly
  day_of_week: sunday
  state_review: true
  sub_tasks:
    - title: "advance"
      action: { type: advance_module }
      show_if: not_on_last_module
    - title: "mark done"
      action: { type: mark_book_finished, book: "B1" }
"""
    _setup(tmp_path, weekly)
    # No exception → validation passes.
    validate(tmp_path, ritual_times={"morning_reading": "06:00"})
