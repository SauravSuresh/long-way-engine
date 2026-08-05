"""lw — terminal interface to the long-way engine."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lw", description="long-way engine CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="dashboard across curricula")
    sub.add_parser("reflect", help="write a reflection (TUI)")
    sub.add_parser("review", help="Sunday state review (TUI)")
    rung = sub.add_parser("rung", help="ladder commands")
    rung_sub = rung.add_subparsers(dest="rung_cmd", required=True)
    rung_sub.add_parser("start", help="pick this rung's challenge and scaffold it")
    args = parser.parse_args(argv)

    if args.cmd == "status":
        from src.lw.status_logic import build_status

        print("\n".join(build_status(REPO_ROOT, date.today())))
        return 0
    if args.cmd == "reflect":
        from src.lw.reflect_tui import run_reflect

        return run_reflect(REPO_ROOT)
    if args.cmd == "review":
        from src.lw.review_tui import run_review

        return run_review(REPO_ROOT)
    if args.cmd == "rung" and args.rung_cmd == "start":
        from src.lw.rung_tui import run_rung_start

        return run_rung_start(REPO_ROOT)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
