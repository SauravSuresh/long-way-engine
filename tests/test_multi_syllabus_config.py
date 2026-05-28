from pathlib import Path

import pytest

from src.config import (
    MultiSyllabusConfig,
    SyllabusEntry,
    SlotCollisionError,
    load_multi_syllabus_config,
)


BASE_YAML = """
ritual_times:
  morning_reading: "06:00"
  anki: "08:30"
  evening_hands_on: "19:00"
  weekly_state_review: "10:00"
priority_order:
  - long-way
syllabuses:
  long-way:
    path: curricula/long-way
    todoist_project_id: "111"
    state_file: state/long-way.yaml
    enabled: true
sunday_off: true
dashboard:
  github_username: "foo"
  repo_name: "long-way-engine"
"""


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content)
    env = tmp_path / ".env"
    env.write_text("TODOIST_TOKEN=abc\n")
    return p


def test_load_single_syllabus(tmp_path: Path):
    p = _write(tmp_path, BASE_YAML)
    cfg = load_multi_syllabus_config(p, tmp_path / ".env")
    assert isinstance(cfg, MultiSyllabusConfig)
    assert cfg.priority_order == ["long-way"]
    assert "long-way" in cfg.syllabuses
    sy = cfg.syllabuses["long-way"]
    assert isinstance(sy, SyllabusEntry)
    assert sy.todoist_project_id == "111"
    assert sy.enabled is True
    # Effective ritual_times = top-level when no override.
    assert sy.ritual_times["morning_reading"] == "06:00"


def test_per_syllabus_override_merges_with_top_level(tmp_path: Path):
    yaml = BASE_YAML.replace(
        "    enabled: true\n",
        "    enabled: true\n    ritual_times:\n      morning_reading: \"13:00\"\n",
    )
    p = _write(tmp_path, yaml)
    cfg = load_multi_syllabus_config(p, tmp_path / ".env")
    sy = cfg.syllabuses["long-way"]
    assert sy.ritual_times["morning_reading"] == "13:00"  # overridden
    assert sy.ritual_times["anki"] == "08:30"             # inherited


def test_priority_order_must_match_enabled_set(tmp_path: Path):
    # priority_order names a syllabus that isn't declared.
    yaml = BASE_YAML.replace(
        "  - long-way\n",
        "  - long-way\n  - ghost\n",
    )
    p = _write(tmp_path, yaml)
    with pytest.raises(ValueError, match="priority_order"):
        load_multi_syllabus_config(p, tmp_path / ".env")


def test_slot_collision_errors(tmp_path: Path):
    # Two syllabuses both at morning_reading 06:00, neither allows overlap.
    yaml = (BASE_YAML
        .replace("  - long-way\n", "  - long-way\n  - job-readiness\n")
        .replace(
            "  long-way:\n    path: curricula/long-way\n    todoist_project_id: \"111\"\n    state_file: state/long-way.yaml\n    enabled: true\n",
            "  long-way:\n    path: curricula/long-way\n    todoist_project_id: \"111\"\n    state_file: state/long-way.yaml\n    enabled: true\n"
            "  job-readiness:\n    path: curricula/job-readiness\n    todoist_project_id: \"222\"\n    state_file: state/job-readiness.yaml\n    enabled: true\n",
        )
    )
    p = _write(tmp_path, yaml)
    with pytest.raises(SlotCollisionError):
        load_multi_syllabus_config(p, tmp_path / ".env")


def test_slot_collision_suppressed_by_allow_slot_overlap(tmp_path: Path):
    yaml = (BASE_YAML
        .replace("  - long-way\n", "  - long-way\n  - job-readiness\n")
        .replace(
            "    enabled: true\n",
            "    enabled: true\n    allow_slot_overlap: true\n",
            1,  # only on the first occurrence (long-way)
        )
        .replace(
            "  long-way:\n",
            "  job-readiness:\n    path: curricula/job-readiness\n    todoist_project_id: \"222\"\n    state_file: state/job-readiness.yaml\n    enabled: true\n  long-way:\n",
        )
    )
    p = _write(tmp_path, yaml)
    cfg = load_multi_syllabus_config(p, tmp_path / ".env")  # must not raise
    assert "job-readiness" in cfg.syllabuses


def test_disabled_syllabus_skipped_for_collisions(tmp_path: Path):
    yaml = (BASE_YAML
        .replace(
            "  long-way:\n",
            "  job-readiness:\n    path: curricula/job-readiness\n    todoist_project_id: \"222\"\n    state_file: state/job-readiness.yaml\n    enabled: false\n  long-way:\n",
        )
    )
    p = _write(tmp_path, yaml)
    cfg = load_multi_syllabus_config(p, tmp_path / ".env")  # must not raise
    assert cfg.syllabuses["job-readiness"].enabled is False
