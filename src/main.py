"""Daily run entrypoint.

Loads state, config, and templates; computes today in the owner's TZ;
for each daily template that should fire, creates the Todoist task
idempotently; persists the cache and appends a LOG.md entry.

Phase A scope: daily cadence + Sunday skip only. No reflections, no
dashboard, no weekly/monthly/quarterly cadences, no `paused` short-circuit.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from src.cache import load_cache, prune, save_cache
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
class RunSummary:
    today: date
    created: list[CreateResult]
    skipped: list[CreateResult]
    errors: int


def _setup_logging(token: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger().addFilter(TokenRedactingFilter(token))


def _today(state: State) -> date:
    return datetime.now(tz=state.timezone).date()


def run(
    config: Config,
    state: State,
    today: date,
    templates_dir: Path,
    cache_path: Path,
    client_factory=TodoistClient,
) -> RunSummary:
    cache = load_cache(cache_path)
    templates = load_templates(templates_dir)
    client = client_factory(token=config.todoist_token, project_id=config.todoist.project_id)

    created: list[CreateResult] = []
    skipped: list[CreateResult] = []
    errors = 0

    for tpl in templates:
        try:
            if not should_create_today(tpl, today, state, config):
                logger.info("template %s: skip rule applied", tpl.id)
                continue
        except NotImplementedError as e:
            logger.warning("template %s: %s", tpl.id, e)
            errors += 1
            continue

        resolved = resolve_variables(tpl, state, config)
        if resolved is None:
            errors += 1
            continue

        ext_id = external_id(tpl.id, today)
        try:
            result = client.create_task_idempotent(resolved, today, ext_id, cache)
        except Exception as e:
            logger.error("template %s: create failed: %s", tpl.id, e)
            errors += 1
            continue

        if result.skipped:
            skipped.append(result)
        else:
            created.append(result)
            cache[ext_id] = {
                "todoist_task_id": result.todoist_task_id,
                "created_at": result.created_at,
                "template_id": result.template_id,
                "due_date": result.due_date.isoformat(),
            }

    cache = prune(cache)
    save_cache(cache_path, cache)
    return RunSummary(today=today, created=created, skipped=skipped, errors=errors)


def append_log(log_path: Path, summary: RunSummary, tz_name: str) -> None:
    when = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
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


def main() -> int:
    config = load_config(CONFIG_PATH, ENV_PATH)
    _setup_logging(config.todoist_token)
    state = load_state(STATE_PATH)
    today = _today(state)
    logger.info("daily run start: today=%s tz=%s", today, state.timezone.key)
    summary = run(config, state, today, TEMPLATES_DIR, CACHE_PATH)
    append_log(LOG_PATH, summary, state.timezone.key)
    logger.info(
        "daily run done: created=%d skipped=%d errors=%d",
        len(summary.created),
        len(summary.skipped),
        summary.errors,
    )
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
