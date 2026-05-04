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

import json

from src.cache import load_cache, prune, save_cache
from src.clock import Clock, FrozenClock
from src.config import Config, TokenRedactingFilter, load_config
from src.dashboard import (
    render as render_dashboard,
    scan_reflections,
    write_css_if_absent,
)
from src.ids import external_id, module_external_id
from src.reflections import StubResult, create_stub, update_metadata
from src.scheduler import should_create_today
from src.state import State, load_state
from src.syllabus import parse_books_from_file
from src.templates import load_templates, resolve_variables
from src.todoist import (
    CreateResult,
    TodoistAdminClient,
    TodoistClient,
    TodoistCompletionClient,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"
STATE_PATH = REPO_ROOT / "state.yaml"
ENV_PATH = REPO_ROOT / ".env"
TEMPLATES_DIR = REPO_ROOT / "task_templates"
CACHE_PATH = REPO_ROOT / ".task_cache.json"
LOG_PATH = REPO_ROOT / "LOG.md"
REFLECTIONS_DIR = REPO_ROOT / "reflections"
REFLECTION_TEMPLATES_DIR = REPO_ROOT / "reflection_templates"
COMPLETION_CACHE_PATH = REPO_ROOT / ".completion_cache.json"
DOCS_DIR = REPO_ROOT / "docs"
DOCS_HTML_PATH = DOCS_DIR / "index.html"
DOCS_DATA_PATH = DOCS_DIR / "assets" / "data.json"
DOCS_CSS_PATH = DOCS_DIR / "assets" / "style.css"


@dataclass
class Decision:
    template_id: str
    external_id: str | None
    decision: str  # "WOULD CREATE" | "SKIP (cache hit)" | "SKIP (Sunday)" | "ERROR"


@dataclass
class StubDecision:
    path: str
    decision: str  # "WOULD CREATE STUB" | "WOULD SKIP STUB (exists)" | "WOULD SKIP STUB (pending)" | "CREATED" | "EXISTS"
    via_template_id: str


@dataclass
class RunSummary:
    today: date
    created: list[CreateResult]
    skipped: list[CreateResult]
    errors: int
    decisions: list[Decision] = field(default_factory=list)
    stub_decisions: list[StubDecision] = field(default_factory=list)
    metadata_updated: int = 0
    dashboard_status: str | None = None  # "ok" | "error" | "skipped" | None (dry-run)


def _setup_logging(token: str, verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger().addFilter(TokenRedactingFilter(token))


def _classify_skip(template, state: State, config: Config, today: date) -> str:
    """Human-readable label for why this template did not fire today."""
    if state.paused:
        return "SKIP (paused)"
    cadence = template.cadence
    if cadence == "daily":
        rules = template.skip_if
        if (
            "sunday" in rules
            and config.sunday_off
            and today.weekday() == 6
        ):
            return "SKIP (Sunday)"
        if (
            "pair_day" in rules
            and config.pair_day
            and today.strftime("%A").lower() == config.pair_day.lower()
        ):
            return "SKIP (pair day)"
        return "SKIP (rule)"
    if cadence == "weekly":
        day = template.day_of_week or "?"
        return f"SKIP (not {day})"
    if cadence == "monthly":
        return "SKIP (not month boundary)"
    if cadence == "quarterly":
        return "SKIP (not quarter boundary)"
    if cadence == "annual":
        return "SKIP (not Jan 1)"
    if cadence == "once-per-module":
        return "SKIP (not current module)"
    return "SKIP (rule)"


_STUB_DECISION_LABELS = {
    "would_create": "WOULD CREATE STUB",
    "would_skip_exists": "WOULD SKIP STUB (exists)",
    "would_skip_pending": "WOULD SKIP STUB (pending)",
    "created": "CREATED",
    "exists": "EXISTS",
}


def _record_stub(
    tpl,
    state: State,
    config: Config,
    today: date,
    reflections_root: Path,
    reflection_templates_root: Path,
    pending_paths: set[Path],
    dry_run: bool,
    stub_decisions: list[StubDecision],
) -> None:
    """Run create_stub for one template and append a StubDecision row."""
    res: StubResult | None = create_stub(
        tpl,
        state,
        config,
        today,
        reflections_root,
        reflection_templates_root,
        pending_paths,
        dry_run=dry_run,
    )
    if res is None:
        return
    stub_decisions.append(
        StubDecision(
            path=str(res.path),
            decision=_STUB_DECISION_LABELS.get(res.decision, res.decision.upper()),
            via_template_id=tpl.id,
        )
    )


def _render_dashboard_once(
    state: State,
    config: Config,
    today: date,
    clock: Clock,
    cache: dict,
    reflections_root: Path,
    completion_cache_path: Path,
    docs_html_path: Path,
    docs_data_path: Path,
    docs_css_path: Path,
    completion_factory,
) -> str:
    """Render dashboard + sidecar JSON. Returns "ok" or "error".

    Per Phase E plan: failures log but never fail the run. The CSS file is
    laid down only on first run; subsequent runs leave it untouched so the
    owner can hand-edit visuals.
    """
    write_css_if_absent(docs_css_path)
    completion_client = completion_factory(
        token=config.todoist_token,
        cache_path=completion_cache_path,
        project_id=config.todoist.project_id,
        clock=clock,
    )
    candidate_ids = sorted({
        str(entry["todoist_task_id"])
        for entry in cache.values()
        if entry.get("todoist_task_id")
        and not str(entry["todoist_task_id"]).startswith("DRY-RUN")
    })
    if candidate_ids:
        statuses = completion_client.get_completion_status(candidate_ids)
        completion_set = {tid for tid, done in statuses.items() if done}
    else:
        completion_set = set()

    reflections = scan_reflections(reflections_root)
    try:
        books = parse_books_from_file()
    except OSError:
        books = []

    html, data = render_dashboard(
        state=state,
        config=config,
        completion_set=completion_set,
        cache=cache,
        reflections=reflections,
        books=books,
        today=today,
        clock=clock,
        reflections_root=reflections_root,
    )

    docs_html_path.parent.mkdir(parents=True, exist_ok=True)
    docs_data_path.parent.mkdir(parents=True, exist_ok=True)
    docs_html_path.write_text(html, encoding="utf-8")
    docs_data_path.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return "ok"


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
    reflections_root: Path | None = None,
    reflection_templates_root: Path | None = None,
    skip_dashboard: bool = False,
    completion_factory=None,
    completion_cache_path: Path | None = None,
    docs_html_path: Path | None = None,
    docs_data_path: Path | None = None,
    docs_css_path: Path | None = None,
) -> RunSummary:
    if clock is None:
        clock = Clock(state.timezone)
    if client_factory is None:
        # Lookup at call time so module-level patches in tests take effect.
        client_factory = TodoistClient
    if completion_factory is None:
        completion_factory = TodoistCompletionClient
    if reflections_root is None:
        reflections_root = REFLECTIONS_DIR
    if reflection_templates_root is None:
        reflection_templates_root = REFLECTION_TEMPLATES_DIR
    if completion_cache_path is None:
        completion_cache_path = COMPLETION_CACHE_PATH
    if docs_html_path is None:
        docs_html_path = DOCS_HTML_PATH
    if docs_data_path is None:
        docs_data_path = DOCS_DATA_PATH
    if docs_css_path is None:
        docs_css_path = DOCS_CSS_PATH

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
    stub_decisions: list[StubDecision] = []
    pending_paths: set[Path] = set()
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

        resolved = resolve_variables(tpl, state, config, today)
        if resolved is None:
            decisions.append(Decision(tpl.id, None, "ERROR (variable)"))
            errors += 1
            continue

        # Module-keyed id for once-per-module so advancing state.current_module
        # gives module N's onboarding a fresh id (different from any past month's
        # date-keyed ids). Cache + marker dedup still prevent re-firing on the
        # same module value.
        if tpl.cadence == "once-per-module":
            assert tpl.module_number is not None  # scheduler already validated
            ext_id = module_external_id(tpl.id, tpl.module_number)
            cache_due = f"module:{tpl.module_number}"
        else:
            ext_id = external_id(tpl.id, today)
            cache_due = today.isoformat()

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
                "due_date": cache_due,
            }

        # Stub creation is template-fired, not task-creation-fired:
        # it runs whether the task was created, marker-deduped, or cache-hit.
        _record_stub(
            tpl,
            state,
            config,
            today,
            reflections_root,
            reflection_templates_root,
            pending_paths,
            dry_run,
            stub_decisions,
        )

    cache = prune(cache, now=clock.now().astimezone(timezone.utc))
    if not dry_run:
        save_cache(cache_path, cache)

    # Metadata walk runs UNCONDITIONALLY at end — even when paused — so
    # owner-edited stubs continue to track word_count and status across
    # pauses. Skipped in dry-run because it would otherwise mutate files.
    metadata_updated = 0
    if not dry_run:
        metadata_updated = update_metadata(reflections_root, reflection_templates_root)

    # Dashboard render: after metadata walk, before append_log. Failure logs
    # but doesn't fail the run (Phase E plan, decision 17). Dry-run skips
    # entirely; --skip-dashboard skips on-demand. Render runs even when
    # paused so the dashboard reflects the pause and preserves prior streaks.
    dashboard_status: str | None = None
    if dry_run:
        dashboard_status = None
    elif skip_dashboard:
        dashboard_status = "skipped"
    else:
        try:
            dashboard_status = _render_dashboard_once(
                state=state,
                config=config,
                today=today,
                clock=clock,
                cache=cache,
                reflections_root=reflections_root,
                completion_cache_path=completion_cache_path,
                docs_html_path=docs_html_path,
                docs_data_path=docs_data_path,
                docs_css_path=docs_css_path,
                completion_factory=completion_factory,
            )
        except Exception as e:
            logger.warning("dashboard render failed: %s", e)
            dashboard_status = "error"

    return RunSummary(
        today=today,
        created=created,
        skipped=skipped,
        errors=errors,
        decisions=decisions,
        stub_decisions=stub_decisions,
        metadata_updated=metadata_updated,
        dashboard_status=dashboard_status,
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
    stubs_created = [s for s in summary.stub_decisions if s.decision == "CREATED"]
    dashboard_line = (
        f"- Dashboard: {summary.dashboard_status}\n"
        if summary.dashboard_status is not None
        else ""
    )
    entry = (
        f"## {summary.today.isoformat()} ({tz_name})\n"
        f"- Run at: {when}\n"
        f"- Created: {len(summary.created)} "
        f"({', '.join(r.template_id for r in summary.created) or 'none'})\n"
        f"- Skipped (cache hit): {len(summary.skipped)} "
        f"({', '.join(r.template_id for r in summary.skipped) or 'none'})\n"
        f"- Reflection stubs created: {len(stubs_created)} "
        f"({', '.join(s.path for s in stubs_created) or 'none'})\n"
        f"- Reflection metadata updated: {summary.metadata_updated}\n"
        f"{dashboard_line}"
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
    p.add_argument(
        "--cleanup-project",
        metavar="ID",
        help=(
            "Destructive: list (and with --yes, delete) ALL tasks in this "
            "Todoist project. Use against sandbox projects only."
        ),
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive operations (only meaningful with --cleanup-project).",
    )
    p.add_argument(
        "--skip-dashboard",
        action="store_true",
        help="Skip the Phase E dashboard render. Default is to render.",
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

    if summary.stub_decisions:
        print("", file=out)
        print("REFLECTION STUBS", file=out)
        srows = [
            (s.path, s.decision, s.via_template_id) for s in summary.stub_decisions
        ]
        path_w = max(len("PATH"), max(len(r[0]) for r in srows))
        sdec_w = max(len("DECISION"), max(len(r[1]) for r in srows))
        via_w = max(len("VIA TEMPLATE"), max(len(r[2]) for r in srows))
        sfmt = f"{{:<{path_w}}}  {{:<{sdec_w}}}  {{:<{via_w}}}"
        print(sfmt.format("PATH", "DECISION", "VIA TEMPLATE"), file=out)
        for r in srows:
            print(sfmt.format(*r), file=out)


def cleanup_project(
    project_id: str,
    token: str,
    confirm: bool,
    cache_path: Path | None = None,
    admin_factory=None,
    out=None,
) -> int:
    """List (and on --yes, delete) all tasks in `project_id`.

    If --yes: also wipes `cache_path` so the next run gets a clean slate.
    Returns process exit code.
    """
    if out is None:
        out = sys.stdout
    if admin_factory is None:
        admin_factory = TodoistAdminClient

    admin = admin_factory(token=token)
    tasks = admin.list_tasks(project_id)
    print(f"Project {project_id}: {len(tasks)} task(s)", file=out)
    for t in tasks:
        tid = t.get("id", "?")
        content = t.get("content", "")
        print(f"  {tid}  {content}", file=out)

    if not confirm:
        print(
            "\nDry-run (no --yes). Re-run with --yes to delete the tasks above.",
            file=out,
        )
        return 0

    if not tasks:
        print("\nNothing to delete.", file=out)
        return 0

    deleted = 0
    errors = 0
    for t in tasks:
        try:
            admin.delete_task(str(t["id"]))
            deleted += 1
        except Exception as e:
            logger.error("delete failed for task %s: %s", t.get("id"), e)
            errors += 1

    print(f"\nDeleted {deleted}/{len(tasks)} task(s); {errors} error(s).", file=out)

    if cache_path is not None and cache_path.exists():
        cache_path.unlink()
        print(f"Removed cache file {cache_path}.", file=out)

    return 0 if errors == 0 else 1


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    config = load_config(CONFIG_PATH, ENV_PATH)
    _setup_logging(config.todoist_token, verbose=args.verbose)

    if args.cleanup_project:
        return cleanup_project(
            project_id=args.cleanup_project,
            token=config.todoist_token,
            confirm=args.yes,
            cache_path=args.cache_file,
        )

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
        skip_dashboard=args.skip_dashboard,
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
