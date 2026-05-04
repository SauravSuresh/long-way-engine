"""Phase D: syllabus regex extractor + primary-book-per-month table + drift sanity."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.syllabus import (
    PRIMARY_BOOK_BY_MONTH,
    SYLLABUS_PATH,
    Book,
    current_book,
    normalize_for_drift_check,
    parse_books,
    parse_books_from_file,
)


def test_normalize_collapses_punctuation_and_case():
    assert normalize_for_drift_check("Computer Systems: A Programmer's Perspective") == \
        "computer systems a programmer s perspective"


def test_normalize_handles_em_dash_and_smart_quotes():
    a = "Computer Networking — A Top-Down Approach"
    b = "Computer Networking: A Top-Down Approach"
    assert normalize_for_drift_check(a) == normalize_for_drift_check(b)


def test_parse_books_simple_range():
    text = """### Phase 1 reading

- *Computer Systems: A Programmer's Perspective* — Bryant & O'Hallaron *(months 1–6)*

---
"""
    books = parse_books(text)
    assert len(books) == 1
    b = books[0]
    assert b.phase == 1
    assert b.title == "Computer Systems: A Programmer's Perspective"
    assert b.author == "Bryant & O'Hallaron"
    assert b.start_month == 1
    assert b.end_month == 6


def test_parse_books_single_month():
    text = """### Phase 1 reading

- *Debugging* — David Agans *(month 2 — read first)*

---
"""
    books = parse_books(text)
    assert books[0].title == "Debugging"
    assert books[0].start_month == 2
    assert books[0].end_month == 2


def test_parse_books_reference_only_no_months():
    text = """### Phase 1 reading

- *The Linux Programming Interface* — Kerrisk *(reference, dip in as needed)*

---
"""
    books = parse_books(text)
    assert books[0].title == "The Linux Programming Interface"
    assert books[0].is_reference is True


def test_parse_books_extracts_from_real_syllabus():
    """Real syllabus has at least the four Phase 1 books we care about."""
    books = parse_books_from_file(SYLLABUS_PATH)
    titles = [b.title for b in books]
    assert "Computer Systems: A Programmer's Perspective" in titles
    assert "Computer Networking: A Top-Down Approach" in titles
    assert any("Go Programming Language" in t for t in titles)
    assert any("Designing Data-Intensive Applications" in t for t in titles)


def test_parse_books_groups_by_phase():
    """Each Phase X reading section produces books tagged with phase=X."""
    books = parse_books_from_file(SYLLABUS_PATH)
    phases = {b.phase for b in books}
    assert phases == {1, 2, 3, 4}


# --- PRIMARY_BOOK_BY_MONTH table ----------------------------------------------


def test_primary_book_table_covers_months_1_to_39():
    assert set(PRIMARY_BOOK_BY_MONTH.keys()) == set(range(1, 40))


def test_primary_book_table_no_empty_values():
    for month, title in PRIMARY_BOOK_BY_MONTH.items():
        assert title, f"month {month} has empty primary book"


def test_current_book_month_1_csapp():
    assert current_book(1) == "Computer Systems: A Programmer's Perspective"


def test_current_book_month_7_networking():
    assert current_book(7) == "Computer Networking: A Top-Down Approach"


def test_current_book_carry_forward_month_11():
    """Month 11 has no main book per syllabus — carries forward Networking."""
    assert current_book(11) == current_book(10) == "Computer Networking: A Top-Down Approach"


def test_current_book_zero_or_negative_month_is_empty():
    """Defensive: month 0 or negative returns "" rather than crashing."""
    assert current_book(0) == ""
    assert current_book(-1) == ""


def test_current_book_far_future_carries_forward():
    """Month 100 walks back to the last mapped month (39 = DDIA re-read)."""
    assert current_book(100) == "Designing Data-Intensive Applications"


# --- DRIFT SANITY -------------------------------------------------------------


def test_drift_sanity_every_table_value_appears_in_syllabus():
    """Cross-check: every PRIMARY_BOOK_BY_MONTH value's title must appear
    (after normalization) in the regex-extracted books from the real syllabus.

    This is a best-effort drift catcher — if the syllabus reading schedule
    is edited at a month boundary (book swapped, range shifted) and the
    table isn't updated, this test surfaces the mismatch.

    Normalization makes the substring check robust to smart quotes,
    em-dashes, colons, and other typography that round-trips through
    markdown editors.
    """
    extracted = parse_books_from_file(SYLLABUS_PATH)
    extracted_normalized = [normalize_for_drift_check(b.title) for b in extracted]

    missing: list[tuple[int, str]] = []
    for month, primary in PRIMARY_BOOK_BY_MONTH.items():
        norm = normalize_for_drift_check(primary)
        if not any(norm in et or et in norm for et in extracted_normalized):
            missing.append((month, primary))

    if missing:
        details = "\n".join(f"  month {m}: {t!r}" for m, t in missing)
        pytest.fail(
            "PRIMARY_BOOK_BY_MONTH entries not found in regex extraction of "
            f"the-long-way.md:\n{details}\n"
            "Either: (a) the syllabus reading schedule was edited and the "
            "table needs updating to match, or (b) the table has a typo.\n"
            "Normalization in use: lowercase + non-alnum collapsed to whitespace."
        )
