"""Tests for derive_month / derive_phase / update_derived_fields."""

from __future__ import annotations

from datetime import date

from zoneinfo import ZoneInfo

from src.state import PauseInterval, State, derive_month, derive_phase, update_derived_fields
from src.syllabus import Module, Phase, Syllabus


def _state(start, paused_intervals=None):
    return State(
        start_date=start,
        timezone=ZoneInfo("UTC"),
        phase=1,
        month=1,
        current_module=1,
        current_book="",
        pause_history=paused_intervals or [],
    )


def _syllabus(phase_ranges):
    return Syllabus(
        meta={},
        phases=[
            Phase(number=i + 1, name=f"P{i + 1}", months=(lo, hi))
            for i, (lo, hi) in enumerate(phase_ranges)
        ],
        books=[],
        primary_book_by_month={},
        modules=[],
    )


def test_derive_month_day_zero_is_month_one():
    s = _state(date(2026, 5, 1))
    assert derive_month(s, date(2026, 5, 1)) == 1


def test_derive_month_day_29_still_month_one():
    s = _state(date(2026, 5, 1))
    assert derive_month(s, date(2026, 5, 30)) == 1


def test_derive_month_day_30_is_month_two():
    s = _state(date(2026, 5, 1))
    assert derive_month(s, date(2026, 5, 31)) == 2


def test_derive_month_excludes_closed_pause_intervals():
    s = _state(
        date(2026, 5, 1),
        paused_intervals=[
            PauseInterval(start=date(2026, 5, 10), end=date(2026, 5, 25), reason="vacation"),
        ],
    )
    # 30 days elapsed minus 15 pause days = 15 effective; month 1.
    assert derive_month(s, date(2026, 5, 31)) == 1


def test_derive_month_negative_elapsed_returns_one():
    s = _state(date(2026, 6, 1))
    assert derive_month(s, date(2026, 5, 1)) == 1


def test_derive_phase_lookup_within_range():
    syl = _syllabus([(1, 3), (4, 8), (9, 12)])
    assert derive_phase(1, syl) == 1
    assert derive_phase(3, syl) == 1
    assert derive_phase(4, syl) == 2
    assert derive_phase(8, syl) == 2
    assert derive_phase(9, syl) == 3
    assert derive_phase(12, syl) == 3


def test_derive_phase_beyond_last_phase_returns_last():
    syl = _syllabus([(1, 3), (4, 8)])
    assert derive_phase(99, syl) == 2


def test_update_derived_fields_replaces_month_and_phase():
    s = _state(date(2026, 5, 1))
    syl = _syllabus([(1, 3), (4, 8)])
    new = update_derived_fields(s, syl, date(2026, 9, 1))  # 123 days elapsed → month 5
    assert new.month == 5
    assert new.phase == 2
    # Original state untouched (immutability via replace).
    assert s.month == 1
