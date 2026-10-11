import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from src.season_dashboard import catalog, render_seasons_section, season_tiles, seasons_data
from src.season_run import load_season_context
from src.seasons import SyllabusFacts

OWNER = """
todoist_project_id: seasons-proj
rhythm:
  rest_week: true
  deep_blocks:
    monday: {start: "07:30", minutes: 90, lane: main}
    tuesday: {start: "07:30", minutes: 90, lane: side}
    saturday: {start: "07:30", minutes: 210, lane: main}
bucket:
  - {id: mb-rungs, name: Marketplace rungs, area: Work, hours: 20, syllabus: mb, modules: [1, 5]}
  - {id: aws, name: AWS SAA, area: Learning, hours: 10, lane: side}
  - {id: old, name: Old thing, area: Work, hours: 5}
disciplines:
  - {id: anki, name: "Anki · {milestone}", minutes: 20, start: "07:15"}
"""
STATE = """
milestones:
  mb-rungs: {logged: {2026-10-10: 210, 2026-10-05: 90}, done: null}
  old: {logged: {2026-09-01: 300}, done: 2026-09-02}
"""
FACTS = {"mb": SyllabusFacts(True, frozenset(), 16)}
MON = date(2026, 10, 12)


def _ctx(tmp_path: Path):
    (tmp_path / "seasons.yaml").write_text(OWNER)
    (tmp_path / "state.yaml").write_text(STATE)
    return load_season_context(tmp_path / "seasons.yaml", tmp_path / "state.yaml", MON, FACTS)


def test_section_renders_hero_today_chart_heatmap_bucket(tmp_path):
    ctx = _ctx(tmp_path)
    html = render_seasons_section(ctx, {})
    assert "Marketplace rungs has your deep hours until" in html
    assert "AWS SAA</strong> rides along on Tue" in html
    assert "Deep block 7:30 am to 9 am, 90 min, for <strong>Marketplace rungs</strong>" in html
    assert 'class="sz-track"' in html and 'class="sg main"' in html and 'class="sg side"' in html
    assert 'class="sz-cal"' in html and "5.0 of 20 h logged" in html
    assert "Finished (1)" in html and "Old thing" in html
    assert "Anki · Marketplace rungs: streak 0" in html


def test_tiles_keep_trmnl_classes(tmp_path):
    ctx = _ctx(tmp_path)
    tiles = season_tiles(ctx, {})
    assert tiles.count('class="trmnl-tile"') == 3  # main, side, disciplines
    assert '<div class="t-name">Marketplace rungs</div>' in tiles
    assert "BLOCK 7:30 am &middot; 90 min" in tiles
    assert '<div class="t-name">DISCIPLINES</div>' in tiles and "1 due today" in tiles


def test_data_is_json_serialisable_and_complete(tmp_path):
    ctx = _ctx(tmp_path)
    data = json.loads(json.dumps(seasons_data(ctx, {})))
    assert data["current"] == {"main": "mb-rungs", "side": "aws", "resting": False}
    assert data["milestones"]["mb-rungs"]["logged_minutes"] == 300
    assert data["milestones"]["old"]["done"] == "2026-09-02"
    assert data["milestones"]["aws"]["segments"][0]["lane"] == "side"


def test_catalog_lists_tracks_and_modules():
    cfg = SimpleNamespace(syllabuses={"mb": SimpleNamespace(enabled=True), "lw": SimpleNamespace(enabled=False)})
    syl = SimpleNamespace(
        meta={"name": "Marketplace"},
        tracks=[SimpleNamespace(category="Platform", title="Build")],
        modules=[SimpleNamespace(number=1, name="Rung 1")],
    )
    cat = catalog(cfg, {"mb": syl})
    assert cat["syllabuses"]["mb"] == {
        "name": "Marketplace", "enabled": True,
        "tracks": [{"category": "Platform", "item": "Build"}],
        "modules": [{"number": 1, "name": "Rung 1"}],
    }
    assert cat["syllabuses"]["lw"] == {"name": "lw", "enabled": False, "tracks": [], "modules": []}


def test_render_multi_syllabus_orders_sections_and_swaps_tiles(tmp_path):
    from zoneinfo import ZoneInfo

    from src.clock import FrozenClock
    from src.config import DashboardConfig, MultiSyllabusConfig, SyllabusEntry
    from src.dashboard import render_multi_syllabus
    from src.state import SharedState, SyllabusState
    from src.syllabus import load_syllabus

    ctx = _ctx(tmp_path)
    seasons = {"html": render_seasons_section(ctx, {}), "tiles": season_tiles(ctx, {}), "data": seasons_data(ctx, {})}
    lw_path = Path(__file__).resolve().parent.parent / "curricula" / "long-way"
    tz = ZoneInfo("Asia/Kolkata")
    state = SyllabusState(start_date=date(2026, 1, 1), phase=1, month=4, current_module=2, current_book="b")

    def cfg(sections):
        return MultiSyllabusConfig(
            default_ritual_times={"morning_reading": "06:00", "anki": "08:30"},
            priority_order=["long-way"],
            syllabuses={"long-way": SyllabusEntry(key="long-way", path=lw_path, todoist_project_id="p", state_file=tmp_path / "s.yaml", enabled=True, ritual_times={"morning_reading": "06:00", "anki": "08:30"})},
            sunday_off=True,
            pair_day=None,
            dashboard=DashboardConfig(github_username="u", repo_name="r", sections=sections),
            todoist_token="",
        )

    def render(sections, seasons_arg):
        return render_multi_syllabus(
            cfg=cfg(sections), shared=SharedState(timezone=tz), syllabus_states={"long-way": state},
            syllabuses={"long-way": load_syllabus(lw_path)}, completion_by_syllabus={"long-way": set()},
            cache_by_syllabus={"long-way": {}}, reflections_by_syllabus={"long-way": []},
            books_by_syllabus={"long-way": []}, today=MON, clock=FrozenClock(MON, tz),
            reflections_root=tmp_path / "r", seasons=seasons_arg,
        )

    def band(h):
        return h[h.index('<header class="trmnl-band">'):h.index("</header>")]

    html, data = render(None, seasons)
    assert html.index('<section class="seasons"') < html.index('<section class="syllabus-card"')  # default order
    assert '<div class="t-name">Marketplace rungs</div>' in band(html) and "t-pct-label" not in band(html)  # season tiles replaced adherence tiles
    assert data["seasons"]["current"]["main"] == "mb-rungs"

    html, _ = render(["syllabus_cards", "seasons"], seasons)
    assert html.index('<section class="syllabus-card"') < html.index('<section class="seasons"')
    html, _ = render(["syllabus_cards"], seasons)
    assert '<section class="seasons"' not in html

    html, data = render(None, None)  # layer off: unchanged behaviour
    assert "t-pct-label" in band(html) and "seasons" not in data and '<section class="seasons"' not in html
