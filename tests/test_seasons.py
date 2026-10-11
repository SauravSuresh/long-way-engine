from datetime import date
from pathlib import Path

from src.seasons import (
    MilestoneProgress,
    SeasonsState,
    SyllabusFacts,
    load_seasons,
    load_seasons_state,
    save_seasons_state,
    validate,
)

OWNER_YAML = """
todoist_project_id: "p1"
rhythm:
  sleep: {from: "22:30", to: "06:00"}
  fixed_hours: {from: "09:30", to: "18:30", days: [monday, tuesday, wednesday, thursday, friday]}
  shutdown: "21:00"
  rest_week: true
  deep_blocks:
    monday:   {start: "07:30", minutes: 90, lane: main}
    tuesday:  {start: "07:30", minutes: 90, lane: side}
    saturday: {start: "07:30", minutes: 210}
bucket:
  - id: marketplace-rungs-1-5
    name: Marketplace rungs 1-5
    area: Work
    hours: 200
    syllabus: marketplace-builder
    modules: [1, 5]
    pin_start: 2026-10-20
  - id: aws-saa
    name: AWS SAA
    area: Learning
    hours: 40
    lane: side
    syllabus: devops-ready
    track: {category: Certifications, item: AWS Solutions Architect Associate}
  - id: previz-product
    name: Previz product
    area: Work
    hours: 100
disciplines:
  - id: anki
    name: "Anki - {milestone}"
    minutes: 20
    start: "07:15"
"""

FACTS = {
    "marketplace-builder": SyllabusFacts(True, frozenset(), 16),
    "devops-ready": SyllabusFacts(True, frozenset({("Certifications", "AWS Solutions Architect Associate")}), 13),
    "long-way": SyllabusFacts(False, frozenset(), 23),
}


def _owner(tmp_path: Path, text: str = OWNER_YAML):
    p = tmp_path / "seasons.yaml"
    p.write_text(text)
    return load_seasons(p)


def test_load_owner_file(tmp_path):
    s = _owner(tmp_path)
    assert s.todoist_project_id == "p1"
    assert s.two_lanes
    assert set(s.rhythm.deep_blocks) == {"monday", "tuesday", "saturday"}
    assert s.rhythm.deep_blocks["saturday"].lane == "main"
    mb, aws, previz = s.bucket
    assert mb.modules == (1, 5) and mb.pin_start == date(2026, 10, 20) and not mb.bare
    assert aws.track == ("Certifications", "AWS Solutions Architect Associate") and aws.lane == "side"
    assert previz.bare
    assert s.disciplines[0].days == ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    assert validate(s, SeasonsState(), FACTS) == ([], [])


def test_lanes_implied_by_side_block(tmp_path):
    s = _owner(tmp_path, OWNER_YAML.replace("lane: side}", "lane: main}"))
    assert not s.two_lanes


def test_validation_errors(tmp_path):
    bad = OWNER_YAML.replace("id: previz-product", "id: Previz Product").replace(
        "    modules: [1, 5]\n", "    modules: [1, 99]\n    track: {category: X, item: Y}\n"
    ).replace("syllabus: devops-ready", "syllabus: long-way")
    errors, _ = validate(_owner(tmp_path, bad), SeasonsState(), FACTS)
    joined = "\n".join(errors)
    assert "id must be a slug" in joined
    assert "at most one of track / modules" in joined
    assert "outside 1..16" in joined
    assert "disabled in config.yaml" in joined
    assert "not declared by 'long-way'" in joined


def test_unknown_syllabus_and_bare_with_binding(tmp_path):
    bad = OWNER_YAML.replace("syllabus: marketplace-builder", "syllabus: nope").replace(
        "    hours: 100\n", "    hours: 100\n    modules: [1, 2]\n"
    )
    errors, _ = validate(_owner(tmp_path, bad), SeasonsState(), FACTS)
    assert any("unknown syllabus 'nope'" in e for e in errors)
    assert any("need a syllabus" in e for e in errors)


def test_state_roundtrip_and_orphan_warning(tmp_path):
    p = tmp_path / "state" / "seasons.yaml"
    assert load_seasons_state(p) == SeasonsState()
    st = SeasonsState(
        milestones={"aws-saa": MilestoneProgress({date(2026, 10, 13): 90, date(2026, 10, 14): 90}, None), "ghost": MilestoneProgress({}, date(2026, 1, 1))},
        rest_until=date(2026, 12, 7),
        last_run={"main": "aws-saa", "side": None, "resting": False},
    )
    save_seasons_state(p, st)
    back = load_seasons_state(p)
    assert back == st
    assert back.milestones["aws-saa"].logged_minutes == 180
    _, warnings = validate(_owner(tmp_path), back, FACTS)
    assert warnings == ["state.milestones[ghost]: not in bucket (orphan)"]
