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
