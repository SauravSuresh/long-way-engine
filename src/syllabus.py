"""YAML-backed curriculum types and primary-book-per-month lookup.

Public surface:

  - `Book`, `Phase`, `Module`, `Syllabus` — dataclasses describing the
    curriculum loaded from `curriculum/syllabus.yaml`.
  - `load_syllabus(curriculum_dir)` — read syllabus.yaml into a Syllabus.
  - `current_book(month, syllabus)` — primary book for `month` with
    carry-forward to the most recent prior mapped month.

Validation lives in `src/curriculum_validator.py`. This module is the
runtime read path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


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
class TrackDeclaration:
    title: str
    category: str
    phase: int
    months: tuple[int, int] | None  # None = manual lifecycle


@dataclass(frozen=True)
class Syllabus:
    meta: dict
    phases: list[Phase]
    books: list[Book]
    primary_book_by_month: dict[int, str]
    modules: list[Module]
    tracks: list[TrackDeclaration] = field(default_factory=list)


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
    tracks: list[TrackDeclaration] = []
    for t in raw.get("tracks") or []:
        months_raw = t.get("months")
        months = (int(months_raw[0]), int(months_raw[1])) if months_raw else None
        tracks.append(TrackDeclaration(
            title=str(t["title"]),
            category=str(t["category"]),
            phase=int(t["phase"]),
            months=months,
        ))
    return Syllabus(
        meta=raw.get("meta", {}),
        phases=phases,
        books=books,
        primary_book_by_month=primary,
        modules=modules,
        tracks=tracks,
    )


def current_book(month: int, syllabus: "Syllabus") -> str:
    """Primary book for `month` with carry-forward.

    Returns "" only when no prior month is mapped.
    """
    table = syllabus.primary_book_by_month
    if month in table:
        return table[month]
    for m in range(month - 1, 0, -1):
        if m in table:
            return table[m]
    return ""


def current_module_name(module_number: int, syllabus: "Syllabus") -> str:
    """Module name for `module_number`. Returns "" if not found.

    Resolver for the `{current_module}` placeholder documented in AGENTS.md.
    Returns the human-readable module name, mirroring how `{current_book}`
    returns the title (not the index).
    """
    for m in syllabus.modules:
        if m.number == module_number:
            return m.name
    return ""
