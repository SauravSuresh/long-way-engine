"""Daily run entrypoint.

Loads multi-syllabus config and shared state; iterates over enabled
syllabuses in priority order; for each, creates Todoist tasks idempotently,
manages state mutations, persists cache / state / shared-state; then renders
the multi-syllabus dashboard.

Legacy `run()` (single-syllabus, takes Config + State + flat cache_path) is
kept intact so existing tests continue to pass without modification.
"""

from __future__ import annotations

import argparse
import logging
import sys
import dataclasses
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo

import json

from src.cache import (
    NamespacedCache,
    load_cache,
    load_namespaced_cache,
    prune,
    save_cache,
    save_namespaced_cache,
)
from src.clock import Clock, FrozenClock
from src.config import (
    Config,
    DashboardConfig,
    MultiSyllabusConfig,
    SyllabusEntry,
    TodoistConfig,
    TokenRedactingFilter,
    load_config,
    load_multi_syllabus_config,
)
from src.dashboard import (
    ReflectionMeta,
    render as render_dashboard,
    render_multi_syllabus,
    scan_reflections,
    write_css_if_absent,
)
from src.ids import external_id, module_external_id
from src.reflections import StubResult, create_stub, update_metadata
from src.scheduler import _is_last_saturday_of_month, should_create_today
from src.state import (
    SharedState,
    State,
    SyllabusState,
    load_shared_state,
    load_state,
    load_syllabus_state,
    save_shared_state,
    save_state,
    save_syllabus_state,
    update_derived_fields,
)
from src.state_review import (
    PERSISTENT_EMERGENCY_PAUSE_DESC,
    PERSISTENT_EMERGENCY_PAUSE_TITLE,
    PERSISTENT_RESUME_DESC,
    PERSISTENT_RESUME_TITLE,
    StateReviewSummary,
    evaluate_show_if,
    open_persistent_cache_entry,
    persistent_pause_external_id,
    persistent_resume_external_id,
    run_state_review_phase,
)
from src.syllabus import Syllabus, load_syllabus, load_syllabus_for_entry
from src.curriculum_validator import validate as validate_curriculum, validate_multi_syllabus
from src.templates import ResolvedTemplate, load_templates, resolve_variables
from src.todoist import (
    CreateResult,
    TodoistAdminClient,
    TodoistClient,
    TodoistCompletionClient,
)
from src.todoist_review import TodoistReviewClient

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"
# Legacy single-syllabus state path — kept so test monkeypatches still work.
STATE_PATH = REPO_ROOT / "state.yaml"
SHARED_STATE_PATH = REPO_ROOT / "state" / "shared.yaml"
ENV_PATH = REPO_ROOT / ".env"
# Legacy curriculum paths — kept so test monkeypatches still work.
CURRICULUM_DIR = REPO_ROOT / "curriculum"
RITUALS_DIR = CURRICULUM_DIR / "rituals"
MODULES_PATH = CURRICULUM_DIR / "modules.yaml"
CACHE_PATH = REPO_ROOT / ".task_cache.json"
STATE_LOG_PATH = REPO_ROOT / "state_log.yaml"
LOG_PATH = REPO_ROOT / "LOG.md"
REFLECTIONS_DIR = REPO_ROOT / "reflections"
REFLECTION_TEMPLATES_DIR = CURRICULUM_DIR / "reflection_templates"
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
    state_review: StateReviewSummary | None = None


@dataclass
class AggregateSummary:
    """Combined summary across all syllabuses in the loop."""
    today: date | None = None
    created: list[CreateResult] = field(default_factory=list)
    skipped: list[CreateResult] = field(default_factory=list)
    errors: int = 0
    decisions: list[Decision] = field(default_factory=list)
    stub_decisions: list[StubDecision] = field(default_factory=list)
    metadata_updated: int = 0
    dashboard_status: str | None = None

    def merge(self, summary: RunSummary) -> None:
        if self.today is None:
            self.today = summary.today
        self.created.extend(summary.created)
        self.skipped.extend(summary.skipped)
        self.errors += summary.errors
        self.decisions.extend(summary.decisions)
        self.stub_decisions.extend(summary.stub_decisions)
        self.metadata_updated += summary.metadata_updated
        if summary.dashboard_status is not None:
            self.dashboard_status = summary.dashboard_status

    def to_run_summary(self) -> RunSummary:
        return RunSummary(
            today=self.today or date.today(),
            created=self.created,
            skipped=self.skipped,
            errors=self.errors,
            decisions=self.decisions,
            stub_decisions=self.stub_decisions,
            metadata_updated=self.metadata_updated,
            dashboard_status=self.dashboard_status,
        )


def _setup_logging(token: str, verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger().addFilter(TokenRedactingFilter(token))


def _classify_skip(template, state: State | SyllabusState, config: Config, today: date) -> str:
    """Human-readable label for why this template did not fire today."""
    if state.paused:
        return "SKIP (paused)"
    # Global Sunday-off mirrors scheduler.should_create_today: when set,
    # NO cadence fires on Sundays — surface this uniformly in the dry-run
    # table so the operator sees one consistent reason across all rows.
    if config.sunday_off and today.weekday() == 6:
        return "SKIP (Sunday)"
    cadence = template.cadence
    if cadence == "daily":
        rules = template.skip_if
        if (
            "pair_day" in rules
            and config.pair_day
            and today.strftime("%A").lower() == config.pair_day.lower()
        ):
            return "SKIP (pair day)"
        return "SKIP (rule)"
    if cadence == "weekly":
        day = template.day_of_week or "?"
        if (
            template.day_of_week
            and today.weekday() == "monday tuesday wednesday thursday friday saturday sunday".split().index(template.day_of_week.lower())
            and "last-saturday-of-month" in template.skip_if
            and _is_last_saturday_of_month(today)
        ):
            return "SKIP (last Saturday)"
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
    state: State | SyllabusState,
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


def _ensure_persistent_tasks(
    client,
    cache: dict,
    state: State | SyllabusState,
    today: date,
    syllabus_key: str = "",
) -> None:
    """Create emergency-pause + resume tasks if none currently open.

    `resume` is only created when state.paused is true. Both tasks have
    no due date — they sit in the Todoist inbox until checked.
    """
    if open_persistent_cache_entry(cache, "emergency-pause") is None:
        ext_id = persistent_pause_external_id(today)
        tpl = ResolvedTemplate(
            id="persistent-emergency-pause",
            title=PERSISTENT_EMERGENCY_PAUSE_TITLE,
            description=PERSISTENT_EMERGENCY_PAUSE_DESC,
            due="",
            labels=["state-review"],
            cadence="daily",
            syllabus_key=syllabus_key,
        )
        try:
            result = client.create_task_idempotent(tpl, today, ext_id, cache)
        except Exception as e:
            logger.warning("persistent emergency-pause create failed: %s", e)
            return
        cache.setdefault(ext_id, {})
        if not result.skipped:
            cache[ext_id].update({
                "todoist_task_id": result.todoist_task_id,
                "created_at": result.created_at,
                "template_id": tpl.id,
                "due_date": "persistent",
            })
        cache[ext_id].update({
            "persistent_category": "emergency-pause",
            "persistent_action": {
                "type": "set_pause",
                "days": 365,
                "reason": "emergency",
            },
            "persistent_consumed": False,
        })

    if state.paused and open_persistent_cache_entry(cache, "resume") is None:
        ext_id = persistent_resume_external_id(today)
        tpl = ResolvedTemplate(
            id="persistent-resume",
            title=PERSISTENT_RESUME_TITLE,
            description=PERSISTENT_RESUME_DESC,
            due="",
            labels=["state-review"],
            cadence="daily",
            syllabus_key=syllabus_key,
        )
        try:
            result = client.create_task_idempotent(tpl, today, ext_id, cache)
        except Exception as e:
            logger.warning("persistent resume create failed: %s", e)
            return
        cache.setdefault(ext_id, {})
        if not result.skipped:
            cache[ext_id].update({
                "todoist_task_id": result.todoist_task_id,
                "created_at": result.created_at,
                "template_id": tpl.id,
                "due_date": "persistent",
            })
        cache[ext_id].update({
            "persistent_category": "resume",
            "persistent_action": {"type": "unset_pause"},
            "persistent_consumed": False,
        })


def _module_titles_from_templates(templates) -> dict[int, str]:
    """Map module_number -> onboarding template title for the dashboard's
    module trunk. Lineage detours are excluded; they share a module_number
    but the trunk is the onboarding spine."""
    return {
        tpl.module_number: tpl.title
        for tpl in templates
        if tpl.cadence == "once-per-module"
        and tpl.module_number is not None
        and tpl.id.endswith("-onboarding")
    }


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
    module_titles: dict[int, str],
    syllabus: Syllabus | None = None,
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
    books = syllabus.books if syllabus is not None else []

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
        module_titles=module_titles,
        syllabus=syllabus,
    )

    docs_html_path.parent.mkdir(parents=True, exist_ok=True)
    docs_data_path.parent.mkdir(parents=True, exist_ok=True)
    docs_html_path.write_text(html, encoding="utf-8")
    docs_data_path.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return "ok"


# ---------------------------------------------------------------------------
# Legacy single-syllabus run() — kept for backward compatibility.
# Tests import and call this directly with Config + State + cache_path.
# ---------------------------------------------------------------------------


def run(
    config: Config,
    state: State,
    today: date,
    template_paths: list[Path],
    cache_path: Path,
    client_factory=None,
    clock: Clock | None = None,
    dry_run: bool = False,
    project_id: str | None = None,
    reflections_root: Path | None = None,
    reflection_templates_root: Path | None = None,
    skip_dashboard: bool = False,
    sweep: bool = True,
    admin_factory=None,
    completion_factory=None,
    review_factory=None,
    completion_cache_path: Path | None = None,
    docs_html_path: Path | None = None,
    docs_data_path: Path | None = None,
    docs_css_path: Path | None = None,
    state_path: Path | None = None,
    state_log_path: Path | None = None,
    syllabus=None,
) -> RunSummary:
    if clock is None:
        clock = Clock(state.timezone)
    if client_factory is None:
        # Lookup at call time so module-level patches in tests take effect.
        client_factory = TodoistClient
    if completion_factory is None:
        completion_factory = TodoistCompletionClient
    if review_factory is None:
        review_factory = TodoistReviewClient
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
    if state_path is None:
        state_path = STATE_PATH
    if state_log_path is None:
        state_log_path = STATE_LOG_PATH

    cache = load_cache(cache_path)
    templates = load_templates(template_paths)

    # PHASE 1: state-mutation.
    # NOTE: state-review is only available via run_for_syllabus().
    # The legacy run() is retained for backwards-compatibility with tests that
    # call it directly with Config + State + flat cache_path. The old
    # `if syllabus is not None:` branch that called run_state_review_phase()
    # with a 2-tuple unpack was removed here because run_state_review_phase()
    # now returns a 3-tuple (state, shared, summary) and requires shared/shared_path
    # kwargs. Use run_for_syllabus() for any code path that needs state-review.
    state_review_summary: StateReviewSummary | None = None
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

        resolved = resolve_variables(tpl, state, config, today, syllabus=syllabus)
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

        # state-review sub-tasks: create one Todoist sub-task per resolved
        # SubtaskSpec whose show_if predicate is true today. Mark each
        # cache entry with `state_review_action` so the next cron can
        # dispatch the mutation when the sub-task is checked. The parent
        # entry gets `state_review_parent: true` for orchestrator lookup.
        if resolved.state_review and syllabus is not None and tpl.cadence == "weekly":
            cache.setdefault(ext_id, {})["state_review_parent"] = True
            parent_task_id = (
                cache[ext_id].get("todoist_task_id") or result.todoist_task_id
            )
            for i, sub in enumerate(resolved.sub_tasks):
                if not evaluate_show_if(sub.show_if, state, syllabus):
                    continue
                sub_ext_id = external_id(f"{tpl.id}:sub:{i}", today)
                sub_resolved = ResolvedTemplate(
                    id=f"{tpl.id}:sub:{i}",
                    title=sub.title,
                    description="",
                    due="",
                    labels=list(resolved.labels),
                    cadence=resolved.cadence,
                    skip_if=[],
                )
                try:
                    sub_result = client.create_task_idempotent(
                        sub_resolved, today, sub_ext_id, cache,
                        parent_id=str(parent_task_id),
                    )
                except Exception as e:
                    logger.error("sub-task %s create failed: %s", sub_ext_id, e)
                    errors += 1
                    continue
                if not sub_result.skipped:
                    cache[sub_ext_id] = {
                        "todoist_task_id": sub_result.todoist_task_id,
                        "created_at": sub_result.created_at,
                        "template_id": sub_resolved.id,
                        "due_date": today.isoformat(),
                    }
                cache[sub_ext_id]["state_review_action"] = dict(sub.action)
                cache[sub_ext_id]["state_review_parent_task_id"] = str(parent_task_id)

            # Auto-inject one mark_track_finished sub-task per `current`
            # track. Narrow carve-out from the curriculum-authored rule
            # (spec section 5). Stable external_id keyed off
            # (parent_ext_id, "auto-finish", category, title) so the same
            # current track produces the same sub-task each week.
            sub_idx = len(resolved.sub_tasks)
            for category, items in sorted(state.learning_tracks.items()):
                for title, lifecycle_state in sorted(items.items()):
                    if lifecycle_state != "current":
                        continue
                    auto_key = f"{tpl.id}:auto-finish:{category}:{title}"
                    auto_ext_id = external_id(auto_key, today)
                    auto_resolved = ResolvedTemplate(
                        id=f"{tpl.id}:auto-finish:{sub_idx}",
                        title=f"I finished [{category}: {title}]",
                        description="",
                        due="",
                        labels=list(resolved.labels),
                        cadence=resolved.cadence,
                        skip_if=[],
                    )
                    try:
                        auto_result = client.create_task_idempotent(
                            auto_resolved, today, auto_ext_id, cache,
                            parent_id=str(parent_task_id),
                        )
                    except Exception as e:
                        logger.error("auto-finish sub-task %s create failed: %s", auto_ext_id, e)
                        errors += 1
                        continue
                    if not auto_result.skipped:
                        cache[auto_ext_id] = {
                            "todoist_task_id": auto_result.todoist_task_id,
                            "created_at": auto_result.created_at,
                            "template_id": auto_resolved.id,
                            "due_date": today.isoformat(),
                        }
                    cache[auto_ext_id]["state_review_action"] = {
                        "type": "mark_track_finished",
                        "category": category,
                        "item": title,
                    }
                    cache[auto_ext_id]["state_review_parent_task_id"] = str(parent_task_id)
                    sub_idx += 1

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

    # Persistent emergency-pause / resume tasks. Created once per
    # consumption cycle; the state-review phase marks them consumed on
    # completion, and the next cron creates a fresh instance with a new
    # versioned external_id. Always-on (no Sunday gate) — emergencies
    # don't respect rest days.
    if not dry_run and syllabus is not None:
        _ensure_persistent_tasks(client, cache, state, today)

    sweep_result = SweepResult()
    if sweep:
        sweep_admin = (admin_factory or TodoistAdminClient)(token=config.todoist_token)
        sweep_completion = (completion_factory or TodoistCompletionClient)(
            token=config.todoist_token,
            cache_path=completion_cache_path,
            project_id=project_id or config.todoist.project_id,
            clock=clock,
        )
        sweep_result = sweep_past_due(
            cache,
            today=today,
            completion_client=sweep_completion,
            admin_client=sweep_admin,
            dry_run=dry_run,
        )
        if sweep_result.checked:
            logger.info(
                "sweep: checked=%d completed=%d missed=%d deleted=%d errors=%d",
                sweep_result.checked,
                sweep_result.completed_marked,
                sweep_result.missed_marked,
                sweep_result.deleted,
                sweep_result.errors,
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
                module_titles=_module_titles_from_templates(templates),
                syllabus=syllabus,
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
        state_review=state_review_summary,
    )


# ---------------------------------------------------------------------------
# Per-syllabus run — used by the multi-syllabus main() loop.
# ---------------------------------------------------------------------------


def run_for_syllabus(
    *,
    cfg: MultiSyllabusConfig,
    entry: SyllabusEntry,
    state: SyllabusState,
    shared: SharedState,
    syllabus: Syllabus,
    today: date,
    clock: Clock,
    cache: NamespacedCache,
    template_paths: list[Path] | None = None,
    client_factory=None,
    dry_run: bool = False,
    sweep: bool = True,
    admin_factory=None,
    completion_factory=None,
    review_factory=None,
    state_log_path: Path | None = None,
    reflections_root_override: Path | None = None,
) -> tuple[RunSummary, SyllabusState, SharedState, dict[str, Any]]:
    """Execute one syllabus' daily run.

    Returns (summary, new_state, new_shared, dashboard_data).

    `dashboard_data` is a dict with keys: completion_set, module_titles,
    books — consumed by main() when assembling the multi-syllabus render.
    """
    if client_factory is None:
        client_factory = TodoistClient
    if completion_factory is None:
        completion_factory = TodoistCompletionClient
    if review_factory is None:
        review_factory = TodoistReviewClient

    # Per-syllabus paths derived from entry.
    if template_paths is None:
        template_paths = [entry.path / "rituals", entry.path / "modules.yaml"]
    reflections_root = reflections_root_override or (REFLECTIONS_DIR / entry.key)
    reflection_templates_root = entry.path / "reflection_templates"
    if state_log_path is None:
        state_log_path = REPO_ROOT / "state" / f"{entry.key}_state_log.yaml"

    # Per-syllabus cache slice: a live mutable dict inside nc.data.
    # Downstream mutations land directly in the namespaced structure.
    syllabus_cache = cache.data.setdefault(entry.key, {})

    # Config shim so legacy callees (scheduler, templates, state_review) keep
    # working. Config is NOT removed — it acts as an internal adapter here.
    per_syllabus_cfg_shim = Config(
        todoist=TodoistConfig(project_id=entry.todoist_project_id, labels={}),
        ritual_times=entry.ritual_times,
        sunday_off=cfg.sunday_off,
        pair_day=cfg.pair_day,
        dashboard=cfg.dashboard,
        todoist_token=cfg.todoist_token,
        curriculum_dir=entry.path,
    )

    templates = load_templates(template_paths)

    # PHASE 1: state-mutation.
    state_review_summary: StateReviewSummary | None = None
    state, shared, state_review_summary = run_state_review_phase(
        config=per_syllabus_cfg_shim,
        state=state,
        shared=shared,
        syllabus=syllabus,
        today=today,
        cache=syllabus_cache,
        state_path=entry.state_file,
        shared_path=SHARED_STATE_PATH,
        state_log_path=state_log_path,
        review_factory=review_factory,
        completion_factory=completion_factory,
        dry_run=dry_run,
        todoist_token=cfg.todoist_token,
        project_id=entry.todoist_project_id,
    )

    # Derive month/phase and persist per-syllabus state.
    state = update_derived_fields(state, syllabus, today)  # type: ignore[assignment]
    if not dry_run:
        save_syllabus_state(entry.state_file, state)

    client = client_factory(
        token=cfg.todoist_token,
        project_id=entry.todoist_project_id,
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
            if not should_create_today(tpl, today, state, per_syllabus_cfg_shim):
                label = _classify_skip(tpl, state, per_syllabus_cfg_shim, today)
                logger.info("[%s] template %s: %s", entry.key, tpl.id, label.lower())
                decisions.append(Decision(tpl.id, None, label))
                continue
        except NotImplementedError as e:
            logger.warning("[%s] template %s: %s", entry.key, tpl.id, e)
            decisions.append(Decision(tpl.id, None, "ERROR (cadence)"))
            errors += 1
            continue

        resolved = resolve_variables(tpl, state, per_syllabus_cfg_shim, today, syllabus=syllabus)
        if resolved is None:
            decisions.append(Decision(tpl.id, None, "ERROR (variable)"))
            errors += 1
            continue
        resolved = dataclasses.replace(resolved, syllabus_key=entry.key)

        if tpl.cadence == "once-per-module":
            assert tpl.module_number is not None
            ext_id = module_external_id(tpl.id, tpl.module_number)
            cache_due = f"module:{tpl.module_number}"
        else:
            ext_id = external_id(tpl.id, today)
            cache_due = today.isoformat()

        try:
            result = client.create_task_idempotent(resolved, today, ext_id, syllabus_cache)
        except Exception as e:
            logger.error("[%s] template %s: create failed: %s", entry.key, tpl.id, e)
            decisions.append(Decision(tpl.id, ext_id, "ERROR (api)"))
            errors += 1
            continue

        if result.skipped:
            skipped.append(result)
            decisions.append(Decision(tpl.id, ext_id, "SKIP (cache hit)"))
        else:
            created.append(result)
            decisions.append(Decision(tpl.id, ext_id, "WOULD CREATE" if dry_run else "CREATED"))
            syllabus_cache[ext_id] = {
                "todoist_task_id": result.todoist_task_id,
                "created_at": result.created_at,
                "template_id": result.template_id,
                "due_date": cache_due,
            }

        if resolved.state_review and tpl.cadence == "weekly":
            syllabus_cache.setdefault(ext_id, {})["state_review_parent"] = True
            parent_task_id = (
                syllabus_cache[ext_id].get("todoist_task_id") or result.todoist_task_id
            )
            for i, sub in enumerate(resolved.sub_tasks):
                if not evaluate_show_if(sub.show_if, state, syllabus):
                    continue
                sub_ext_id = external_id(f"{tpl.id}:sub:{i}", today)
                sub_resolved = ResolvedTemplate(
                    id=f"{tpl.id}:sub:{i}",
                    title=sub.title,
                    description="",
                    due="",
                    labels=list(resolved.labels),
                    cadence=resolved.cadence,
                    skip_if=[],
                )
                try:
                    sub_result = client.create_task_idempotent(
                        sub_resolved, today, sub_ext_id, syllabus_cache,
                        parent_id=str(parent_task_id),
                    )
                except Exception as e:
                    logger.error("[%s] sub-task %s create failed: %s", entry.key, sub_ext_id, e)
                    errors += 1
                    continue
                if not sub_result.skipped:
                    syllabus_cache[sub_ext_id] = {
                        "todoist_task_id": sub_result.todoist_task_id,
                        "created_at": sub_result.created_at,
                        "template_id": sub_resolved.id,
                        "due_date": today.isoformat(),
                    }
                syllabus_cache[sub_ext_id]["state_review_action"] = dict(sub.action)
                syllabus_cache[sub_ext_id]["state_review_parent_task_id"] = str(parent_task_id)

            sub_idx = len(resolved.sub_tasks)
            for category, items in sorted(state.learning_tracks.items()):
                for title_item, lifecycle_state in sorted(items.items()):
                    if lifecycle_state != "current":
                        continue
                    auto_key = f"{tpl.id}:auto-finish:{category}:{title_item}"
                    auto_ext_id = external_id(auto_key, today)
                    auto_resolved = ResolvedTemplate(
                        id=f"{tpl.id}:auto-finish:{sub_idx}",
                        title=f"I finished [{category}: {title_item}]",
                        description="",
                        due="",
                        labels=list(resolved.labels),
                        cadence=resolved.cadence,
                        skip_if=[],
                    )
                    try:
                        auto_result = client.create_task_idempotent(
                            auto_resolved, today, auto_ext_id, syllabus_cache,
                            parent_id=str(parent_task_id),
                        )
                    except Exception as e:
                        logger.error("[%s] auto-finish %s create failed: %s", entry.key, auto_ext_id, e)
                        errors += 1
                        continue
                    if not auto_result.skipped:
                        syllabus_cache[auto_ext_id] = {
                            "todoist_task_id": auto_result.todoist_task_id,
                            "created_at": auto_result.created_at,
                            "template_id": auto_resolved.id,
                            "due_date": today.isoformat(),
                        }
                    syllabus_cache[auto_ext_id]["state_review_action"] = {
                        "type": "mark_track_finished",
                        "category": category,
                        "item": title_item,
                    }
                    syllabus_cache[auto_ext_id]["state_review_parent_task_id"] = str(parent_task_id)
                    sub_idx += 1

        _record_stub(
            tpl,
            state,
            per_syllabus_cfg_shim,
            today,
            reflections_root,
            reflection_templates_root,
            pending_paths,
            dry_run,
            stub_decisions,
        )

    if not dry_run:
        _ensure_persistent_tasks(client, syllabus_cache, state, today, syllabus_key=entry.key)

    if sweep:
        sweep_admin = (admin_factory or TodoistAdminClient)(token=cfg.todoist_token)
        sweep_completion = (completion_factory or TodoistCompletionClient)(
            token=cfg.todoist_token,
            cache_path=COMPLETION_CACHE_PATH,
            project_id=entry.todoist_project_id,
            clock=clock,
        )
        sweep_result = sweep_past_due(
            syllabus_cache,
            today=today,
            completion_client=sweep_completion,
            admin_client=sweep_admin,
            dry_run=dry_run,
        )
        if sweep_result.checked:
            logger.info(
                "[%s] sweep: checked=%d completed=%d missed=%d deleted=%d errors=%d",
                entry.key,
                sweep_result.checked,
                sweep_result.completed_marked,
                sweep_result.missed_marked,
                sweep_result.deleted,
                sweep_result.errors,
            )

    # Prune per-syllabus cache slice in place.
    pruned = prune(syllabus_cache, now=clock.now().astimezone(timezone.utc))
    syllabus_cache.clear()
    syllabus_cache.update(pruned)

    metadata_updated = 0
    if not dry_run:
        metadata_updated = update_metadata(reflections_root, reflection_templates_root)

    summary = RunSummary(
        today=today,
        created=created,
        skipped=skipped,
        errors=errors,
        decisions=decisions,
        stub_decisions=stub_decisions,
        metadata_updated=metadata_updated,
        dashboard_status=None,  # dashboard rendered once in main() after all syllabuses
        state_review=state_review_summary,
    )

    # Build per-syllabus dashboard inputs for the post-loop render.
    completion_set: set[str] = {
        str(entry_v["todoist_task_id"])
        for entry_v in syllabus_cache.values()
        if entry_v.get("todoist_task_id")
        and not str(entry_v["todoist_task_id"]).startswith("DRY-RUN")
    }
    dashboard_data: dict[str, Any] = {
        "completion_set": completion_set,
        "module_titles": _module_titles_from_templates(templates),
        "books": syllabus.books,
        "reflections_root": reflections_root,
    }

    return summary, state, shared, dashboard_data


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


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
    p.add_argument(
        "--no-sweep",
        action="store_true",
        help=(
            "Skip the daily sweep of past-due Todoist tasks. By default each "
            "run resolves cache entries whose due_date is before today: "
            "completed ones get status=completed; uncompleted ones get "
            "status=missed AND are deleted from Todoist."
        ),
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


@dataclass
class SweepResult:
    checked: int = 0
    completed_marked: int = 0
    missed_marked: int = 0
    deleted: int = 0
    errors: int = 0
    skipped: int = 0  # dry-run or sweep disabled


def sweep_past_due(
    cache: dict[str, dict],
    *,
    today: date,
    completion_client,
    admin_client,
    dry_run: bool,
) -> SweepResult:
    """Daily sweep: for cache entries whose due_date is before today and
    whose status is not yet recorded, either mark them completed (if the
    Todoist completion API confirms it) or delete them from Todoist and
    mark them missed in the cache.

    Mutates `cache` in place. The caller persists it via save_cache().
    In dry-run: no API calls, no cache writes — just logs.
    """
    result = SweepResult()

    candidates: list[tuple[str, str, date]] = []  # (ext_id, task_id, due)
    for ext_id, entry in cache.items():
        due_raw = entry.get("due_date")
        if not isinstance(due_raw, str) or due_raw.startswith("module:"):
            continue
        try:
            due = date.fromisoformat(due_raw)
        except ValueError:
            continue
        if due >= today:
            continue
        if entry.get("status") in ("missed", "completed"):
            continue
        task_id = str(entry.get("todoist_task_id") or "")
        if not task_id or task_id.startswith("DRY-RUN-"):
            continue
        candidates.append((ext_id, task_id, due))

    result.checked = len(candidates)
    if not candidates:
        return result

    if dry_run:
        result.skipped = len(candidates)
        for ext_id, task_id, due in candidates:
            logger.info(
                "DRY RUN sweep: would resolve past-due task %s (ext=%s, due=%s)",
                task_id, ext_id, due.isoformat(),
            )
        return result

    try:
        statuses = completion_client.get_completion_status(
            [task_id for _, task_id, _ in candidates]
        )
    except Exception as e:
        logger.error("sweep: completion lookup failed (%s); skipping sweep", e)
        result.errors = 1
        return result

    today_iso = today.isoformat()
    for ext_id, task_id, due in candidates:
        if statuses.get(task_id):
            cache[ext_id]["status"] = "completed"
            cache[ext_id]["completed_at"] = today_iso
            result.completed_marked += 1
            logger.info(
                "sweep: marked completed (ext=%s, due=%s)", ext_id, due.isoformat(),
            )
            continue
        try:
            admin_client.delete_task(task_id)
            result.deleted += 1
        except Exception as e:
            msg = str(e)
            if "404" in msg:
                # Already gone from Todoist (user deleted manually). Still
                # record the miss in cache so the dashboard reflects it.
                logger.info(
                    "sweep: task %s already 404 in Todoist; marking missed", task_id,
                )
            else:
                logger.error(
                    "sweep: delete failed for %s (%s); leaving for retry next run",
                    task_id, e,
                )
                result.errors += 1
                continue
        cache[ext_id]["status"] = "missed"
        cache[ext_id]["missed_at"] = today_iso
        result.missed_marked += 1
        logger.info(
            "sweep: marked missed and deleted (ext=%s, due=%s)",
            ext_id, due.isoformat(),
        )

    return result


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


# ---------------------------------------------------------------------------
# Multi-syllabus main()
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    cfg = load_multi_syllabus_config(CONFIG_PATH, ENV_PATH)
    _setup_logging(cfg.todoist_token, verbose=args.verbose)

    if args.cleanup_project:
        return cleanup_project(
            project_id=args.cleanup_project,
            token=cfg.todoist_token,
            confirm=args.yes,
            cache_path=args.cache_file,
        )

    errors = validate_multi_syllabus(cfg.syllabuses, repo_root=REPO_ROOT)
    if errors:
        for e in errors:
            logger.error("config: %s", e)
        print("config validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 2

    shared = load_shared_state(SHARED_STATE_PATH)
    nc = load_namespaced_cache(args.cache_file or CACHE_PATH)

    if args.today is not None:
        clock: Clock = FrozenClock(args.today, shared.timezone)
        today = args.today
    else:
        clock = Clock(shared.timezone)
        today = clock.today()

    logger.info(
        "daily run start: today=%s tz=%s dry_run=%s syllabuses=%s",
        today,
        shared.timezone.key,
        args.dry_run,
        list(cfg.priority_order),
    )

    # Accumulators for the dashboard render and log.
    per_syllabus_states: dict[str, SyllabusState] = {}
    syllabuses_parsed: dict[str, Syllabus] = {}
    per_syllabus_completion: dict[str, set[str]] = {}
    per_syllabus_module_titles: dict[str, dict[int, str]] = {}
    per_syllabus_books: dict[str, list] = {}
    per_syllabus_reflections_root: dict[str, Path] = {}

    aggregate = AggregateSummary()
    new_shared = shared

    for key in cfg.priority_order:
        entry = cfg.syllabuses[key]
        if not entry.enabled:
            continue

        state = load_syllabus_state(entry.state_file)
        syllabus = load_syllabus_for_entry(entry)

        per_summary, state, new_shared, dash_data = run_for_syllabus(
            cfg=cfg,
            entry=entry,
            state=state,
            shared=new_shared,
            syllabus=syllabus,
            today=today,
            clock=clock,
            cache=nc,
            dry_run=args.dry_run,
            sweep=not args.no_sweep,
        )

        aggregate.merge(per_summary)
        per_syllabus_states[key] = state
        syllabuses_parsed[key] = syllabus
        per_syllabus_completion[key] = dash_data["completion_set"]
        per_syllabus_module_titles[key] = dash_data["module_titles"]
        per_syllabus_books[key] = dash_data["books"]
        per_syllabus_reflections_root[key] = dash_data["reflections_root"]

    # After all syllabuses: persist cache + shared state, render dashboard.
    if not args.dry_run:
        save_namespaced_cache(args.cache_file or CACHE_PATH, nc)
        if new_shared is not shared:
            save_shared_state(SHARED_STATE_PATH, new_shared)

        if not args.skip_dashboard:
            try:
                per_syllabus_reflections: dict[str, list[ReflectionMeta]] = {
                    key: scan_reflections(per_syllabus_reflections_root[key])
                    for key in cfg.priority_order
                    if cfg.syllabuses[key].enabled
                }
                per_syllabus_cache_data: dict[str, dict] = {
                    key: nc.data.get(key, {})
                    for key in cfg.priority_order
                    if cfg.syllabuses[key].enabled
                }

                html, data = render_multi_syllabus(
                    cfg=cfg,
                    shared=new_shared,
                    syllabus_states=per_syllabus_states,
                    syllabuses=syllabuses_parsed,
                    completion_by_syllabus=per_syllabus_completion,
                    cache_by_syllabus=per_syllabus_cache_data,
                    reflections_by_syllabus=per_syllabus_reflections,
                    books_by_syllabus=per_syllabus_books,
                    today=today,
                    clock=clock,
                    reflections_root=REFLECTIONS_DIR,
                    module_titles_by_syllabus=per_syllabus_module_titles,
                )
                DOCS_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
                DOCS_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
                DOCS_HTML_PATH.write_text(html, encoding="utf-8")
                DOCS_DATA_PATH.write_text(
                    json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
                    encoding="utf-8",
                )
                write_css_if_absent(DOCS_CSS_PATH)
                aggregate.dashboard_status = "ok"
            except Exception as e:
                logger.warning("dashboard render failed: %s", e)
                aggregate.dashboard_status = "error"
        else:
            aggregate.dashboard_status = "skipped"

    summary = aggregate.to_run_summary()

    if args.dry_run:
        _print_dry_run_table(summary)
    else:
        # Use timezone from shared state for the log timestamp.
        append_log(LOG_PATH, summary, shared.timezone.key, clock=clock)

    logger.info(
        "daily run done: created=%d skipped=%d errors=%d",
        len(summary.created),
        len(summary.skipped),
        summary.errors,
    )
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    # Cron / CLI entry: load config once, run the curriculum validator for
    # fail-fast safety, then hand off to main() which re-loads config.
    _bootstrap_cfg = load_multi_syllabus_config(CONFIG_PATH, ENV_PATH)
    _bootstrap_shared = load_shared_state(SHARED_STATE_PATH)
    for _key in _bootstrap_cfg.priority_order:
        _entry = _bootstrap_cfg.syllabuses[_key]
        if not _entry.enabled:
            continue
        _bootstrap_state = load_syllabus_state(_entry.state_file)
        validate_curriculum(
            _entry.path,
            ritual_times=_entry.ritual_times,
            state_current_module=_bootstrap_state.current_module,
            state_month=_bootstrap_state.month,
            state_learning_tracks=_bootstrap_state.learning_tracks,
        )
    sys.exit(main())
