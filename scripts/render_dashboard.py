"""scripts/render_dashboard.py — synthetic-completion dashboard render.

Permanent debug tool for visualising the Phase E dashboard against the
local repo state without making any API calls. Treats every task_id
present in `.task_cache.json` as completed so the streak walker has
something to walk against; the resulting streak numbers are SYNTHETIC
and must not be interpreted as real progress data.

Two safeguards against misreading:

  1. A stdout banner before any output.
  2. A coloured HTML banner injected into the rendered page itself.

The script never writes to docs/ — that path is owned by the daily
workflow's render hook. Default --out is /tmp/dashboard_synthetic.html;
the script refuses any --out under docs/.

Audit pattern (must return zero matches):

    grep -nE 'requests\\.(post|patch|delete|put|get)' scripts/render_dashboard.py

This script makes ZERO HTTP calls. The audit lists `get` too, on
purpose: even read-only network access is out of scope here.

Usage:

    python scripts/render_dashboard.py [--today YYYY-MM-DD] [--out PATH]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.cache import load_cache  # noqa: E402
from src.clock import FrozenClock  # noqa: E402
from src.config import load_config  # noqa: E402
from src.dashboard import render, scan_reflections  # noqa: E402
from src.state import load_state  # noqa: E402
from src.syllabus import parse_books_from_file  # noqa: E402
from src.templates import load_templates  # noqa: E402

CONFIG_PATH = REPO_ROOT / "config.yaml"
STATE_PATH = REPO_ROOT / "state.yaml"
ENV_PATH = REPO_ROOT / ".env"
CACHE_PATH = REPO_ROOT / ".task_cache.json"
REFLECTIONS_DIR = REPO_ROOT / "reflections"
CURRICULUM_DIR = REPO_ROOT / "curriculum"
RITUALS_DIR = CURRICULUM_DIR / "rituals"
MODULES_PATH = CURRICULUM_DIR / "modules.yaml"
DOCS_DIR = REPO_ROOT / "docs"
DEFAULT_OUT = Path("/tmp/dashboard_synthetic.html")

BANNER_HTML = (
    '<div class="synthetic-banner" style="background:#fce39e;color:#864;'
    'padding:.75rem 1rem;text-align:center;font-weight:700;'
    'border-bottom:2px solid #c93;font-family:-apple-system,sans-serif;">'
    'SYNTHETIC RENDER &mdash; all cached tasks treated as completed. '
    'Streak numbers are NOT real.'
    '</div>'
)
BANNER_STDOUT = (
    "SYNTHETIC RENDER — all cached tasks treated as completed.\n"
    "  Streak numbers in the output are NOT real.\n"
)


def parse_today(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--today must be YYYY-MM-DD: {e}")


def inject_banner(html: str) -> str:
    """Insert the synthetic-render banner immediately after <body>."""
    if "<body>" not in html:
        raise RuntimeError(
            "banner injection failed: dashboard HTML missing <body> tag — "
            "src/dashboard.py structure changed; update render_dashboard.py"
        )
    out = html.replace("<body>", f"<body>{BANNER_HTML}", 1)
    if BANNER_HTML not in out:
        raise RuntimeError("banner injection failed: replacement did not land")
    return out


def synthetic_completion_set(cache: dict) -> set[str]:
    """Treat every non-DRY-RUN cache task_id as a completion."""
    return {
        str(entry["todoist_task_id"])
        for entry in cache.values()
        if entry.get("todoist_task_id")
        and not str(entry["todoist_task_id"]).startswith("DRY-RUN")
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Synthetic-completion dashboard render.")
    p.add_argument(
        "--today",
        type=parse_today,
        default=None,
        help="Override today (YYYY-MM-DD). Default: actual today in owner TZ.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output HTML path. Default {DEFAULT_OUT}. Must not point under docs/.",
    )
    args = p.parse_args(argv)

    out_resolved = args.out.resolve()
    docs_resolved = DOCS_DIR.resolve()
    try:
        out_resolved.relative_to(docs_resolved)
    except ValueError:
        pass  # Not under docs/ — good.
    else:
        sys.stderr.write(
            f"--out {args.out} is under docs/; that path is owned by the daily "
            "workflow. Use a path outside the repo (e.g. /tmp/...).\n"
        )
        return 2

    sys.stdout.write(BANNER_STDOUT)
    sys.stdout.flush()

    config = load_config(CONFIG_PATH, ENV_PATH)
    state = load_state(STATE_PATH)
    cache = load_cache(CACHE_PATH)
    today = args.today or datetime.now(state.timezone).date()
    clock = FrozenClock(today, state.timezone)

    completion = synthetic_completion_set(cache)
    sys.stdout.write(f"  cache entries: {len(cache)}\n")
    sys.stdout.write(f"  synthetic completion_set size: {len(completion)}\n")
    sys.stdout.write(f"  today: {today.isoformat()}\n")

    reflections = scan_reflections(REFLECTIONS_DIR)
    try:
        books = parse_books_from_file()
    except OSError:
        books = []

    templates = load_templates([RITUALS_DIR, MODULES_PATH])
    module_titles = {
        tpl.module_number: tpl.title
        for tpl in templates
        if tpl.cadence == "once-per-module"
        and tpl.module_number is not None
        and tpl.id.endswith("-onboarding")
    }

    html, _data = render(
        state=state,
        config=config,
        completion_set=completion,
        cache=cache,
        reflections=reflections,
        books=books,
        today=today,
        clock=clock,
        reflections_root=REFLECTIONS_DIR,
        module_titles=module_titles,
    )

    out_html = inject_banner(html)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(out_html, encoding="utf-8")
    sys.stdout.write(f"  wrote {args.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
