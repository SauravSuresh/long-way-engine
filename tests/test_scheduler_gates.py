"""Scheduler integration for the gated_by predicate.

Each gate type is unit-tested in test_tracks.py; here we verify the
scheduler short-circuits should_create_today on a failing gate AFTER
paused / sunday_off shorts.
"""

from __future__ import annotations

from datetime import date

import pytest
from zoneinfo import ZoneInfo

from src.scheduler import should_create_today
from src.state import State
from src.templates import Template


def _state(**overrides):
    base = dict(
        start_date=date(2026, 5, 1),
        timezone=ZoneInfo("UTC"),
        phase=1,
        month=1,
        current_module=5,
        current_book="",
    )
    base.update(overrides)
    return State(**base)


class _Config:
    sunday_off = False
    pair_day = None
    ritual_times: dict = {}


def _template(gated_by):
    return Template(
        id="t",
        title="t",
        description="",
        due="",
        labels=[],
        cadence="daily",
        gated_by=gated_by,
    )


# A Monday so no sunday_off interaction.
MON = date(2026, 5, 4)


def test_no_gates_template_fires():
    tpl = _template([])
    assert should_create_today(tpl, MON, _state(), _Config()) is True


def test_module_gate_fires_when_in_range():
    tpl = _template([{"type": "module_gte", "value": 3}])
    assert should_create_today(tpl, MON, _state(current_module=5), _Config()) is True


def test_module_gate_skips_when_below():
    tpl = _template([{"type": "module_gte", "value": 10}])
    assert should_create_today(tpl, MON, _state(current_module=5), _Config()) is False


def test_track_gate_fires_when_current():
    tpl = _template([
        {"type": "track", "category": "Courses", "item": "X"},
    ])
    s = _state(learning_tracks={"Courses": {"X": "current"}})
    assert should_create_today(tpl, MON, s, _Config()) is True


def test_track_gate_skips_when_done():
    tpl = _template([
        {"type": "track", "category": "Courses", "item": "X"},
    ])
    s = _state(learning_tracks={"Courses": {"X": "done"}})
    assert should_create_today(tpl, MON, s, _Config()) is False


def test_anded_gates_both_must_pass():
    tpl = _template([
        {"type": "track", "category": "Courses", "item": "X"},
        {"type": "module_gte", "value": 3},
    ])
    s = _state(current_module=5, learning_tracks={"Courses": {"X": "current"}})
    assert should_create_today(tpl, MON, s, _Config()) is True
    s2 = _state(current_module=2, learning_tracks={"Courses": {"X": "current"}})
    assert should_create_today(tpl, MON, s2, _Config()) is False


def test_paused_state_wins_over_gates():
    """Paused short stays above gated_by (no need to even evaluate)."""
    tpl = _template([{"type": "module_gte", "value": 0}])  # always-true gate
    assert should_create_today(tpl, MON, _state(paused=True), _Config()) is False
