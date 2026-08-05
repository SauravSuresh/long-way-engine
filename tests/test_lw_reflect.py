def test_split_sections_on_h2():
    from src.lw.reflect_logic import split_sections

    body = "# Title\nintro\n\n## One\na\nb\n\n## Two\nc\n"
    sections = split_sections(body)
    assert [s.heading for s in sections] == ["# Title", "## One", "## Two"]
    assert sections[1].content.strip() == "a\nb"


def test_assemble_roundtrips():
    from src.lw.reflect_logic import assemble, split_sections

    body = "# T\nx\n\n## A\n1\n\n## B\n2\n"
    assert assemble("", split_sections(body)).strip() == body.strip()


def test_reflect_targets_finds_weekly_stub_templates():
    from datetime import date
    from pathlib import Path

    from src.lw.reflect_logic import reflect_targets
    from src.lw.status_logic import load_engine

    ctx = load_engine(Path(__file__).resolve().parents[1])
    targets = reflect_targets(ctx, date(2026, 8, 7))  # a Friday
    keys = {(t.key, t.cadence) for t in targets}
    assert ("marketplace-builder", "weekly") in keys
    mb = next(t for t in targets if t.key == "marketplace-builder" and t.cadence == "weekly")
    assert "marketplace-builder/weekly" in str(mb.stub_path).replace("\\", "/")
    assert "marketplace-builder/marketplace-builder" not in str(mb.stub_path)


def test_initial_sections_blank_fallback_on_unresolvable_placeholder(tmp_path):
    """A reflection template referencing a placeholder resolve_string can't
    fill makes _render_template return None; initial_sections must still
    hand the form exactly one blank Section, not an empty list (which used
    to crash FormScreen.on_mount with an IndexError)."""
    from datetime import date

    from src.config import DashboardConfig, MultiSyllabusConfig, SyllabusEntry
    from src.lw.reflect_logic import ReflectTarget, Section, initial_sections
    from src.lw.status_logic import CurriculumCtx, EngineCtx
    from src.templates import Template

    tpl_dir = tmp_path / "reflection_templates"
    tpl_dir.mkdir()
    (tpl_dir / "weekly.md").write_text("# Week {bogus}\n", encoding="utf-8")

    entry = SyllabusEntry(
        key="k", path=tmp_path, todoist_project_id="1",
        state_file=tmp_path / "state.yaml", enabled=True, ritual_times={},
    )
    cfg = MultiSyllabusConfig(
        default_ritual_times={}, priority_order=["k"], syllabuses={"k": entry},
        sunday_off=True, pair_day=None,
        dashboard=DashboardConfig(github_username="u", repo_name="r"),
        todoist_token="t",
    )
    ctx = EngineCtx(
        cfg, shared=None,
        per_key={"k": CurriculumCtx(entry, state=None, syllabus=None, templates=[])},
        repo_root=tmp_path,
    )
    tpl = Template(id="k-weekly", title="t", description="d", due="today", labels=[], cadence="weekly")
    target = ReflectTarget(
        key="k", cadence="weekly", template=tpl,
        stub_path=tmp_path / "reflections" / "weekly" / "2026-W99.md",
    )

    fm, sections = initial_sections(ctx, target, date(2026, 8, 7))
    assert fm == ""
    assert sections == [Section("", "")]


def test_marketplace_builder_weekly_template_renders(tmp_path):
    """Regression: {week} in the weekly reflection template used to be an
    unknown placeholder (resolve_string only knows {iso_week}), so
    create_stub could never write this curriculum's weekly stub."""
    from datetime import date
    from pathlib import Path

    from src.lw.reflect_logic import _cfg_shim
    from src.lw.status_logic import load_engine
    from src.reflections import create_stub

    ctx = load_engine(Path(__file__).resolve().parents[1])
    cur = ctx.per_key["marketplace-builder"]
    tpl = next(
        t for t in cur.templates
        if t.cadence == "weekly" and (t.raw.get("reflection") or {}).get("create_stub")
    )
    tpl_root = cur.entry.path / "reflection_templates"

    result = create_stub(
        tpl, cur.state, _cfg_shim(ctx, "marketplace-builder"), date(2026, 8, 7),
        tmp_path, tpl_root, pending_paths=set(), dry_run=False,
    )

    assert result is not None
    assert result.decision == "created"
    assert "Weekly Reflection" in result.path.read_text(encoding="utf-8")
