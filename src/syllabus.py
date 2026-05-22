"""Syllabus parser and primary-book-per-month lookup.

Hybrid design (Phase D):

  - `parse_books(syllabus_text)` — regex extractor over `the-long-way.md`'s
    "Phase X reading" sections. Returns every italicised entry with
    title, author, and (when present) month range. Used by Phase E's
    dashboard to render the per-phase reading list.

  - `PRIMARY_BOOK_BY_MONTH` — hand-written dict, months 1..39 → primary
    book title. Disambiguates months where the syllabus lists multiple
    overlapping reads (e.g. month 2 has both CSAPP 1–6 and Debugging 2;
    primary is CSAPP, the long read). Source of truth for {current_book}.

  - `current_book(month)` — table lookup with carry-forward fallback.
    Months not in the table return the most recent prior month's value,
    so book-less months (LFCS prep, certs, build-only stretches) keep a
    sensible morning-reading title rather than an empty string.

The drift sanity test (`test_syllabus.py`) cross-checks the table against
the regex extractor: every table value must appear as a substring (after
normalization) of some regex-extracted title. Catches the "I edited the
markdown reading schedule but forgot the table" class of drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
SYLLABUS_PATH = REPO_ROOT / "the-long-way.md"


@dataclass(frozen=True)
class Book:
    phase: int
    title: str
    author: str
    start_month: int | None  # None for reference-only entries
    end_month: int | None

    @property
    def is_reference(self) -> bool:
        return self.start_month is None


@dataclass(frozen=True)
class Phase:
    number: int
    name: str
    months: tuple[int, int]  # inclusive [start, end]


@dataclass(frozen=True)
class Module:
    number: int
    name: str
    phase: int


@dataclass(frozen=True)
class Syllabus:
    meta: dict
    phases: list[Phase]
    books: list[Book]
    primary_book_by_month: dict[int, str]
    modules: list[Module]


def load_syllabus(curriculum_dir: Path) -> "Syllabus":
    """Parse curriculum/syllabus.yaml into a Syllabus dataclass.

    Validation lives in src/curriculum_validator.py — this loader is
    intentionally permissive so the validator can collect every error
    in one pass.
    """
    import yaml
    raw = yaml.safe_load(
        (curriculum_dir / "syllabus.yaml").read_text(encoding="utf-8")
    )
    phases = [
        Phase(number=p["number"], name=p["name"],
              months=(p["months"][0], p["months"][1]))
        for p in raw.get("phases", [])
    ]
    books: list[Book] = []
    for b in raw.get("books", []):
        months = b.get("months")
        start, end = (months[0], months[1]) if months else (None, None)
        books.append(Book(
            phase=b["phase"], title=b["title"], author=b["author"],
            start_month=start, end_month=end,
        ))
    modules = [
        Module(number=m["number"], name=m["name"], phase=m["phase"])
        for m in raw.get("modules", [])
    ]
    primary = {int(k): str(v) for k, v in (raw.get("primary_book_by_month") or {}).items()}
    return Syllabus(
        meta=raw.get("meta", {}),
        phases=phases,
        books=books,
        primary_book_by_month=primary,
        modules=modules,
    )


# --- regex extractor -----------------------------------------------------------

# Match "### Phase N reading" up to the next "### " or "---" line.
_PHASE_SECTION_RE = re.compile(
    r"^### Phase (\d+) reading\s*\n(.*?)(?=\n### |\n---\s*\n)",
    re.DOTALL | re.MULTILINE,
)

# Inside a section, match a bullet that names a book in italics.
# Pattern: - *<Title>* — <Author> *(<timing>)*
# The em-dash `—` separates title and author. Author runs until the next `*(`.
_BOOK_RE = re.compile(
    r"^- \*([^*\n]+)\*\s+—\s+([^*\n]+?)\s+\*\(([^)\n]+)\)\*",
    re.MULTILINE,
)

# Inside the timing string: "month 2", "months 1–6", "months 7-10".
# Accepts both en-dash (–) and hyphen-minus (-).
_MONTHS_RE = re.compile(r"months?\s+(\d+)(?:\s*[–\-]\s*(\d+))?", re.IGNORECASE)


def parse_books(syllabus_text: str) -> list[Book]:
    """Extract every italicised book bullet from the four 'Phase X reading' sections."""
    out: list[Book] = []
    for sec in _PHASE_SECTION_RE.finditer(syllabus_text):
        phase = int(sec.group(1))
        content = sec.group(2)
        for m in _BOOK_RE.finditer(content):
            title = m.group(1).strip()
            author = m.group(2).strip()
            timing = m.group(3).strip()
            mm = _MONTHS_RE.search(timing)
            if mm:
                start = int(mm.group(1))
                end = int(mm.group(2)) if mm.group(2) else start
            else:
                start = end = None
            out.append(Book(phase=phase, title=title, author=author,
                            start_month=start, end_month=end))
    return out


def parse_books_from_file(path: Path = SYLLABUS_PATH) -> list[Book]:
    return parse_books(path.read_text(encoding="utf-8"))


# --- primary-book-per-month lookup --------------------------------------------

# Hand-written. Update when the syllabus reading schedule shifts.
# The drift sanity test cross-checks every entry against the regex extractor.
PRIMARY_BOOK_BY_MONTH: dict[int, str] = {
    # Phase 1 — Foundations (months 1–12). Source: "### Phase 1 reading".
    # CSAPP is the months-1–6 primary. Debugging is a single-weekend read in
    # month 2 — primary stays CSAPP.
    1: "Computer Systems: A Programmer's Perspective",
    2: "Computer Systems: A Programmer's Perspective",
    3: "Computer Systems: A Programmer's Perspective",
    4: "Computer Systems: A Programmer's Perspective",
    5: "Computer Systems: A Programmer's Perspective",
    6: "Computer Systems: A Programmer's Perspective",
    # Networking takes over months 7–10. Months 11–12 (LFCS prep, lab work)
    # have no main book — carry forward.
    7: "Computer Networking: A Top-Down Approach",
    8: "Computer Networking: A Top-Down Approach",
    9: "Computer Networking: A Top-Down Approach",
    10: "Computer Networking: A Top-Down Approach",
    11: "Computer Networking: A Top-Down Approach",   # carry-forward
    12: "Computer Networking: A Top-Down Approach",   # carry-forward

    # Phase 2 — Go & the Backend Toolkit (months 13–20). Source: "### Phase 2 reading".
    # Month 13 is boot.dev course ramp; The Go Programming Language proper
    # is months 14–18. Carry forward through 13, and after the book ends
    # through 19–20 (HTTP servers + Docker hands-on).
    13: "Computer Networking: A Top-Down Approach",   # carry-forward
    14: "The Go Programming Language",
    15: "The Go Programming Language",
    16: "The Go Programming Language",
    17: "The Go Programming Language",
    18: "The Go Programming Language",
    19: "The Go Programming Language",                # carry-forward
    20: "The Go Programming Language",                # carry-forward

    # Phase 3 — Distributed Systems & Booking (months 21–30). Source: "### Phase 3 reading".
    # DDIA is the long primary 21–26. Building Microservices overlaps 24–28
    # but is "as reference during architecture" — primary 27–28. Months
    # 29–30 are deployment/cert work — carry forward.
    21: "Designing Data-Intensive Applications",
    22: "Designing Data-Intensive Applications",
    23: "Designing Data-Intensive Applications",
    24: "Designing Data-Intensive Applications",
    25: "Designing Data-Intensive Applications",
    26: "Designing Data-Intensive Applications",
    27: "Building Microservices",
    28: "Building Microservices",
    29: "Building Microservices",                     # carry-forward
    30: "Building Microservices",                     # carry-forward

    # Phase 4 — Kubernetes, Observability, Synthesis (months 31–39).
    # Source: "### Phase 4 reading".
    # Kubernetes Up & Running 31–33. SRE 34–36 (APoSD overlaps 36–37 but is
    # short — primary stays SRE for 36). DDIA re-read 37–39.
    31: "Kubernetes Up & Running",
    32: "Kubernetes Up & Running",
    33: "Kubernetes Up & Running",
    34: "Site Reliability Engineering",
    35: "Site Reliability Engineering",
    36: "Site Reliability Engineering",
    37: "Designing Data-Intensive Applications",      # re-read
    38: "Designing Data-Intensive Applications",      # re-read
    39: "Designing Data-Intensive Applications",      # re-read
}


def current_book(month: int, syllabus: "Syllabus | None" = None) -> str:
    """Primary book for `month` with carry-forward to the most recent mapped month.

    When `syllabus` is provided, look up in syllabus.primary_book_by_month.
    When `syllabus` is None (legacy callers, removed in Task 16), fall back
    to the module-level PRIMARY_BOOK_BY_MONTH dict. Returns "" only when no
    prior month is mapped.
    """
    table = syllabus.primary_book_by_month if syllabus is not None else PRIMARY_BOOK_BY_MONTH
    if month in table:
        return table[month]
    for m in range(month - 1, 0, -1):
        if m in table:
            return table[m]
    return ""


# --- drift sanity normalization (used by tests) -------------------------------

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_for_drift_check(s: str) -> str:
    """Lowercase + replace runs of non-alnum with single space + strip.

    Both sides of the drift sanity test (table value and regex-extracted
    title) go through this. Smart quotes, em-dashes, colons, ampersands,
    and abbreviations all collapse so a substring check is robust to
    typographic drift in the syllabus.
    """
    return _NON_ALNUM.sub(" ", s.lower()).strip()
