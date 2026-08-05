"""Pure logic for lw reflect: find targets, split/assemble template sections."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.config import Config, TodoistConfig
from src.reflections import _render_template, create_stub, split_frontmatter
from src.lw.status_logic import EngineCtx


@dataclass
class Section:
    heading: str
    content: str


@dataclass
class ReflectTarget:
    key: str
    cadence: str
    template: object
    stub_path: Path


def _cfg_shim(ctx: EngineCtx, key: str) -> Config:
    """Per-syllabus Config shim, mirroring src/main.py:806 exactly —
    resolve_string reads config.ritual_times, which only lives on
    SyllabusEntry / this shim, not on the top-level MultiSyllabusConfig."""
    entry = ctx.per_key[key].entry
    return Config(
        todoist=TodoistConfig(project_id=entry.todoist_project_id, labels={}),
        ritual_times=entry.ritual_times,
        sunday_off=ctx.cfg.sunday_off,
        pair_day=ctx.cfg.pair_day,
        dashboard=ctx.cfg.dashboard,
        todoist_token=ctx.cfg.todoist_token,
        curriculum_dir=entry.path,
    )


def reflect_targets(ctx: EngineCtx, today: date) -> list[ReflectTarget]:
    """Every reflection-stub template across enabled curricula, with the
    path this date's reflection files to. Existence is not filtered —
    editing an existing reflection is legitimate."""
    out: list[ReflectTarget] = []
    for key, cur in ctx.per_key.items():
        cfg_shim = _cfg_shim(ctx, key)
        root = ctx.repo_root / "reflections" / key
        tpl_root = cur.entry.path / "reflection_templates"
        for tpl in cur.templates:
            if not (tpl.raw.get("reflection") or {}).get("create_stub"):
                continue
            result = create_stub(
                tpl, cur.state, cfg_shim, today, root, tpl_root,
                pending_paths=set(), dry_run=True,
            )
            if result is None:
                continue
            out.append(ReflectTarget(key, tpl.cadence, tpl, result.path))
    return out


def split_sections(body: str) -> list[Section]:
    """Split markdown on top-level headings (# or ##). The preamble/title
    chunk is section 0. '---' separators stay inside their section."""
    sections: list[Section] = []
    heading: str | None = None
    buf: list[str] = []
    for line in body.splitlines():
        if line.startswith("# ") or line.startswith("## "):
            if heading is not None or buf:
                sections.append(Section(heading or "", "\n".join(buf).strip("\n")))
                buf = []
            heading = line
        else:
            buf.append(line)
    sections.append(Section(heading or "", "\n".join(buf).strip("\n")))
    return sections


def raw_frontmatter_block(text: str) -> str:
    """Verbatim '---\\n...\\n---' block from the start of `text`, or '' if
    frontmatter is missing/malformed. Mirrors split_frontmatter's own
    detection (index math included) so re-emitting this slice — instead of
    re-serializing the parsed dict — keeps update_metadata's YAML formatting
    untouched on rewrite."""
    fm, _ = split_frontmatter(text)
    if not fm:
        return ""
    prefix_len = 3  # leading '---'
    rest = text[3:]
    if rest.startswith("\n"):
        prefix_len += 1
        rest = rest[1:]
    end_marker = rest.find("\n---")
    return text[: prefix_len + end_marker + len("\n---")]


def initial_sections(ctx: EngineCtx, target: ReflectTarget, today: date) -> tuple[str, list[Section]]:
    """(raw_frontmatter_block, sections) to pre-fill the form with.

    If the stub file already exists on disk, sections come from ITS body —
    re-entering `lw reflect` edits the existing reflection, not the template.
    Otherwise sections come from the rendered cadence template."""
    if target.stub_path.exists():
        text = target.stub_path.read_text(encoding="utf-8")
        _, body = split_frontmatter(text)
        return raw_frontmatter_block(text), split_sections(body)
    cur = ctx.per_key[target.key]
    tpl_root = cur.entry.path / "reflection_templates"
    cfg_shim = _cfg_shim(ctx, target.key)
    # _render_template resolves the WHOLE raw template file (frontmatter
    # included), same shape as an on-disk stub's text — split it the same way.
    rendered = _render_template(tpl_root, target.cadence, cur.state, cfg_shim, today, target.template.id)
    if rendered is None:
        # _render_template already logged why (e.g. a template placeholder
        # resolve_string can't fill). Still give the user one blank section
        # to write into rather than a form with nothing in it.
        return "", [Section("", "")]
    _, body = split_frontmatter(rendered)
    return raw_frontmatter_block(rendered), split_sections(body)


def assemble(frontmatter: str, sections: list[Section]) -> str:
    parts: list[str] = []
    if frontmatter:
        parts.append(frontmatter.strip("\n"))
    for s in sections:
        chunk = (s.heading + "\n" if s.heading else "") + s.content
        parts.append(chunk.strip("\n"))
    return "\n\n".join(p for p in parts if p) + "\n"
