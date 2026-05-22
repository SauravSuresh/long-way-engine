"""One-time migration: generate curriculum/syllabus.yaml from existing sources.

Reads:
  - src/syllabus.py PRIMARY_BOOK_BY_MONTH (the dict)
  - the-long-way.md (regex parsed for full book list)
  - curriculum/modules.yaml (module numbers + onboarding task titles)

Writes:
  - curriculum/syllabus.yaml

Deleted at the end of the plan. Not part of the shipped engine.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.syllabus import PRIMARY_BOOK_BY_MONTH, parse_books_from_file

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "curriculum" / "syllabus.yaml"
MODULES_PATH = REPO_ROOT / "curriculum" / "modules.yaml"


PHASES = [
    {"number": 1, "name": "Foundations",
     "months": [1, 12]},
    {"number": 2, "name": "Go & the Backend Toolkit",
     "months": [13, 20]},
    {"number": 3, "name": "Distributed Systems & Booking",
     "months": [21, 30]},
    {"number": 4, "name": "Kubernetes, Observability, Synthesis",
     "months": [31, 39]},
]


def _extract_module_name(title: str) -> str:
    """Turn 'Module 4: C & Memory Management — start' into 'C & Memory Management'."""
    m = re.match(r"^Module \d+:\s*(.+?)(?:\s+—\s+start)?$", title.strip())
    return m.group(1).strip() if m else title.strip()


def build_modules() -> list[dict]:
    raw = yaml.safe_load(MODULES_PATH.read_text(encoding="utf-8")) or []
    by_number: dict[int, dict] = {}
    for entry in raw:
        if entry.get("cadence") != "once-per-module":
            continue
        mod_num = entry.get("module_number")
        if mod_num is None:
            continue
        # Only the onboarding task per module (id ends with -onboarding).
        if not entry["id"].endswith("-onboarding"):
            continue
        name = _extract_module_name(entry["title"])
        # Phase derived from PHASES table by month — modules don't carry
        # their own month, but we can infer phase from existing PHASES
        # by looking at the module number's typical phase boundaries.
        # Hand-map (mirrors the current modules.yaml comments):
        if mod_num <= 11:
            phase = 1
        elif mod_num <= 16:
            phase = 2
        elif mod_num <= 20:
            phase = 3
        else:
            phase = 4
        by_number[mod_num] = {
            "number": mod_num,
            "name": name,
            "phase": phase,
        }
    return [by_number[k] for k in sorted(by_number)]


def build_books() -> list[dict]:
    """Pull books from the regex parser over the-long-way.md."""
    parsed = parse_books_from_file()
    out: list[dict] = []
    for b in parsed:
        entry: dict = {
            "title": b.title,
            "author": b.author,
            "phase": b.phase,
        }
        if b.start_month is not None:
            entry["months"] = [b.start_month, b.end_month]
        entry["role"] = "primary"  # default; reviewer adjusts secondary/reference by hand
        out.append(entry)
    return out


def main() -> None:
    syllabus = {
        "meta": {
            "name": "The Long Way",
            "total_months": 39,
            "start_month_index": 1,
        },
        "phases": PHASES,
        "books": build_books(),
        "primary_book_by_month": dict(sorted(PRIMARY_BOOK_BY_MONTH.items())),
        "modules": build_modules(),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        yaml.safe_dump(syllabus, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
