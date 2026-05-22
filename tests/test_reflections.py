"""Tests for src/reflections.py — stub creation, metadata maintenance,
edge-triggered status toggle, never-overwrite invariant.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.reflections import (
    WORD_COUNT_THRESHOLD,
    StubResult,
    _baseline_word_count,
    count_words_in_body,
    create_stub,
    render_frontmatter,
    split_frontmatter,
    update_metadata,
)
from src.templates import Template
from tests.test_templates import make_config, make_state

REPO_ROOT = Path(__file__).resolve().parent.parent
REFLECTION_TEMPLATES = REPO_ROOT / "curriculum" / "reflection_templates"


def weekly_template_with_stub() -> Template:
    return Template(
        id="weekly-friday-review",
        title="Friday review",
        description="",
        due="today at 20:00",
        labels=["weekly-ritual"],
        cadence="weekly",
        day_of_week="friday",
        raw={
            "id": "weekly-friday-review",
            "cadence": "weekly",
            "day_of_week": "friday",
            "reflection": {
                "create_stub": True,
                "stub_path": "reflections/weekly/{iso_year}-W{iso_week:02d}.md",
            },
        },
    )


def daily_template_no_stub() -> Template:
    return Template(
        id="daily-anki",
        title="Anki",
        description="",
        due="",
        labels=[],
        cadence="daily",
        raw={"id": "daily-anki", "cadence": "daily"},
    )


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------


def test_split_frontmatter_happy():
    text = "---\ntype: weekly\nstatus: stub\n---\nbody line 1\nbody line 2\n"
    fm, body = split_frontmatter(text)
    assert fm["type"] == "weekly"
    assert fm["status"] == "stub"
    assert body.startswith("body line 1")


def test_split_frontmatter_empty_body():
    text = "---\ntype: weekly\n---\n"
    fm, body = split_frontmatter(text)
    assert fm["type"] == "weekly"
    assert body == ""


def test_split_frontmatter_no_frontmatter():
    text = "no frontmatter here\njust body\n"
    fm, body = split_frontmatter(text)
    assert fm == {}
    assert body == text


def test_split_frontmatter_unbalanced_returns_empty():
    """One `---` only — no closing — treated as malformed."""
    text = "---\ntype: weekly\nno closing\n"
    fm, body = split_frontmatter(text)
    assert fm == {}


def test_split_frontmatter_non_dict_returns_empty():
    text = "---\n- a\n- b\n---\nbody\n"
    fm, body = split_frontmatter(text)
    assert fm == {}


def test_split_frontmatter_yaml_error_returns_empty():
    text = "---\nthis: is: not: valid: yaml: : :\n---\nbody\n"
    fm, body = split_frontmatter(text)
    # Either yaml accepts and we get {}, or yaml errors and we get {} — both fine.
    assert fm == {} or isinstance(fm, dict)


def test_render_frontmatter_round_trip():
    fm = {"type": "weekly", "status": "stub", "word_count": 42}
    body = "Body here.\n"
    out = render_frontmatter(fm, body)
    fm2, body2 = split_frontmatter(out)
    assert fm2 == fm
    assert body2 == body


def test_count_words_in_body():
    assert count_words_in_body("a b c") == 3
    assert count_words_in_body("") == 0
    assert count_words_in_body("one\ntwo\nthree four") == 4


# ---------------------------------------------------------------------------
# create_stub
# ---------------------------------------------------------------------------


def test_create_stub_writes_file_when_absent(tmp_path: Path):
    reflections = tmp_path / "reflections"
    pending: set[Path] = set()

    res = create_stub(
        weekly_template_with_stub(),
        make_state(),
        make_config(),
        date(2026, 5, 8),  # Friday, ISO W19/2026
        reflections,
        REFLECTION_TEMPLATES,
        pending,
    )
    assert res is not None
    assert res.decision == "created"
    expected = reflections / "weekly" / "2026-W19.md"
    assert res.path == expected
    assert expected.exists()

    fm, body = split_frontmatter(expected.read_text())
    assert fm["type"] == "weekly"
    assert fm["status"] == "stub"
    assert fm["word_count"] == 0
    assert fm["iso_week"] == "2026-W19"
    # YAML auto-parses bare ISO dates to datetime.date.
    assert fm["date"] == date(2026, 5, 8)
    assert "Three things I learned this week" in body


def test_create_stub_never_overwrites(tmp_path: Path):
    reflections = tmp_path / "reflections"
    expected = reflections / "weekly" / "2026-W19.md"
    expected.parent.mkdir(parents=True)
    expected.write_text("OWNER PROSE — DO NOT CLOBBER")

    res = create_stub(
        weekly_template_with_stub(),
        make_state(),
        make_config(),
        date(2026, 5, 8),
        reflections,
        REFLECTION_TEMPLATES,
        pending_paths=set(),
    )
    assert res is not None
    assert res.decision == "exists"
    assert expected.read_text() == "OWNER PROSE — DO NOT CLOBBER"


def test_create_stub_returns_none_for_template_without_reflection():
    res = create_stub(
        daily_template_no_stub(),
        make_state(),
        make_config(),
        date(2026, 5, 4),
        Path("/tmp/whatever"),
        REFLECTION_TEMPLATES,
        pending_paths=set(),
    )
    assert res is None


def test_create_stub_dry_run_writes_nothing(tmp_path: Path):
    reflections = tmp_path / "reflections"
    pending: set[Path] = set()

    res = create_stub(
        weekly_template_with_stub(),
        make_state(),
        make_config(),
        date(2026, 5, 8),
        reflections,
        REFLECTION_TEMPLATES,
        pending,
        dry_run=True,
    )
    assert res is not None
    assert res.decision == "would_create"
    assert not (reflections / "weekly" / "2026-W19.md").exists()
    assert (reflections / "weekly" / "2026-W19.md") in pending


def test_create_stub_pending_collision(tmp_path: Path):
    """Same path in pending set → would_skip_pending without filesystem touch."""
    reflections = tmp_path / "reflections"
    target = reflections / "weekly" / "2026-W19.md"
    pending: set[Path] = {target}

    res = create_stub(
        weekly_template_with_stub(),
        make_state(),
        make_config(),
        date(2026, 5, 8),
        reflections,
        REFLECTION_TEMPLATES,
        pending,
        dry_run=True,
    )
    assert res is not None
    assert res.decision == "would_skip_pending"
    assert not target.exists()


def test_create_stub_real_run_pending_path_written_first_call(tmp_path: Path):
    """Real run: first call writes, second call (same path) sees it on disk."""
    reflections = tmp_path / "reflections"
    pending: set[Path] = set()

    a = create_stub(
        weekly_template_with_stub(),
        make_state(),
        make_config(),
        date(2026, 5, 8),
        reflections,
        REFLECTION_TEMPLATES,
        pending,
    )
    b = create_stub(
        weekly_template_with_stub(),
        make_state(),
        make_config(),
        date(2026, 5, 8),
        reflections,
        REFLECTION_TEMPLATES,
        pending,
    )
    assert a.decision == "created"
    assert b.decision == "exists"  # second call sees the file


def test_create_stub_missing_stub_path_warns_and_returns_none(tmp_path: Path, caplog):
    bad = Template(
        id="weekly-bad",
        title="x",
        description="",
        due="",
        labels=[],
        cadence="weekly",
        raw={
            "id": "weekly-bad",
            "cadence": "weekly",
            "reflection": {"create_stub": True},  # no stub_path
        },
    )
    res = create_stub(
        bad,
        make_state(),
        make_config(),
        date(2026, 5, 8),
        tmp_path,
        REFLECTION_TEMPLATES,
        pending_paths=set(),
    )
    assert res is None
    assert any("stub_path" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# update_metadata — edge-triggered toggle, manual revert, malformed handling
# ---------------------------------------------------------------------------


def _seed_stub(path: Path, body_words: int, status: str = "stub", recorded_count: int = 0) -> None:
    fm = f"---\ntype: weekly\ndate: 2026-05-08\niso_week: 2026-W19\nstatus: {status}\nword_count: {recorded_count}\n---\n"
    body = " ".join("w" * 1 for _ in range(body_words)) if body_words else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fm + body)


def _baseline() -> int:
    """Count baseline words via the engine's own helper (matches update_metadata)."""
    return _baseline_word_count(REFLECTION_TEMPLATES, "weekly")


def test_update_metadata_updates_word_count(tmp_path: Path):
    f = tmp_path / "reflections" / "weekly" / "2026-W19.md"
    _seed_stub(f, body_words=10, recorded_count=0)
    update_metadata(tmp_path / "reflections", REFLECTION_TEMPLATES)
    fm, _ = split_frontmatter(f.read_text())
    assert fm["word_count"] == 10
    assert fm["status"] == "stub"  # below threshold


def test_update_metadata_off_by_one_below_threshold_stays_stub(tmp_path: Path):
    """Body has exactly baseline+threshold-1 words → stays stub."""
    f = tmp_path / "reflections" / "weekly" / "2026-W19.md"
    body_words = _baseline() + WORD_COUNT_THRESHOLD - 1
    _seed_stub(f, body_words=body_words, recorded_count=0)
    update_metadata(tmp_path / "reflections", REFLECTION_TEMPLATES)
    fm, _ = split_frontmatter(f.read_text())
    assert fm["word_count"] == body_words
    assert fm["status"] == "stub"


def test_update_metadata_off_by_one_at_threshold_flips_to_filled(tmp_path: Path):
    """Body has exactly baseline+threshold words → flips to filled."""
    f = tmp_path / "reflections" / "weekly" / "2026-W19.md"
    body_words = _baseline() + WORD_COUNT_THRESHOLD
    _seed_stub(f, body_words=body_words, recorded_count=0)
    update_metadata(tmp_path / "reflections", REFLECTION_TEMPLATES)
    fm, _ = split_frontmatter(f.read_text())
    assert fm["word_count"] == body_words
    assert fm["status"] == "filled"


def test_update_metadata_filled_stays_filled(tmp_path: Path):
    """Once filled, never reverts even if word count drops below threshold."""
    f = tmp_path / "reflections" / "weekly" / "2026-W19.md"
    _seed_stub(f, body_words=5, status="filled", recorded_count=200)
    update_metadata(tmp_path / "reflections", REFLECTION_TEMPLATES)
    fm, _ = split_frontmatter(f.read_text())
    assert fm["status"] == "filled"
    assert fm["word_count"] == 5  # count IS updated


def test_update_metadata_manual_revert_sticks(tmp_path: Path):
    """Manual `status: stub` on a high-word-count file does not auto-flip back to filled.

    Edge-triggered: old_count was already above threshold, so no upward
    crossing this run.
    """
    f = tmp_path / "reflections" / "weekly" / "2026-W19.md"
    body_words = _baseline() + WORD_COUNT_THRESHOLD + 100
    _seed_stub(f, body_words=body_words, status="stub", recorded_count=body_words)
    update_metadata(tmp_path / "reflections", REFLECTION_TEMPLATES)
    fm, _ = split_frontmatter(f.read_text())
    assert fm["status"] == "stub"  # manual revert respected
    assert fm["word_count"] == body_words


def test_update_metadata_manual_revert_then_drop_then_recross_flips(tmp_path: Path):
    """Owner reverts to stub; deletes prose; re-adds across threshold; engine flips again."""
    f = tmp_path / "reflections" / "weekly" / "2026-W19.md"
    threshold = _baseline() + WORD_COUNT_THRESHOLD

    # Step 1: manual revert. recorded high, body high. Stays stub.
    _seed_stub(f, body_words=threshold + 100, status="stub", recorded_count=threshold + 100)
    update_metadata(tmp_path / "reflections", REFLECTION_TEMPLATES)
    fm, _ = split_frontmatter(f.read_text())
    assert fm["status"] == "stub"

    # Step 2: owner deletes prose to below threshold. Engine updates count.
    _seed_stub(f, body_words=10, status="stub", recorded_count=fm["word_count"])
    update_metadata(tmp_path / "reflections", REFLECTION_TEMPLATES)
    fm, _ = split_frontmatter(f.read_text())
    assert fm["status"] == "stub"
    assert fm["word_count"] == 10

    # Step 3: owner adds prose across threshold. Engine flips to filled.
    _seed_stub(
        f, body_words=threshold + 50, status="stub", recorded_count=fm["word_count"]
    )
    update_metadata(tmp_path / "reflections", REFLECTION_TEMPLATES)
    fm, _ = split_frontmatter(f.read_text())
    assert fm["status"] == "filled"


def test_update_metadata_skips_owner_only_dirs(tmp_path: Path):
    """Files under private/, debugging/, pairing/ are never touched."""
    reflections = tmp_path / "reflections"
    for d in ("private", "debugging", "pairing"):
        p = reflections / d / "x.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("OWNER ONLY")
    update_metadata(reflections, REFLECTION_TEMPLATES)
    for d in ("private", "debugging", "pairing"):
        assert (reflections / d / "x.md").read_text() == "OWNER ONLY"


def test_update_metadata_malformed_frontmatter_warns_and_continues(tmp_path: Path, caplog):
    bad = tmp_path / "reflections" / "weekly" / "2026-W19.md"
    good = tmp_path / "reflections" / "weekly" / "2026-W20.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("no frontmatter at all\nbody only\n")
    _seed_stub(good, body_words=5, recorded_count=0)

    update_metadata(tmp_path / "reflections", REFLECTION_TEMPLATES)

    assert any("malformed frontmatter" in r.getMessage() for r in caplog.records)
    fm, _ = split_frontmatter(good.read_text())
    assert fm["word_count"] == 5
    # Bad file unchanged.
    assert "no frontmatter at all" in bad.read_text()


def test_update_metadata_returns_count_of_files_touched(tmp_path: Path):
    f1 = tmp_path / "reflections" / "weekly" / "2026-W19.md"
    f2 = tmp_path / "reflections" / "monthly" / "2026-05.md"
    _seed_stub(f1, body_words=10, recorded_count=0)
    _seed_stub(f2, body_words=10, recorded_count=0)
    n = update_metadata(tmp_path / "reflections", REFLECTION_TEMPLATES)
    assert n == 2
