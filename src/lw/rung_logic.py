"""Pure logic for lw rung start: brief discovery + paper/code scaffold.

No Todoist, no network — reads curriculum briefs + modules.yaml templates,
writes ladder/<slug>/{meta.yaml,adr.md} and code_root/<slug>/README.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml

from src.lw.status_logic import CurriculumCtx

_GITHUB_USER = "SauravSuresh"
_GITHUB_REPO = "long-way-engine"

_BRIEF_RE = re.compile(r"rung-(\d{2})([abc])-")


@dataclass
class RungOption:
    slug: str
    option: str
    title: str
    brief_path: Path


@dataclass
class ScaffoldResult:
    paper_dir: Path
    code_dir: Path


def rung_options(repo_root: Path, cur: CurriculumCtx) -> list[RungOption]:
    """The current rung's briefs (a/b/c), sorted by option letter."""
    module_number = cur.state.current_module
    briefs_dir = cur.entry.path / "briefs"
    opts: list[RungOption] = []
    for path in sorted(briefs_dir.glob(f"rung-{module_number:02d}[abc]-*.md")):
        match = _BRIEF_RE.match(path.stem)
        if not match:
            continue
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        title = first_line.split("—", 1)[-1].strip()
        opts.append(RungOption(slug=path.stem, option=match.group(2), title=title, brief_path=path))
    return opts


def _brief_github_url(brief_path: Path) -> str:
    parts = brief_path.parts
    idx = parts.index("curricula")
    rel = "/".join(parts[idx:])
    return f"https://github.com/{_GITHUB_USER}/{_GITHUB_REPO}/blob/main/{rel}"


def scaffold(
    repo_root: Path, cur: CurriculumCtx, opt: RungOption, code_root: Path, today: date,
    *, code_dir: Path | None = None,
) -> ScaffoldResult:
    """code_dir, if given, is the exact directory to scaffold code into
    (e.g. the path the user confirmed in the rung TUI, slug or no slug).
    Otherwise defaults to code_root/opt.slug."""
    module_number = cur.state.current_module
    ladder_dir = repo_root / "ladder"
    if ladder_dir.exists() and any(ladder_dir.glob(f"rung-{module_number:02d}?-*")):
        raise FileExistsError(f"rung {module_number} already picked")

    deadline_days = next(
        t.deadline_days
        for t in cur.templates
        if t.cadence == "once-per-module" and t.module_number == module_number
    )
    deadline = today + timedelta(days=deadline_days)

    paper_dir = ladder_dir / opt.slug
    paper_dir.mkdir(parents=True)
    code_dir = code_dir if code_dir is not None else code_root / opt.slug
    code_dir.mkdir(parents=True)

    meta = {
        "rung": module_number,
        "option": opt.option,
        "slug": opt.slug,
        "picked_at": today.isoformat(),
        "code_path": str(code_dir),
        "deadline": deadline.isoformat(),
        "extensions": [],
        "outcome": None,
    }
    meta_path = paper_dir / "meta.yaml"
    meta_path.write_text(
        yaml.safe_dump(meta, sort_keys=False, default_flow_style=False), encoding="utf-8"
    )

    adr_path = paper_dir / "adr.md"
    adr_path.write_text(
        f"# ADR — {opt.title}\n\n"
        f"**Picked:** option {opt.option} on {today.isoformat()}. **Why this option:**\n\n"
        "## Context\n\n"
        "## Options considered\n\n"
        "## Decision\n\n"
        "## Consequences\n",
        encoding="utf-8",
    )

    readme_path = code_dir / "README.md"
    readme_path.write_text(f"Brief: {_brief_github_url(opt.brief_path)}\n", encoding="utf-8")

    return ScaffoldResult(paper_dir=paper_dir, code_dir=code_dir)
