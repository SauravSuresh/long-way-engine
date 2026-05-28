from pathlib import Path
import pytest


def test_build_rows_collision_detected():
    from scripts.show_timetable import TimetableRow, find_collisions
    rows = [
        TimetableRow(time="10:00", weekdays={"Sat"}, syllabus="long-way", ritual="weekly_state_review"),
        TimetableRow(time="10:00", weekdays={"Sat"}, syllabus="job-readiness", ritual="weekly_state_review"),
    ]
    cols = find_collisions(rows)
    assert len(cols) == 1
    assert cols[0].time == "10:00"
    assert cols[0].weekday == "Sat"


def test_find_collisions_no_collision_different_times():
    from scripts.show_timetable import TimetableRow, find_collisions
    rows = [
        TimetableRow(time="06:00", weekdays={"Mon", "Tue"}, syllabus="long-way", ritual="morning_reading"),
        TimetableRow(time="13:00", weekdays={"Mon", "Tue"}, syllabus="job-readiness", ritual="morning_reading"),
    ]
    assert find_collisions(rows) == []


def test_find_collisions_same_syllabus_same_slot_is_not_a_collision():
    """Two templates in the same syllabus at the same time are fine — it's a per-syllabus authoring choice."""
    from scripts.show_timetable import TimetableRow, find_collisions
    rows = [
        TimetableRow(time="06:00", weekdays={"Mon"}, syllabus="long-way", ritual="morning_reading"),
        TimetableRow(time="06:00", weekdays={"Mon"}, syllabus="long-way", ritual="morning_meditation"),
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

    # NOTE: load_multi_syllabus_config will raise SlotCollisionError because both syllabuses
    # claim weekly_state_review at 10:00. The visualizer needs to either:
    #  (a) catch SlotCollisionError, still print the timetable from the raw config,
    #      and exit non-zero with a clear message; OR
    #  (b) bypass load_multi_syllabus_config's slot-collision check and do its own.
    # Pick (b): the visualizer's whole point is to show collisions visually, so it must
    # tolerate them. Add a kwarg or use a "lenient" loader path.

    from scripts.show_timetable import main
    rc = main(["--config", str(cfg), "--env", str(tmp_path / ".env"), "--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc != 0
    assert "COLLISION" in out or "collision" in out.lower()


def test_main_exits_zero_when_no_collision(tmp_path, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "ritual_times:\n  morning_reading: '06:00'\n"
        "priority_order: [a]\n"
        "syllabuses:\n"
        "  a:\n    path: curricula/a\n    todoist_project_id: '1'\n    state_file: state/a.yaml\n    enabled: true\n"
        "dashboard:\n  github_username: u\n  repo_name: r\n"
    )
    (tmp_path / ".env").write_text("TODOIST_TOKEN=x\n")
    (tmp_path / "curricula" / "a" / "rituals").mkdir(parents=True)
    (tmp_path / "curricula" / "a" / "rituals" / "daily.yaml").write_text(
        "- id: daily-morning\n  cadence: daily\n  ritual_time: morning_reading\n  title: read\n"
    )
    from scripts.show_timetable import main
    rc = main(["--config", str(cfg), "--env", str(tmp_path / ".env"), "--repo-root", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "morning_reading" in out
    assert "06:00" in out
