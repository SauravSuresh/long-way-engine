from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.season_run import (
    SEASONS_NS,
    SeasonsError,
    credit_completed_blocks,
    emit_season_tasks,
    load_season_context,
    reconcile_pause,
    season_tasks,
)
from src.seasons import SyllabusFacts
from src.state import SyllabusState

OWNER = """
todoist_project_id: seasons-proj
rhythm:
  rest_week: true
  deep_blocks:
    monday: {start: "07:30", minutes: 90, lane: main}
    tuesday: {start: "07:30", minutes: 90, lane: side}
bucket:
  - {id: mb-rungs, name: Marketplace rungs, area: Work, hours: 100, syllabus: mb, modules: [1, 5]}
  - {id: aws, name: AWS SAA, area: Learning, hours: 40, lane: side, syllabus: devops,
     track: {category: Certifications, item: AWS SAA}}
  - {id: previz, name: Previz, area: Work, hours: 50}
disciplines:
  - {id: anki, name: "Anki - {milestone}", minutes: 20, start: "07:15"}
  - {id: gym, name: Gym, minutes: 60, start: "18:45", days: [tuesday]}
"""

FACTS = {
    "mb": SyllabusFacts(True, frozenset(), 16),
    "devops": SyllabusFacts(True, frozenset({("Certifications", "AWS SAA"), ("Courses", "bootdev")}), 13),
    "lw": SyllabusFacts(True, frozenset(), 23),
}
CFG = SimpleNamespace(
    todoist_token="t",
    syllabuses={
        "mb": SimpleNamespace(key="mb", enabled=True, todoist_project_id="mb-proj"),
        "devops": SimpleNamespace(key="devops", enabled=True, todoist_project_id="devops-proj"),
        "lw": SimpleNamespace(key="lw", enabled=True, todoist_project_id="lw-proj"),
    },
)
MON, TUE = date(2026, 10, 12), date(2026, 10, 13)


def _ctx(tmp_path: Path, today: date, owner: str = OWNER, state_text: str | None = None):
    (tmp_path / "seasons.yaml").write_text(owner)
    sp = tmp_path / "state" / "seasons.yaml"
    if state_text is not None:
        sp.parent.mkdir(exist_ok=True)
        sp.write_text(state_text)
    return load_season_context(tmp_path / "seasons.yaml", sp, today, FACTS)


def _tpl(**raw):
    return SimpleNamespace(id=raw.get("id", "t"), raw=raw, gated_by=raw.get("gated_by", []))


def _state(paused=False, since=None):
    return SyllabusState(start_date=date(2026, 8, 1), phase=1, month=1, current_module=1, current_book="b", paused=paused, paused_since=since)


class FakeClient:
    made: list[tuple[str, str, str]] = []

    def __init__(self, *, token, project_id, clock=None, dry_run=False):
        self.project_id = project_id

    def create_task_idempotent(self, template, due_date, external_id, cache, *, parent_id=None):
        from src.todoist import CreateResult

        if external_id in cache:
            return CreateResult(external_id, cache[external_id]["todoist_task_id"], template.id, due_date, "", True)
        FakeClient.made.append((self.project_id, external_id, template.title))
        return CreateResult(external_id, f"T-{len(FakeClient.made)}", template.id, due_date, "now", False)


def test_absent_file_means_layer_off(tmp_path):
    assert load_season_context(tmp_path / "nope.yaml", tmp_path / "s.yaml", MON, FACTS) is None


def test_invalid_owner_file_raises(tmp_path):
    with pytest.raises(SeasonsError):
        _ctx(tmp_path, MON, OWNER.replace("syllabus: mb", "syllabus: ghost"))


def test_in_season_and_block_target(tmp_path):
    ctx = _ctx(tmp_path, MON)
    assert ctx.in_season() == {"mb": ctx.main, "devops": ctx.side}
    assert ctx.block_target().id == "mb-rungs"  # Monday is a main day
    assert _ctx(tmp_path, TUE).block_target().id == "aws"  # Tuesday is a side day
    assert _ctx(tmp_path, date(2026, 10, 14)).block_target() is None  # no block Wednesday


def test_ritual_gating(tmp_path):
    ctx = _ctx(tmp_path, MON)
    assert ctx.ritual_allowed("mb", _tpl())
    assert not ctx.ritual_allowed("lw", _tpl())  # off-season syllabus
    aws_gate = [{"type": "track", "category": "Certifications", "item": "AWS SAA"}]
    bootdev_gate = [{"type": "track", "category": "Courses", "item": "bootdev"}]
    assert ctx.ritual_allowed("devops", _tpl(gated_by=aws_gate))
    assert not ctx.ritual_allowed("devops", _tpl(gated_by=bootdev_gate))  # other track, same syllabus
    assert ctx.ritual_allowed("devops", _tpl())  # ungated rituals fire in season
    # slot rituals fire only when today's block serves that milestone
    assert ctx.ritual_allowed("mb", _tpl(slot="deep_block"))
    assert not ctx.ritual_allowed("devops", _tpl(slot="deep_block"))
    assert ctx.due_override(_tpl(slot="deep_block")) == "today at 07:30"
    assert ctx.due_override(_tpl()) is None
    assert ctx.slot_cache_fields("mb") == {"season_milestone": "mb-rungs", "block_minutes": 90}


def test_rest_week_gates_everything(tmp_path):
    ctx = _ctx(tmp_path, MON, state_text="rest_until: 2026-10-15\n")
    assert ctx.resting and ctx.in_season() == {} and ctx.block_target() is None
    assert ctx.milestone_label() == "Rest"


def test_reconcile_pause_opens_and_closes_only_its_own(tmp_path):
    ctx = _ctx(tmp_path, MON)
    lw = reconcile_pause(ctx, "lw", _state())
    assert lw.paused and lw.paused_since == MON and lw.paused_until is None
    assert ctx.state.last_run["paused"] == ["lw"]
    # owner's own pause on an in-season syllabus is respected
    mb = reconcile_pause(ctx, "mb", _state(paused=True, since=date(2026, 10, 1)))
    assert mb.paused
    # a seasons-opened pause is lifted when the syllabus comes back in season
    ctx.state.last_run["paused"] = ["mb"]
    mb = reconcile_pause(ctx, "mb", _state(paused=True, since=date(2026, 10, 1)))
    assert not mb.paused and mb.pause_history[-1].start == date(2026, 10, 1) and mb.pause_history[-1].end == MON
    assert ctx.state.last_run["paused"] == []


def test_season_tasks_shapes(tmp_path):
    ctx = _ctx(tmp_path, MON)
    tasks = season_tasks(ctx, CFG, slot_fired=set())
    ids = [t.external_id for t in tasks]
    assert ids == ["seasons:block:mb-rungs:2026-10-12", "seasons:disc:anki:2026-10-12"]  # gym is Tuesday-only
    block, anki = tasks
    assert (block.project_id, block.namespace, block.resolved.due) == ("mb-proj", "mb", "today at 07:30")
    assert block.resolved.title == "Deep block · Marketplace rungs (90 min)"
    assert block.cache_fields == {"season_milestone": "mb-rungs", "block_minutes": 90}
    assert anki.resolved.title == "Anki - Marketplace rungs" and anki.project_id == "seasons-proj"
    # a slot ritual already covered the block -> no generic task
    assert [t.external_id for t in season_tasks(ctx, CFG, slot_fired={"mb"})] == ["seasons:disc:anki:2026-10-12"]


def test_bare_milestone_goes_to_seasons_project(tmp_path):
    state = "milestones:\n  mb-rungs: {done: 2026-10-01}\n  aws: {done: 2026-10-01}\n"
    ctx = _ctx(tmp_path, MON, state_text=state)
    block = season_tasks(ctx, CFG, set())[0]
    assert (block.project_id, block.namespace) == ("seasons-proj", SEASONS_NS)
    assert block.resolved.syllabus_key == ""


def test_emit_is_idempotent_and_credits_minutes(tmp_path):
    FakeClient.made.clear()
    ctx = _ctx(tmp_path, MON)
    nc = SimpleNamespace(data={})
    assert emit_season_tasks(ctx, CFG, nc, set(), client_factory=FakeClient, clock=None, dry_run=False) == (2, 0, 0)
    assert emit_season_tasks(ctx, CFG, nc, set(), client_factory=FakeClient, clock=None, dry_run=False) == (0, 2, 0)
    entry = nc.data["mb"]["seasons:block:mb-rungs:2026-10-12"]
    assert entry["season_milestone"] == "mb-rungs" and entry["due_date"] == "2026-10-12"
    # sweep marks it completed the next morning -> credited once, on the due date
    entry["status"] = "completed"
    assert credit_completed_blocks(ctx.state, nc.data) == 1
    assert ctx.state.milestones["mb-rungs"].logged == {MON: 90}
    assert credit_completed_blocks(ctx.state, nc.data) == 0
