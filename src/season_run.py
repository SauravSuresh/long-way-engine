"""Seasons layer inside the daily run (wayfinder #11).

Glue between the forecast (who holds today's deep block) and the engine:
pause reconciliation, off-season / slot gating of syllabus rituals, the
generic deep-block + discipline tasks, and crediting completed blocks as
logged minutes. Everything here is called from main.py; the pure parts
take explicit inputs so they test without IO.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.forecast import REST_DAYS, Forecast, forecast
from src.seasons import (
    WEEKDAYS,
    DeepBlock,
    Milestone,
    MilestoneProgress,
    Seasons,
    SeasonsState,
    SyllabusFacts,
    load_seasons,
    load_seasons_state,
    save_seasons_state,
    validate,
)
from src.state import SyllabusState
from src.state_mutations import unset_pause
from src.templates import ResolvedTemplate

logger = logging.getLogger(__name__)

SEASONS_NS = "seasons"  # cache namespace for bare blocks + disciplines
SEASON_ACTOR = "seasons"  # todoist_task_id recorded on pause mutations


class SeasonsError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("seasons.yaml validation failed:\n  " + "\n  ".join(errors))
        self.errors = errors


@dataclass
class SeasonContext:
    seasons: Seasons
    state: SeasonsState
    fc: Forecast
    today: date

    # --- derived views ----------------------------------------------------

    def _by_id(self, mid: str | None) -> Milestone | None:
        return next((m for m in self.seasons.bucket if m.id == mid), None) if mid else None

    @property
    def main(self) -> Milestone | None:
        return self._by_id(self.fc.main)

    @property
    def side(self) -> Milestone | None:
        return self._by_id(self.fc.side)

    @property
    def resting(self) -> bool:
        return self.fc.resting

    def in_season(self) -> dict[str, Milestone]:
        """syllabus key -> milestone holding it today. Empty during rest week."""
        if self.resting:
            return {}
        return {m.syllabus: m for m in (self.main, self.side) if m is not None and m.syllabus}

    def block_today(self) -> DeepBlock | None:
        return self.seasons.rhythm.deep_blocks.get(WEEKDAYS[self.today.weekday()])

    def block_target(self) -> Milestone | None:
        """Who gets today's deep block (side-day fallback to main, and vice versa)."""
        block = self.block_today()
        if block is None or self.resting:
            return None
        if self.seasons.two_lanes and block.lane == "side":
            return self.side or self.main
        return self.main or self.side

    def milestone_label(self) -> str:
        return self.main.name if (self.main and not self.resting) else "Rest"

    # --- gating of syllabus rituals ------------------------------------------

    def ritual_allowed(self, syllabus_key: str, template: Any) -> bool:
        m = self.in_season().get(syllabus_key)
        if m is None:
            return False
        if _is_slot(template) and self.block_target() is not m:
            return False
        if m.track:
            for gate in getattr(template, "gated_by", None) or []:
                if isinstance(gate, dict) and gate.get("type") == "track":
                    if (str(gate.get("category")), str(gate.get("item"))) != m.track:
                        return False
        return True

    def due_override(self, template: Any) -> str | None:
        block = self.block_today()
        return f"today at {block.start}" if _is_slot(template) and block else None

    def slot_cache_fields(self, syllabus_key: str) -> dict[str, Any]:
        """Extra cache fields so a completed slot ritual credits minutes."""
        m, block = self.in_season().get(syllabus_key), self.block_today()
        return {"season_milestone": m.id, "block_minutes": block.minutes} if (m and block) else {}


def _is_slot(template: Any) -> bool:
    raw = getattr(template, "raw", None) or {}
    return raw.get("slot") == "deep_block"


# --- loading ----------------------------------------------------------------


def syllabus_facts(cfg: Any, syllabuses: dict[str, Any]) -> dict[str, SyllabusFacts]:
    out: dict[str, SyllabusFacts] = {}
    for key, entry in cfg.syllabuses.items():
        syl = syllabuses.get(key)
        out[key] = SyllabusFacts(
            enabled=bool(entry.enabled),
            tracks=frozenset((t.category, t.title) for t in (syl.tracks if syl else [])),
            module_count=len(syl.modules) if syl else 0,
        )
    return out


def load_season_context(
    seasons_path: Path,
    state_path: Path,
    today: date,
    facts: dict[str, SyllabusFacts],
) -> SeasonContext | None:
    """None when seasons.yaml is absent: the layer is opt-in."""
    if not seasons_path.exists():
        return None
    seasons = load_seasons(seasons_path)
    state = load_seasons_state(state_path)
    errors, warnings = validate(seasons, state, facts)
    for w in warnings:
        logger.warning("seasons: %s", w)
    if errors:
        raise SeasonsError(errors)
    return SeasonContext(seasons, state, forecast(seasons, state, today), today)


# --- pause reconciliation ---------------------------------------------------


def reconcile_pause(ctx: SeasonContext, key: str, state: SyllabusState) -> SyllabusState:
    """Off-season => open an indefinite pause; back in season => close it.

    Only pauses the seasons layer opened (tracked in state.last_run.paused)
    are ever lifted, so an owner's vacation pause is left alone.
    """
    paused_by: set[str] = set(ctx.state.last_run.get("paused") or [])
    desired = key in ctx.in_season()
    expired = state.paused and state.paused_until is not None and state.paused_until <= ctx.today
    if desired and state.paused and (key in paused_by or expired):
        state = unset_pause(state, todoist_task_id=SEASON_ACTOR, today=ctx.today).new_state  # type: ignore[assignment]
        paused_by.discard(key)
        logger.info("[%s] seasons: in season, unpaused", key)
    elif not desired and not state.paused:
        state = replace(state, paused=True, paused_since=ctx.today, paused_until=None)
        paused_by.add(key)
        logger.info("[%s] seasons: off-season, paused", key)
    elif not desired and expired:
        # Owner's dated pause ran out while off-season: close it, then take over.
        state = unset_pause(state, todoist_task_id=SEASON_ACTOR, today=ctx.today).new_state  # type: ignore[assignment]
        state = replace(state, paused=True, paused_since=ctx.today, paused_until=None)
        paused_by.add(key)
        logger.info("[%s] seasons: owner pause expired, now off-season", key)
    ctx.state.last_run["paused"] = sorted(paused_by)
    return state


# --- task emission ----------------------------------------------------------


@dataclass
class SeasonTask:
    external_id: str
    project_id: str
    namespace: str
    resolved: ResolvedTemplate
    cache_fields: dict[str, Any]


def season_tasks(ctx: SeasonContext, cfg: Any, slot_fired: set[str]) -> list[SeasonTask]:
    """Today's generic deep-block task (if no slot ritual covered it) + disciplines."""
    out: list[SeasonTask] = []
    today = ctx.today.isoformat()
    target, block = ctx.block_target(), ctx.block_today()
    if target is not None and block is not None and not (target.syllabus and target.syllabus in slot_fired):
        if target.syllabus:
            entry = cfg.syllabuses[target.syllabus]
            project, ns, skey = entry.todoist_project_id, target.syllabus, target.syllabus
        else:
            project, ns, skey = ctx.seasons.todoist_project_id, SEASONS_NS, ""
        out.append(
            SeasonTask(
                external_id=f"seasons:block:{target.id}:{today}",
                project_id=project,
                namespace=ns,
                resolved=ResolvedTemplate(
                    id="seasons:block",
                    title=f"Deep block · {target.name} ({block.minutes} min)",
                    description="",
                    due=f"today at {block.start}",
                    labels=["deep-block"],
                    cadence="daily",
                    skip_if=[],
                    syllabus_key=skey,
                ),
                cache_fields={"season_milestone": target.id, "block_minutes": block.minutes},
            )
        )
    weekday = WEEKDAYS[ctx.today.weekday()]
    for d in ctx.seasons.disciplines:
        if weekday not in d.days:
            continue
        out.append(
            SeasonTask(
                external_id=f"seasons:disc:{d.id}:{today}",
                project_id=ctx.seasons.todoist_project_id,
                namespace=SEASONS_NS,
                resolved=ResolvedTemplate(
                    id=f"seasons:disc:{d.id}",
                    title=d.name.replace("{milestone}", ctx.milestone_label()),
                    description="",
                    due=f"today at {d.start}",
                    labels=["discipline"],
                    cadence="daily",
                    skip_if=[],
                ),
                cache_fields={"discipline": d.id},
            )
        )
    return out


def emit_season_tasks(
    ctx: SeasonContext,
    cfg: Any,
    nc: Any,
    slot_fired: set[str],
    *,
    client_factory,
    clock,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Create today's season tasks. Returns (created, skipped, errors)."""
    created = skipped = errors = 0
    clients: dict[str, Any] = {}
    for task in season_tasks(ctx, cfg, slot_fired):
        cache = nc.data.setdefault(task.namespace, {})
        client = clients.get(task.project_id)
        if client is None:
            client = clients[task.project_id] = client_factory(
                token=cfg.todoist_token, project_id=task.project_id, clock=clock, dry_run=dry_run
            )
        try:
            result = client.create_task_idempotent(task.resolved, ctx.today, task.external_id, cache)
        except Exception as e:  # noqa: BLE001 — one bad task must not sink the run
            logger.error("seasons: create failed for %s: %s", task.external_id, e)
            errors += 1
            continue
        if result.skipped:
            skipped += 1
        else:
            created += 1
            cache[task.external_id] = {
                "todoist_task_id": result.todoist_task_id,
                "created_at": result.created_at,
                "template_id": task.resolved.id,
                "due_date": ctx.today.isoformat(),
            }
        cache[task.external_id].update(task.cache_fields)
    return created, skipped, errors


# --- minutes ----------------------------------------------------------------


def credit_completed_blocks(state: SeasonsState, caches: dict[str, dict[str, dict[str, Any]]]) -> int:
    """Completed block tasks -> logged minutes on their due date (once per day)."""
    credited = 0
    for cache in caches.values():
        for entry in cache.values():
            mid = entry.get("season_milestone")
            if not mid or entry.get("status") != "completed" or entry.get("season_logged"):
                continue
            try:
                due = date.fromisoformat(str(entry.get("due_date")))
            except ValueError:
                continue
            prog = state.milestones.setdefault(mid, MilestoneProgress())
            prog.logged[due] = max(prog.logged.get(due, 0), int(entry.get("block_minutes") or 0))
            entry["season_logged"] = True
            credited += 1
    return credited


def finish_run(ctx: SeasonContext, state_path: Path, nc: Any, *, dry_run: bool) -> int:
    """Credit minutes, stamp last_run, persist state. Returns credited count."""
    credited = credit_completed_blocks(ctx.state, nc.data)
    ctx.state.last_run.update({"main": ctx.fc.main, "side": ctx.fc.side, "resting": ctx.resting})
    if not dry_run:
        save_seasons_state(state_path, ctx.state)
    return credited


# --- streaks ----------------------------------------------------------------


def _in_rest(state: SeasonsState, d: date, today: date) -> bool:
    """Inside a recorded rest week, or inside the live one (rest_until)."""
    if state.rest_until is not None and today - timedelta(days=REST_DAYS) <= d <= state.rest_until:
        return True
    return any(a <= d <= b for a, b in state.rests)


def deep_work_streak(seasons: Seasons, state: SeasonsState, today: date, *, lookback: int = 400) -> int:
    """Consecutive block days with logged minutes, walking back from yesterday.

    Days without a block and rest-week days are skipped, not broken.
    """
    logged_days = {d for p in state.milestones.values() for d, m in p.logged.items() if m > 0}
    streak = 0
    d = today - timedelta(days=1)
    for _ in range(lookback):
        if WEEKDAYS[d.weekday()] in seasons.rhythm.deep_blocks and not _in_rest(state, d, today):
            if d not in logged_days:
                break
            streak += 1
        d -= timedelta(days=1)
    return streak


def discipline_streaks(seasons: Seasons, cache: dict[str, dict[str, Any]], today: date, *, lookback: int = 400) -> dict[str, int]:
    """Per-discipline streak over completed discipline tasks in the seasons cache."""
    done: dict[str, set[date]] = {}
    for entry in cache.values():
        did = entry.get("discipline")
        if did and entry.get("status") == "completed":
            try:
                done.setdefault(did, set()).add(date.fromisoformat(str(entry["due_date"])))
            except (KeyError, ValueError):
                continue
    out: dict[str, int] = {}
    for disc in seasons.disciplines:
        streak, d = 0, today - timedelta(days=1)
        for _ in range(lookback):
            if WEEKDAYS[d.weekday()] in disc.days:
                if d not in done.get(disc.id, set()):
                    break
                streak += 1
            d -= timedelta(days=1)
        out[disc.id] = streak
    return out
