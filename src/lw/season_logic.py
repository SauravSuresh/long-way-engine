"""`lw season` — status / done / log / rest-end over state/seasons.yaml.

Pure functions take (seasons, state, today) and return (new_state, lines);
`run_season` does the IO + commit. No Todoist, no network.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from src.forecast import REST_DAYS, forecast
from src.seasons import MilestoneProgress, Seasons, SeasonsState, load_seasons, load_seasons_state, save_seasons_state


def status_lines(seasons: Seasons, state: SeasonsState, today: date) -> list[str]:
    fc = forecast(seasons, state, today)
    out: list[str] = []
    if fc.resting:
        out.append(f"Week off until {state.rest_until}. Then: {fc.main or '—'}")
    else:
        out.append(f"Main: {fc.main or '—'}    Side: {fc.side or '—'}")
    out.append("")
    out.append(f"{'milestone':24} {'lane':5} {'logged':>8} {'hours':>6}  start -> end")
    for m in seasons.bucket:
        prog = state.milestones.get(m.id)
        if prog and prog.done:
            continue
        f = fc.milestones[m.id]
        logged = prog.logged_minutes / 60 if prog else 0
        when = "hours reached" if f.hours_reached else f"{f.start or '—'} -> {f.end or 'past horizon'}"
        out.append(f"{m.name[:24]:24} {m.lane:5} {logged:8.1f} {m.hours:6.0f}  {when}")
    if fc.rests:
        out.append("")
        out.append("rest weeks: " + ", ".join(f"{a}..{b}" for a, b in fc.rests))
    return out


def mark_done(seasons: Seasons, state: SeasonsState, today: date, milestone_id: str | None) -> tuple[SeasonsState, str]:
    fc = forecast(seasons, state, today)
    mid = milestone_id or fc.main
    if mid is None or mid not in {m.id for m in seasons.bucket}:
        raise SystemExit(f"no such milestone: {mid!r}")
    prog = state.milestones.setdefault(mid, MilestoneProgress())
    prog.done = today
    msg = f"{mid} done"
    others_live = any(m.id != mid and not (state.milestones.get(m.id) and state.milestones[m.id].done) for m in seasons.bucket)
    if mid == fc.main and seasons.rhythm.rest_week and others_live:
        state.rest_until = today + timedelta(days=REST_DAYS)
        msg += f"; rest week until {state.rest_until}"
    return state, msg


def log_minutes(seasons: Seasons, state: SeasonsState, today: date, minutes: int, on: date | None, milestone_id: str | None) -> tuple[SeasonsState, str]:
    mid = milestone_id or forecast(seasons, state, today).main
    if mid is None or mid not in {m.id for m in seasons.bucket}:
        raise SystemExit(f"no such milestone: {mid!r}")
    day = on or today
    state.milestones.setdefault(mid, MilestoneProgress()).logged[day] = max(0, int(minutes))
    return state, f"{mid}: {minutes} min on {day}"


def rest_end(state: SeasonsState) -> tuple[SeasonsState, str]:
    state.rest_until = None
    return state, "rest week ended"


def run_season(repo_root: Path, args, today: date | None = None) -> int:
    today = today or date.today()
    seasons_path, state_path = repo_root / "seasons.yaml", repo_root / "state" / "seasons.yaml"
    if not seasons_path.exists():
        print("no seasons.yaml — the seasons layer is off")
        return 1
    seasons, state = load_seasons(seasons_path), load_seasons_state(state_path)
    if args.season_cmd == "status":
        print("\n".join(status_lines(seasons, state, today)))
        return 0
    if args.season_cmd == "done":
        state, msg = mark_done(seasons, state, today, args.milestone)
    elif args.season_cmd == "log":
        state, msg = log_minutes(seasons, state, today, args.minutes, args.date, args.milestone)
    elif args.season_cmd == "rest-end":
        state, msg = rest_end(state)
    else:
        return 2
    save_seasons_state(state_path, state)
    print(msg)
    from src.lw.gitops import commit_and_push

    commit_and_push(repo_root, [state_path], f"chore(seasons): {msg}")
    return 0
