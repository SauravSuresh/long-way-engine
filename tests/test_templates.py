from datetime import date
from pathlib import Path

from zoneinfo import ZoneInfo

from src.config import Config, DashboardConfig, TodoistConfig
from src.state import State
from src.templates import Template, load_templates, resolve_variables

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


def test_resolve_current_book_and_ritual_time(tmp_path: Path):
    (tmp_path / "daily.yaml").write_text(TPL_YAML)
    state, config = make_state(), make_config()
    templates = load_templates(tmp_path)

    morning = resolve_variables(templates[0], state, config)
    assert morning is not None
    assert morning.title == "Morning reading: CSAPP"
    assert "CSAPP" in morning.description
    assert morning.due == "today at 06:00"

    anki = resolve_variables(templates[1], state, config)
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
    out = resolve_variables(bad, make_state(), make_config())
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
    assert resolve_variables(bad, make_state(), make_config()) is None
