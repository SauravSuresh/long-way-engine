from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_rung_options_finds_three_briefs_for_rung_1():
    from src.lw.rung_logic import rung_options
    from src.lw.status_logic import load_engine

    ctx = load_engine(REPO)
    opts = rung_options(REPO, ctx.per_key["marketplace-builder"])
    assert len(opts) == 3
    assert {o.option for o in opts} == {"a", "b", "c"}
    assert all(o.brief_path.exists() for o in opts)


def test_scaffold_writes_meta_and_adr(tmp_path):
    import yaml

    from src.lw.rung_logic import rung_options, scaffold
    from src.lw.status_logic import load_engine

    ctx = load_engine(REPO)
    cur = ctx.per_key["marketplace-builder"]
    opt = rung_options(REPO, cur)[0]
    fake_repo = tmp_path / "engine"
    fake_repo.mkdir()
    result = scaffold(fake_repo, cur, opt, tmp_path / "code", date(2026, 8, 5))
    meta = yaml.safe_load((result.paper_dir / "meta.yaml").read_text())
    assert meta["rung"] == cur.state.current_module
    assert meta["option"] == opt.option
    assert meta["deadline"] == "2026-08-19"  # picked_at + deadline_days(14)
    assert meta["outcome"] is None
    adr = (result.paper_dir / "adr.md").read_text()
    assert "Context" in adr and "Decision" in adr
    assert result.code_dir.is_dir()


def test_scaffold_honors_overridden_code_dir_exactly(tmp_path):
    """A user-edited code path (e.g. not ending in opt.slug) must land
    exactly where typed, not have its leaf silently replaced by opt.slug."""
    from src.lw.rung_logic import rung_options, scaffold
    from src.lw.status_logic import load_engine

    ctx = load_engine(REPO)
    cur = ctx.per_key["marketplace-builder"]
    opt = rung_options(REPO, cur)[0]
    fake_repo = tmp_path / "engine"
    fake_repo.mkdir()
    custom_dir = tmp_path / "somewhere" / "custom-name"
    result = scaffold(
        fake_repo, cur, opt, tmp_path / "code", date(2026, 8, 5),
        code_dir=custom_dir,
    )
    assert result.code_dir == custom_dir
    assert custom_dir.is_dir()
    assert not (tmp_path / "code" / opt.slug).exists()
