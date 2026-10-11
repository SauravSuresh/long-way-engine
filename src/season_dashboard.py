"""Seasons section of the dashboard, TRMNL tiles, and the planner catalog (wayfinder #12).

Pure renderers: (SeasonContext, seasons cache, today) -> HTML / dicts.
Reuses the TRMNL tile class names so the band's screenshot contract holds.
"""

from __future__ import annotations

import html as _html
from datetime import date, timedelta
from typing import Any

from src.forecast import HORIZON_DAYS
from src.season_run import SeasonContext, deep_work_streak, discipline_streaks
from src.seasons import WEEKDAYS, Milestone

PALETTE = ("#0F8B8D", "#E3A008", "#D64933", "#6C4AB6", "#4C956C", "#C2387F", "#2F6FDE", "#8A5A2B")


def _h(s: Any) -> str:
    return _html.escape(str(s), quote=True)


def _fmt_time(hhmm: str, plus: int = 0) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    total = (h * 60 + m + plus) % 1440
    h, m = divmod(total, 60)
    ap = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ap}" if m else f"{h12} {ap}"


def _long(d: date) -> str:
    return d.strftime("%-d %B %Y")


def _short(d: date) -> str:
    return d.strftime("%-d %b")


def _weeks(a: date, b: date) -> int:
    return max(1, round(((b - a).days + 1) / 7))


def _live(ctx: SeasonContext) -> list[Milestone]:
    return [m for m in ctx.seasons.bucket if not (ctx.state.milestones.get(m.id) and ctx.state.milestones[m.id].done)]


def _color(ctx: SeasonContext, m: Milestone) -> str:
    return PALETTE[[x.id for x in ctx.seasons.bucket].index(m.id) % len(PALETTE)]


def _logged(ctx: SeasonContext, m: Milestone) -> int:
    p = ctx.state.milestones.get(m.id)
    return p.logged_minutes if p else 0


def _side_days(ctx: SeasonContext) -> str:
    days = [d[:3].title() for d in WEEKDAYS if (b := ctx.seasons.rhythm.deep_blocks.get(d)) and b.lane == "side"]
    return ", ".join(days)


# --- pieces -----------------------------------------------------------------


def _hero(ctx: SeasonContext) -> str:
    fc, live = ctx.fc, _live(ctx)
    lead = ctx.main or ctx.side
    if not live:
        return "<h1>Put the first milestone in the bucket.</h1><p>Nothing in <code>seasons.yaml</code> is live.</p>"
    if not ctx.seasons.rhythm.deep_blocks:
        return "<h1>Your week has no deep blocks yet.</h1>"
    if lead is None:
        return "<h1>Every milestone waits on a pinned start date.</h1>"
    if ctx.resting:
        return (
            f"<h1>Week off until {_h(_long(ctx.state.rest_until))}.</h1>"
            f"<p>No deep blocks. Then <strong>{_h(lead.name)}</strong> gets your deep hours.</p>"
        )
    info = fc.milestones[lead.id]
    if info.hours_reached:
        h1 = f"{_h(lead.name)}: milestone hours reached."
        sub = ["Mark it done (<code>lw season done</code>) or raise the hours."]
    elif info.end is None:
        h1 = f"{_h(lead.name)} needs more than two years at this pace."
        sub = ["That is a dream, not a milestone. Cut it down to the next thing you could show someone."]
    else:
        h1 = f"{_h(lead.name)} has your deep hours until {_h(_long(info.end))}."
        sub = []
    if ctx.main and ctx.side and _side_days(ctx):
        sub.append(f"<strong>{_h(ctx.side.name)}</strong> rides along on {_h(_side_days(ctx))}.")
    if info.end is not None:
        nxt = min(
            (m for m in live if m is not lead and fc.milestones[m.id].start and fc.milestones[m.id].start > info.end),
            key=lambda m: fc.milestones[m.id].start,
            default=None,
        )
        if nxt:
            rest = "a week off, then " if ctx.seasons.rhythm.rest_week else ""
            sub.append(f"Then {rest}<strong>{_h(nxt.name)}</strong>.")
    wk = sum(b.minutes for b in ctx.seasons.rhythm.deep_blocks.values()) / 60
    tail = f"{wk:g} h of deep work a week."
    if fc.overflow:
        tail += " At this pace the bucket runs past two years. Shrink the milestones, not your sleep."
    sub.append(tail)
    return f"<h1>{h1}</h1><p>{' '.join(sub)}</p>"


def _today_line(ctx: SeasonContext) -> str:
    block, target = ctx.block_today(), ctx.block_target()
    if ctx.resting:
        line = "Week off. No deep block. Disciplines still count."
    elif block and target:
        line = (
            f"Deep block {_fmt_time(block.start)} to {_fmt_time(block.start, block.minutes)}, "
            f"{block.minutes} min, for <strong>{_h(target.name)}</strong>."
        )
    elif block:
        line = f"Deep block {_fmt_time(block.start)} to {_fmt_time(block.start, block.minutes)}. Nothing in the bucket to spend it on."
    else:
        line = f"No deep block on {WEEKDAYS[ctx.today.weekday()].title()}s. That is on purpose."
    due = [d for d in ctx.seasons.disciplines if WEEKDAYS[ctx.today.weekday()] in d.days]
    if due:
        line += " Disciplines: " + ", ".join(f"{_h(d.name.replace('{milestone}', ctx.milestone_label()))} at {_fmt_time(d.start)}" for d in due) + "."
    return f'<p class="sz-today">{line}</p>'


def _chart(ctx: SeasonContext) -> str:
    fc, live, today = ctx.fc, _live(ctx), ctx.today
    if not live or not ctx.seasons.rhythm.deep_blocks:
        return ""
    ends = [(f.end - today).days for f in fc.milestones.values() if f.end]
    total = min(HORIZON_DAYS, max(182, (max(ends) if ends else 0) + 21))

    def pct(days: int) -> str:
        return f"{days / total * 100:.3f}%"

    rests = "".join(
        f'<i class="rs" style="left:{pct((a - today).days)};width:{pct((b - a).days + 1)}" title="Week off"></i>'
        for a, b in fc.rests
        if (a - today).days < total
    )
    rows = []
    for m in sorted(live, key=lambda m: (fc.milestones[m.id].start or date.max)):
        f = fc.milestones[m.id]
        if f.hours_reached:
            when = "hours reached"
        elif f.start is None:
            when = "beyond two years at this pace"
        else:
            start_txt = "now" if f.start <= today else _short(f.start)
            when = f"{start_txt} to {_short(f.end)}, {_weeks(f.start, f.end)} weeks" if f.end else f"{start_txt}, runs past two years"
        segs = "".join(
            f'<i class="sg {s.lane}" style="left:{pct((s.start - today).days)};width:{pct((s.end - s.start).days + 1)}"></i>'
            for s in f.segments
            if (s.start - today).days < total
        )
        rows.append(
            f'<div class="sz-row" style="--c:{_color(ctx, m)}"><div class="sz-head"><span class="sz-name">'
            f'<span class="sz-dot"></span>{_h(m.name)}'
            + (f' <span class="sz-area">{_h(m.area)}</span>' if m.area else "")
            + f'</span><span class="sz-when">{_h(when)}</span></div>'
            f'<div class="sz-track">{rests}{segs}</div></div>'
        )
    return '<h3>The seasons ahead</h3><p class="sz-lede">Tall bars hold main blocks, short bars the side slot, hatched weeks are time off.</p>' + "".join(rows)


def _heatmap(ctx: SeasonContext) -> str:
    today = ctx.today
    monday = today - timedelta(days=today.weekday())
    start = monday - timedelta(days=21)
    per_day: dict[date, int] = {}
    for p in ctx.state.milestones.values():
        for d, mins in p.logged.items():
            per_day[d] = per_day.get(d, 0) + mins
    cells, week = [], 0
    for i in range(28):
        d = start + timedelta(days=i)
        mins = per_day.get(d, 0)
        if monday <= d <= today:
            week += mins
        cls = "future" if d > today else ("l3" if mins >= 90 else "l2" if mins >= 45 else "l1" if mins else "")
        if d == today:
            cls += " today"
        cells.append(f'<span class="{cls.strip()}" title="{_h(_short(d))}: {mins} min"></span>')
    planned = sum(b.minutes for b in ctx.seasons.rhythm.deep_blocks.values())
    return (
        '<h3>Last four weeks</h3><div class="sz-calhead">' + "".join(f"<span>{x}</span>" for x in "MTWTFSS") + "</div>"
        f'<div class="sz-cal">{"".join(cells)}</div>'
        f'<p class="sz-meta">This week: {week} min logged of {planned} planned. '
        f'Deep-work streak: <strong>{deep_work_streak(ctx.seasons, ctx.state, today)}</strong>.</p>'
    )


def _bucket(ctx: SeasonContext) -> str:
    fc, today = ctx.fc, ctx.today
    items = []
    for m in _live(ctx):
        f, logged = fc.milestones[m.id], _logged(ctx, m)
        pct = min(100, round(logged / (m.hours * 60) * 100))
        if f.hours_reached:
            txt = "Milestone hours reached. Mark it done, or raise the hours."
        elif f.start is None:
            txt = "Beyond two years at this pace."
        else:
            lead = "In progress" if f.start <= today else f"Starts {_short(f.start)}"
            txt = f"{lead}, about {_weeks(f.start, f.end)} weeks, ends {_short(f.end)}." if f.end else f"{lead}, runs past two years."
        binding = f" · {m.syllabus}" + (f" / {m.track[1]}" if m.track else f" / modules {m.modules[0]}–{m.modules[1]}" if m.modules else "") if m.syllabus else ""
        items.append(
            f'<li style="--c:{_color(ctx, m)}"><span class="sz-dot"></span><strong>{_h(m.name)}</strong> '
            f'<span class="sz-meta">{_h(m.area)} · {m.lane} · {m.hours:g} h{_h(binding)}</span>'
            f'<div class="sz-bar"><i style="width:{pct}%"></i></div>'
            f'<div class="sz-meta">{logged / 60:.1f} of {m.hours:g} h logged. {_h(txt)}</div></li>'
        )
    done = [m for m in ctx.seasons.bucket if m not in _live(ctx)]
    fold = ""
    if done:
        fold = "<details><summary>Finished (%d)</summary><ul>%s</ul></details>" % (
            len(done),
            "".join(f"<li>{_h(m.name)}, {_logged(ctx, m) / 60:.1f} h logged, done {ctx.state.milestones[m.id].done}</li>" for m in done),
        )
    return f'<h3>The bucket</h3><ol class="sz-bucket">{"".join(items)}</ol>{fold}'


# --- public -----------------------------------------------------------------


def render_seasons_section(ctx: SeasonContext, seasons_cache: dict[str, dict[str, Any]]) -> str:
    streaks = discipline_streaks(ctx.seasons, seasons_cache, ctx.today)
    disc = ""
    if ctx.seasons.disciplines:
        disc = '<h3>Disciplines</h3><p class="sz-meta">' + " · ".join(
            f"{_h(d.name.replace('{milestone}', ctx.milestone_label()))}: streak {streaks.get(d.id, 0)}" for d in ctx.seasons.disciplines
        ) + "</p>"
    return (
        '<section class="seasons" id="seasons"><div class="sz-hero">'
        f"{_hero(ctx)}</div>{_today_line(ctx)}{_chart(ctx)}"
        f'<div class="sz-cols"><div>{_heatmap(ctx)}{disc}</div><div>{_bucket(ctx)}</div></div></section>'
    )


def season_tiles(ctx: SeasonContext, seasons_cache: dict[str, dict[str, Any]]) -> str:
    """Three TRMNL tiles: main season, side season or disciplines, disciplines."""
    streak = deep_work_streak(ctx.seasons, ctx.state, ctx.today)
    block = ctx.block_today()

    def season_tile(m: Milestone | None, label: str) -> str:
        if m is None:
            name, day, rows = label, "nothing queued", ""
        else:
            f, logged = ctx.fc.milestones[m.id], _logged(ctx, m)
            pct = min(100, round(logged / (m.hours * 60) * 100))
            name = m.name
            day = f"{logged / 60:.0f} / {m.hours:g} h &middot; {pct}%"
            until = "hours reached" if f.hours_reached else (_short(f.end) if f.end else "past horizon")
            today_txt = (
                "REST" if ctx.resting
                else f"BLOCK {_fmt_time(block.start)} &middot; {block.minutes} min" if block and ctx.block_target() is m
                else "no block"
            )
            rows = (
                f'<div class="t-row"><span class="t-key">TODAY</span> <span class="t-strong">{today_txt}</span></div>'
                f'<div class="t-row"><span class="t-key">UNTIL</span> <span class="t-strong">{_h(until)}</span></div>'
            )
        return (
            f'<div class="trmnl-tile"><div class="t-name">{_h(name)}</div><div class="t-day">{day}</div>{rows}'
            f'<div class="t-row"><span class="t-key">STREAK</span> <span class="t-strong">{streak}</span></div></div>'
        )

    def disc_tile() -> str:
        streaks = discipline_streaks(ctx.seasons, seasons_cache, ctx.today)
        due = [d for d in ctx.seasons.disciplines if WEEKDAYS[ctx.today.weekday()] in d.days]
        rows = "".join(
            f'<div class="t-row"><span class="t-key">{_h(d.name.replace("{milestone}", "")[:10].strip().upper() or d.id.upper())}</span> '
            f'<span class="t-strong">{streaks.get(d.id, 0)}</span></div>'
            for d in ctx.seasons.disciplines
        )
        return (
            f'<div class="trmnl-tile"><div class="t-name">DISCIPLINES</div>'
            f'<div class="t-day">{len(due)} due today</div>{rows}</div>'
        )

    main_tile = season_tile(ctx.main, "REST" if ctx.resting else "BUCKET EMPTY")
    second = season_tile(ctx.side, "NO SIDE") if ctx.seasons.two_lanes else disc_tile()
    third = disc_tile() if ctx.seasons.two_lanes else ""
    return main_tile + second + third


def seasons_data(ctx: SeasonContext, seasons_cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    fc = ctx.fc
    return {
        "today": iso(ctx.today),
        "current": {"main": fc.main, "side": fc.side, "resting": fc.resting},
        "rest_until": iso(ctx.state.rest_until),
        "overflow": fc.overflow,
        "rests": [{"from": iso(a), "to": iso(b)} for a, b in fc.rests],
        "deep_work_streak": deep_work_streak(ctx.seasons, ctx.state, ctx.today),
        "discipline_streaks": discipline_streaks(ctx.seasons, seasons_cache, ctx.today),
        "milestones": {
            m.id: {
                "name": m.name,
                "area": m.area,
                "hours": m.hours,
                "lane": m.lane,
                "syllabus": m.syllabus,
                "track": list(m.track) if m.track else None,
                "modules": list(m.modules) if m.modules else None,
                "logged_minutes": _logged(ctx, m),
                "logged": {iso(d): v for d, v in sorted((ctx.state.milestones.get(m.id).logged if ctx.state.milestones.get(m.id) else {}).items())},
                "done": iso(ctx.state.milestones[m.id].done) if ctx.state.milestones.get(m.id) else None,
                "start": iso(fc.milestones[m.id].start) if m.id in fc.milestones else None,
                "end": iso(fc.milestones[m.id].end) if m.id in fc.milestones else None,
                "hours_reached": fc.milestones[m.id].hours_reached if m.id in fc.milestones else False,
                "segments": [{"lane": s.lane, "from": iso(s.start), "to": iso(s.end)} for s in (fc.milestones[m.id].segments if m.id in fc.milestones else [])],
            }
            for m in ctx.seasons.bucket
        },
    }


def catalog(cfg: Any, syllabuses: dict[str, Any]) -> dict[str, Any]:
    """Syllabus catalog for the planner's pickers."""
    out: dict[str, Any] = {}
    for key, entry in cfg.syllabuses.items():
        syl = syllabuses.get(key)
        out[key] = {
            "name": str(syl.meta.get("name", key)) if syl else key,
            "enabled": bool(entry.enabled),
            "tracks": [{"category": t.category, "item": t.title} for t in (syl.tracks if syl else [])],
            "modules": [{"number": m.number, "name": getattr(m, "name", "")} for m in (syl.modules if syl else [])],
        }
    return {"syllabuses": out}
