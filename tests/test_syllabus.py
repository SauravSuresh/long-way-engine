"""YAML-backed syllabus loader and current_book lookup."""

from __future__ import annotations

from pathlib import Path


def test_load_syllabus_from_curriculum_dir(tmp_path: Path) -> None:
    """load_syllabus reads curriculum/syllabus.yaml into a Syllabus dataclass."""
    cdir = tmp_path / "curriculum"
    cdir.mkdir()
    (cdir / "syllabus.yaml").write_text(
        "meta:\n"
        "  name: Tiny\n"
        "  start_month_index: 1\n"
        "phases:\n"
        "  - number: 1\n"
        "    name: Foundations\n"
        "    months: [1, 3]\n"
        "books:\n"
        "  - title: Book A\n"
        "    author: Author\n"
        "    phase: 1\n"
        "    months: [1, 3]\n"
        "    role: primary\n"
        "primary_book_by_month:\n"
        "  1: Book A\n"
        "  2: Book A\n"
        "  3: Book A\n"
        "modules:\n"
        "  - number: 1\n"
        "    name: Mod One\n"
        "    phase: 1\n",
        encoding="utf-8",
    )
    from src.syllabus import load_syllabus
    syl = load_syllabus(cdir)
    assert syl.meta["name"] == "Tiny"
    assert len(syl.phases) == 1
    assert syl.phases[0].name == "Foundations"
    assert syl.phases[0].months == (1, 3)
    assert len(syl.books) == 1
    assert syl.primary_book_by_month == {1: "Book A", 2: "Book A", 3: "Book A"}
    assert len(syl.modules) == 1
    assert syl.modules[0].name == "Mod One"


def test_current_book_with_syllabus(tmp_path: Path) -> None:
    """current_book(month, syllabus) does table lookup with carry-forward."""
    from src.syllabus import Syllabus, Phase, Book as SylBook, Module, current_book
    syl = Syllabus(
        meta={"name": "T", "start_month_index": 1},
        phases=[Phase(number=1, name="P1", months=(1, 5))],
        books=[SylBook(phase=1, title="A", author="x", start_month=1, end_month=3)],
        primary_book_by_month={1: "A", 2: "A", 3: "A"},
        modules=[Module(number=1, name="M1", phase=1)],
    )
    assert current_book(1, syl) == "A"
    assert current_book(3, syl) == "A"
    assert current_book(4, syl) == "A"   # carry-forward
    assert current_book(0, syl) == ""     # no prior


def test_load_syllabus_against_live_curriculum() -> None:
    """The repo's own curricula/long-way/syllabus.yaml loads cleanly."""
    from pathlib import Path as P
    from src.syllabus import load_syllabus
    REPO_ROOT = P(__file__).resolve().parent.parent
    syl = load_syllabus(REPO_ROOT / "curricula" / "long-way")
    # Sanity: matches what we expect about the Long Way curriculum.
    assert len(syl.phases) == 4
    assert len(syl.modules) == 23
    assert 1 in syl.primary_book_by_month
    assert 39 in syl.primary_book_by_month


def test_load_syllabus_for_entry_returns_parsed() -> None:
    from pathlib import Path
    from src.config import SyllabusEntry
    from src.syllabus import load_syllabus_for_entry

    entry = SyllabusEntry(
        key="long-way",
        path=Path("curricula/long-way"),
        todoist_project_id="X",
        state_file=Path("state/long-way.yaml"),
        enabled=True,
        ritual_times={},
    )
    sy = load_syllabus_for_entry(entry)
    assert sy.meta["name"]  # parsed without error
