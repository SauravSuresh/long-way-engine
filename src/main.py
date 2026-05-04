"""Daily run entrypoint.

Loads state, config, and templates; computes today in the owner's TZ;
for each daily template that should fire, creates the Todoist task
idempotently; persists the cache and appends a LOG.md entry.

Phase A scope: daily cadence + Sunday skip only. No reflections, no
dashboard, no weekly/monthly/quarterly cadences, no `paused` short-circuit.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from zoneinfo import ZoneInfo

from src.cache import load_cache, prune, save_cache
from src.clock import Clock, FrozenClock
from src.config import Config, TokenRedactingFilter, load_config
from src.ids import external_id
from src.scheduler import should_create_today
from src.state import State, load_state
from src.templates import load_templates, resolve_variables
from src.todoist import CreateResult, TodoistClient

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"
STATE_PATH = REPO_ROOT / "state.yaml"
ENV_PATH = REPO_ROOT / ".env"
TEMPLATES_DIR = REPO_ROOT / "task_templates"
CACHE_PATH = REPO_ROOT / ".task_cache.json"
LOG_PATH = REPO_ROOT / "LOG.md"


@dataclass
class Decision:
    template_id: str
    external_id: str | None
    decision: str  # "WOULD CREATE" | "SKIP (cache hit)" | "SKIP (Sunday)" | "ERROR"


@dataclass
class RunSummary:
    today: date
    created: list[CreateResult]
    skipped: list[CreateResult]
    errors: int
    decisions: list[Decision] = field(default_factory=list)


def _setup_logging(token: str, verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger().addFilter(TokenRedactingFilter(token))


def _classify_skip(template, state: State, config: Config, today: date) -> str:
    """Best-effort label for why a daily template was skipped today."""
    if (
        template.cadence == "daily"
        and template.skip_if == "sunday"
        and config.sunday_off
        and today.weekday() == 6
    ):
        return "SKIP (Sunday)"
    return "SKIP (rule)"


def run(
    config: Config,
    state: State,
    today: date,
    templates_dir: Path,
    cache_path: Path,
    client_factory=None,
    clock: Clock | None = None,
    dry_run: bool = False,
    project_id: str | None = None,
) -> RunSummary:
    if clock is None:
        clock = Clock(state.timezone)
    if client_factory is None:
        # Lookup at call time so module-level patches in tests take effect.
        client_factory = TodoistClient

    cache = load_cache(cache_path)
    templates = load_templates(templates_dir)
    client = client_factory(
        token=config.todoist_token,
        project_id=project_id or config.todoist.project_id,
        clock=clock,
        dry_run=dry_run,
    )

    created: list[CreateResult] = []
    skipped: list[CreateResult] = []
    decisions: list[Decision] = []
    errors = 0

    for tpl in templates:
        try:
            if not should_create_today(tpl, today, state, config):
                label = _classify_skip(tpl, state, config, today)
                logger.info("template %s: %s", tpl.id, label.lower())
                decisions.append(Decision(tpl.id, None, label))
                continue
        except NotImplementedError as e:
            logger.warning("template %s: %s", tpl.id, e)
            decisions.append(Decision(tpl.id, None, "ERROR (cadence)"))
            errors += 1
            continue

        resolved = resolve_variables(tpl, state, config)
        if resolved is None:
            decisions.append(Decision(tpl.id, None, "ERROR (variable)"))
            errors += 1
            continue

        ext_id = external_id(tpl.id, today)
        try:
            result = client.create_task_idempotent(resolved, today, ext_id, cache)
        except Exception as e:
            logger.error("template %s: create failed: %s", tpl.id, e)
            decisions.append(Decision(tpl.id, ext_id, "ERROR (api)"))
            errors += 1
            continue

        if result.skipped:
            skipped.append(result)
            decisions.append(Decision(tpl.id, ext_id, "SKIP (cache hit)"))
        else:
            created.append(result)
            decisions.append(Decision(tpl.id, ext_id, "WOULD CREATE" if dry_run else "CREATED"))
            cache[ext_id] = {
                "todoist_task_id": result.todoist_task_id,
                "created_at": result.created_at,
                "template_id": result.template_id,
                "due_date": result.due_date.isoformat(),
            }

    cache = prune(cache, now=clock.now().astimezone(timezone.utc))
    if not dry_run:
        save_cache(cache_path, cache)

    return RunSummary(
        today=today,
        created=created,
        skipped=skipped,
        errors=errors,
        decisions=decisions,
    )


def append_log(
    log_path: Path,
    summary: RunSummary,
    tz_name: str,
    clock: Clock | None = None,
) -> None:
    if clock is None:
        clock = Clock(ZoneInfo(tz_name))
    when = clock.now().strftime("%Y-%m-%d %H:%M %Z")
    entry = (
        f"## {summary.today.isoformat()} ({tz_name})\n"
        f"- Run at: {when}\n"
        f"- Created: {len(summary.created)} "
        f"({', '.join(r.template_id for r in summary.created) or 'none'})\n"
        f"- Skipped (cache hit): {len(summary.skipped)} "
        f"({', '.join(r.template_id for r in summary.skipped) or 'none'})\n"
        f"- Errors: {summary.errors}\n\n"
    )
    if log_path.exists():
        existing = log_path.read_text(encoding="utf-8")
    else:
        existing = "# Long Way Engine — run log\n\n"
    log_path.write_text(existing + entry, encoding="utf-8")


def _parse_today(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--today must be YYYY-MM-DD: {e}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Long Way Engine — daily run.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="No API calls, no file writes. Print a decision table.",
    )
    p.add_argument(
        "--today",
        type=_parse_today,
        metavar="YYYY-MM-DD",
        help="Override the clock. Time-of-day defaults to 05:30 in owner TZ.",
    )
    p.add_argument(
        "--project-id",
        metavar="ID",
        help="Override config.yaml todoist.project_id.",
    )
    p.add_argument(
        "--cache-file",
        type=Path,
        metavar="PATH",
        help="Override .task_cache.json path.",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="DEBUG-level logging.",
    )
    return p


def _print_dry_run_table(summary: RunSummary, out=None) -> None:
    if out is None:
        out = sys.stdout
    rows = [(d.template_id, d.external_id or "-", d.decision) for d in summary.decisions]
    if not rows:
        print("(no templates produced a decision)", file=out)
        return
    tpl_w = max(len("TEMPLATE"), max(len(r[0]) for r in rows))
    id_w = max(len("EXTERNAL_ID"), max(len(r[1]) for r in rows))
    dec_w = max(len("DECISION"), max(len(r[2]) for r in rows))
    fmt = f"{{:<{tpl_w}}}  {{:<{id_w}}}  {{:<{dec_w}}}"
    print(fmt.format("TEMPLATE", "EXTERNAL_ID", "DECISION"), file=out)
    for r in rows:
        print(fmt.format(*r), file=out)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    config = load_config(CONFIG_PATH, ENV_PATH)
    _setup_logging(config.todoist_token, verbose=args.verbose)
    state = load_state(STATE_PATH)

    if args.today is not None:
        clock: Clock = FrozenClock(args.today, state.timezone)
        today = args.today
    else:
        clock = Clock(state.timezone)
        today = clock.today()

    cache_path = args.cache_file or CACHE_PATH

    logger.info(
        "daily run start: today=%s tz=%s dry_run=%s cache=%s",
        today,
        state.timezone.key,
        args.dry_run,
        cache_path,
    )

    summary = run(
        config,
        state,
        today,
        TEMPLATES_DIR,
        cache_path,
        clock=clock,
        dry_run=args.dry_run,
        project_id=args.project_id,
    )

    if args.dry_run:
        _print_dry_run_table(summary)
    else:
        append_log(LOG_PATH, summary, state.timezone.key, clock=clock)

    logger.info(
        "daily run done: created=%d skipped=%d errors=%d",
        len(summary.created),
        len(summary.skipped),
        summary.errors,
    )
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
