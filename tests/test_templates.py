from datetime import date
from pathlib import Path

import pytest
from zoneinfo import ZoneInfo

from src.config import Config, DashboardConfig, TodoistConfig
from src.state import State
from src.templates import Template, load_templates, resolve_string, resolve_variables

TPL_YAML = """
- id: daily-morning-reading
  title: "Morning reading: {current_book}"
  description: "Read {current_book} for 30 min."
  due: "today at {ritual_times.morning_reading}"
  labels: [daily-ritual]
  cadence: daily
  skip_if: sunday

- id: daily-anki
  title: "Anki review"
  description: "10-15 min."
  due: "today at {ritual_times.anki}"
  labels: [daily-ritual]
  cadence: daily
  skip_if: sunday
"""


def make_state() -> State:
    return State(
        start_date=date(2026, 5, 4),
        timezone=ZoneInfo("Asia/Kolkata"),
        phase=1,
        month=1,
        current_module=1,
        current_book="CSAPP",
    )


def make_config() -> Config:
    return Config(
        todoist=TodoistConfig(project_id="1", labels={"daily": "daily-ritual"}),
        ritual_times={"morning_reading": "06:00", "anki": "08:30"},
        sunday_off=True,
        dashboard=DashboardConfig(github_username="u", repo_name="r"),
        todoist_token="t",
    )


def test_load_templates_reads_directory(tmp_path: Path):
    (tmp_path / "daily.yaml").write_text(TPL_YAML)
    out = load_templates(tmp_path)
    assert [t.id for t in out] == ["daily-morning-reading", "daily-anki"]


def test_load_template_parses_day_of_week(tmp_path: Path):
    (tmp_path / "weekly.yaml").write_text(
        """
- id: weekly-friday
  title: "x"
  due: "today"
  labels: []
  cadence: weekly
  day_of_week: friday
"""
    )
    [t] = load_templates(tmp_path)
    assert t.day_of_week == "friday"
    assert t.day_of_month is None


def test_load_template_parses_day_of_month_int(tmp_path: Path):
    (tmp_path / "monthly.yaml").write_text(
        """
- id: monthly-blog
  title: "x"
  due: "today"
  labels: []
  cadence: monthly
  day_of_month: 1
"""
    )
    [t] = load_templates(tmp_path)
    assert t.day_of_month == 1
    assert isinstance(t.day_of_month, int)


def test_load_template_parses_day_of_month_string(tmp_path: Path):
    (tmp_path / "monthly.yaml").write_text(
        """
- id: monthly-retrieval
  title: "x"
  due: "today"
  labels: []
  cadence: monthly
  day_of_month: last-saturday
"""
    )
    [t] = load_templates(tmp_path)
    assert t.day_of_month == "last-saturday"


def test_load_template_parses_module_number(tmp_path: Path):
    (tmp_path / "modules.yaml").write_text(
        """
- id: module-06-onboarding
  title: "x"
  due: "today"
  labels: []
  cadence: once-per-module
  module_number: 6
"""
    )
    [t] = load_templates(tmp_path)
    assert t.module_number == 6
    assert isinstance(t.module_number, int)


def test_load_template_module_number_defaults_to_none(tmp_path: Path):
    (tmp_path / "daily.yaml").write_text(
        """
- id: daily-anki
  title: "x"
  due: "today"
  labels: []
  cadence: daily
"""
    )
    [t] = load_templates(tmp_path)
    assert t.module_number is None


def test_load_template_keeps_reflection_block_in_raw(tmp_path: Path):
    """Phase C will read reflection.create_stub from raw; Phase B leaves it alone."""
    (tmp_path / "weekly.yaml").write_text(
        """
- id: weekly-friday
  title: "x"
  due: "today"
  labels: []
  cadence: weekly
  day_of_week: friday
  reflection:
    create_stub: true
    stub_path: "reflections/weekly/{iso_year}-W{iso_week:02d}.md"
    template: weekly_review_template
"""
    )
    [t] = load_templates(tmp_path)
    assert t.raw["reflection"]["create_stub"] is True
    assert t.raw["reflection"]["stub_path"].startswith("reflections/weekly/")


def test_resolve_current_book_and_ritual_time(tmp_path: Path):
    (tmp_path / "daily.yaml").write_text(TPL_YAML)
    state, config = make_state(), make_config()
    templates = load_templates(tmp_path)
    today = date(2026, 5, 4)

    morning = resolve_variables(templates[0], state, config, today)
    assert morning is not None
    assert morning.title == "Morning reading: CSAPP"
    assert "CSAPP" in morning.description
    assert morning.due == "today at 06:00"

    anki = resolve_variables(templates[1], state, config, today)
    assert anki is not None
    assert anki.due == "today at 08:30"


def test_missing_variable_returns_none_and_warns(caplog):
    bad = Template(
        id="x",
        title="hello {nonexistent}",
        description="",
        due="",
        labels=[],
        cadence="daily",
    )
    out = resolve_variables(bad, make_state(), make_config(), date(2026, 5, 4))
    assert out is None
    assert any("missing variable" in r.message for r in caplog.records)


def test_missing_ritual_time_returns_none(caplog):
    bad = Template(
        id="x",
        title="t",
        description="",
        due="today at {ritual_times.unknown}",
        labels=[],
        cadence="daily",
    )
    assert resolve_variables(bad, make_state(), make_config(), date(2026, 5, 4)) is None


# ---------------------------------------------------------------------------
# Date-derived placeholders (Phase C)
# ---------------------------------------------------------------------------


def test_resolve_year():
    assert resolve_string("{year}", make_state(), make_config(), date(2026, 5, 4)) == "2026"


def test_resolve_month_padded():
    assert resolve_string("{month:02d}", make_state(), make_config(), date(2026, 5, 4)) == "05"


def test_resolve_month_unpadded():
    assert resolve_string("{month}", make_state(), make_config(), date(2026, 5, 4)) == "5"


def test_resolve_date():
    assert resolve_string("{date}", make_state(), make_config(), date(2026, 5, 4)) == "2026-05-04"


def test_resolve_iso_year_iso_week_calendar_year_boundary():
    """2027-01-01 is Friday but ISO week 53 of 2026."""
    out = resolve_string(
        "{iso_year}-W{iso_week:02d}", make_state(), make_config(), date(2027, 1, 1)
    )
    assert out == "2026-W53"


def test_resolve_iso_year_iso_week_normal():
    out = resolve_string(
        "{iso_year}-W{iso_week:02d}", make_state(), make_config(), date(2026, 5, 8)
    )
    assert out == "2026-W19"


@pytest.mark.parametrize(
    "month,expected",
    [(1, "1"), (3, "1"), (4, "2"), (6, "2"), (7, "3"), (9, "3"), (10, "4"), (12, "4")],
)
def test_resolve_quarter_boundaries(month, expected):
    out = resolve_string("{quarter}", make_state(), make_config(), date(2026, month, 15))
    assert out == expected


def test_resolve_combined_path():
    """A real stub_path resolves end to end."""
    out = resolve_string(
        "reflections/weekly/{iso_year}-W{iso_week:02d}.md",
        make_state(),
        make_config(),
        date(2026, 5, 8),
    )
    assert out == "reflections/weekly/2026-W19.md"


# ---------------------------------------------------------------------------
# current_book fallback chain (Phase D)
# ---------------------------------------------------------------------------


def test_current_book_state_override_wins():
    """state.current_book non-empty short-circuits the syllabus fallback."""
    state = make_state()
    state.current_book = "Some Override"
    state.month = 7  # would otherwise resolve to Networking
    out = resolve_string("{current_book}", state, make_config(), date(2026, 5, 4))
    assert out == "Some Override"


def test_current_book_falls_back_to_syllabus_when_state_empty():
    state = make_state()
    state.current_book = ""
    state.month = 1
    out = resolve_string("{current_book}", state, make_config(), date(2026, 5, 4))
    assert out == "Computer Systems: A Programmer's Perspective"


def test_current_book_syllabus_month_7_networking():
    state = make_state()
    state.current_book = ""
    state.month = 7
    out = resolve_string("{current_book}", state, make_config(), date(2026, 5, 4))
    assert out == "Computer Networking: A Top-Down Approach"


def test_current_book_carry_forward_in_book_less_month():
    state = make_state()
    state.current_book = ""
    state.month = 11  # no main book in syllabus; carry-forward
    out = resolve_string("{current_book}", state, make_config(), date(2026, 5, 4))
    assert out == "Computer Networking: A Top-Down Approach"
