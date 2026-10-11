"""Seasons forecast: who holds the deep blocks, from today to the horizon.

Canonical implementation (wayfinder #10). The planner's JS port must
produce identical output for every fixture in tests/golden/seasons/.
Pure: no IO, no clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from src.seasons import WEEKDAYS, Milestone, Seasons, SeasonsState

HORIZON_DAYS = 730
REST_DAYS = 7


@dataclass
class Segment:
    lane: str
    start: date
    end: date


@dataclass
class MilestoneForecast:
    start: date | None = None
    end: date | None = None  # None while live = runs past the horizon
    hours_reached: bool = False
    segments: list[Segment] = field(default_factory=list)


@dataclass
class Forecast:
    today: date
    main: str | None  # current main milestone id (the one holding / next to hold the blocks)
    side: str | None
    resting: bool
    milestones: dict[str, MilestoneForecast]
    rests: list[tuple[date, date]]
    overflow: bool


def forecast(seasons: Seasons, state: SeasonsState, today: date) -> Forecast:
    two = seasons.two_lanes
    live = [m for m in seasons.bucket if not (state.milestones.get(m.id) and state.milestones[m.id].done)]
    rem: dict[str, int] = {}
    info: dict[str, MilestoneForecast] = {}
    for m in live:
        logged = state.milestones[m.id].logged_minutes if m.id in state.milestones else 0
        rem[m.id] = max(0, int(round(m.hours * 60)) - logged)
        info[m.id] = MilestoneForecast()
    main_q = [m for m in live if m.lane != "side"] if two else list(live)
    side_q = [m for m in live if m.lane == "side"] if two else []
    side_minutes = sum(b.minutes for b in seasons.rhythm.deep_blocks.values() if b.lane == "side") if two else 0

    def day_of(n: int) -> date:
        return today + timedelta(days=n)

    def pick(q: list[Milestone], n: int) -> Milestone | None:
        for m in q:
            if rem[m.id] > 0 and (m.pin_start is None or m.pin_start <= day_of(n)):
                return m
        return None

    def remaining_elsewhere() -> bool:
        return any(rem[m.id] > 0 for m in live)

    def mark(m: Milestone, lane: str, n: int) -> None:
        f = info[m.id]
        d = day_of(n)
        if f.start is None:
            f.start = d
        if f.segments and f.segments[-1].lane == lane and f.segments[-1].end == d - timedelta(days=1):
            f.segments[-1].end = d
        else:
            f.segments.append(Segment(lane, d, d))

    rests: list[tuple[date, date]] = []
    rest_to = -1
    if state.rest_until is not None:
        r = (state.rest_until - today).days
        if r >= 0:
            rest_to = r
            rests.append((today, state.rest_until))
    resting_today = rest_to >= 0

    # Current = first not-done per lane regardless of hours (F4). Hours already
    # reached -> it ends today, followers forecast from tomorrow.
    cur_main = next((m for m in main_q if m.pin_start is None or m.pin_start <= today), None)
    cur_side = next((m for m in side_q if m.pin_start is None or m.pin_start <= today), None)
    current_main_id = cur_main.id if cur_main else None
    current_side_id = cur_side.id if cur_side else None

    def finish(m: Milestone, n: int, as_main: bool) -> None:
        nonlocal rest_to
        rem[m.id] = 0
        info[m.id].end = day_of(n)
        if seasons.rhythm.rest_week and as_main and remaining_elsewhere():
            rest_to = n + REST_DAYS
            rests.append((day_of(n + 1), day_of(n + REST_DAYS)))

    for m, as_main in ((cur_main, True), (cur_side, cur_main is None)):
        if m is not None and rem[m.id] <= 0 and not resting_today:
            info[m.id].hours_reached = True
            mark(m, "main" if as_main else "side", 0)
            finish(m, 0, as_main)
    if cur_main is not None and rem[cur_main.id] <= 0:
        cur_main = None
    if cur_side is not None and rem[cur_side.id] <= 0:
        cur_side = None

    n = 0
    while n < HORIZON_DAYS:
        if cur_main is None or rem[cur_main.id] <= 0:
            cur_main = pick(main_q, n)
        if cur_side is None or rem[cur_side.id] <= 0:
            cur_side = pick(side_q, n)
        if cur_main is None and cur_side is None and not any(rem[m.id] > 0 for m in live):
            break
        if n <= rest_to:
            n += 1
            continue
        if cur_main is not None:
            mark(cur_main, "main", n)
        if cur_side is not None:
            if cur_main is None:
                mark(cur_side, "main", n)
            elif side_minutes > 0:
                mark(cur_side, "side", n)
        block = seasons.rhythm.deep_blocks.get(WEEKDAYS[day_of(n).weekday()])
        if block is None:
            n += 1
            continue
        if two and block.lane == "side":
            target = cur_side or cur_main
        else:
            target = cur_main or cur_side
        if target is None:
            n += 1
            continue
        rem[target.id] -= block.minutes
        if rem[target.id] <= 0:
            finish(target, n, as_main=(target is cur_main) or cur_main is None)
        n += 1

    return Forecast(
        today=today,
        main=current_main_id,
        side=current_side_id,
        resting=resting_today,
        milestones=info,
        rests=rests,
        overflow=n >= HORIZON_DAYS,
    )
