from pathlib import Path
from zoneinfo import ZoneInfo

from src.state import SharedState, load_shared_state, save_shared_state


def test_load_shared_state_basic(tmp_path: Path):
    p = tmp_path / "shared.yaml"
    p.write_text(
        "timezone: Asia/Kolkata\n"
        "manual_counters:\n"
        "  anki_card_count: 42\n"
        "  prs_opened: 3\n"
        "  traces_completed: 1\n"
        "  lineage_detours_done: []\n"
        "notes: |\n"
        "  hello\n"
    )
    s = load_shared_state(p)
    assert isinstance(s, SharedState)
    assert s.timezone == ZoneInfo("Asia/Kolkata")
    assert s.manual_counters["anki_card_count"] == 42
    assert s.manual_counters["prs_opened"] == 3
    assert s.notes.strip() == "hello"


def test_load_shared_state_defaults(tmp_path: Path):
    p = tmp_path / "shared.yaml"
    p.write_text("timezone: UTC\n")
    s = load_shared_state(p)
    assert s.manual_counters == {}
    assert s.notes == ""


def test_load_shared_state_missing_file(tmp_path: Path):
    import pytest

    p = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError):
        load_shared_state(p)


def test_load_shared_state_invalid_timezone(tmp_path: Path):
    import pytest

    p = tmp_path / "shared.yaml"
    p.write_text("timezone: Mars/Olympus\n")
    with pytest.raises(ValueError) as exc:
        load_shared_state(p)
    assert "Mars/Olympus" in str(exc.value)


def test_save_shared_state_round_trips(tmp_path):
    from zoneinfo import ZoneInfo
    from src.state import SharedState, save_shared_state, load_shared_state
    s = SharedState(
        timezone=ZoneInfo("Asia/Kolkata"),
        manual_counters={"anki_card_count": 42, "prs_opened": 3},
        notes="hi",
    )
    p = tmp_path / "shared.yaml"
    save_shared_state(p, s)
    s2 = load_shared_state(p)
    assert s2.timezone == ZoneInfo("Asia/Kolkata")
    assert s2.manual_counters["anki_card_count"] == 42
    assert s2.notes == "hi"
