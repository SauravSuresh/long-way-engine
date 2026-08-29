"""lw reflect — sectioned form TUI. Zero business logic: everything decidable
lives in reflect_logic.py. This module only wires widgets to it."""
from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, TextArea

from src.lw.gitops import commit_and_push
from src.lw.reflect_logic import (
    ReflectTarget,
    Section,
    assemble,
    initial_sections,
    raw_frontmatter_block,
    reflect_targets,
)
from src.lw.status_logic import EngineCtx, load_engine


class TargetItem(ListItem):
    def __init__(self, target: ReflectTarget) -> None:
        super().__init__(Label(f"{target.key} · {target.cadence} · {target.stub_path}"))
        self.target = target


class ListScreen(Screen):
    """Screen 1: pick a reflection target."""

    def __init__(self, targets: list[ReflectTarget]) -> None:
        super().__init__()
        self.targets = targets

    def compose(self) -> ComposeResult:
        yield Header()
        yield ListView(*(TargetItem(t) for t in self.targets))
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.app.start_form(event.item.target)  # type: ignore[attr-defined]


class FormScreen(Screen):
    """Screens 2..N: one TextArea per section, Next/Back cycles through them."""

    BINDINGS = [
        ("ctrl+n", "next", "Next"),
        ("ctrl+b", "back", "Back"),
    ]

    def __init__(self, sections: list[Section]) -> None:
        super().__init__()
        self.sections = sections
        self.index = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label(id="heading"),
            TextArea(id="editor"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load(0)

    def _save_current(self) -> None:
        self.sections[self.index].content = self.query_one("#editor", TextArea).text

    def _load(self, index: int) -> None:
        self.index = index
        section = self.sections[index]
        heading = section.heading or "(preamble)"
        self.query_one("#heading", Label).update(f"{heading}  [{index + 1}/{len(self.sections)}]")
        self.query_one("#editor", TextArea).text = section.content

    def action_next(self) -> None:
        self._save_current()
        if self.index + 1 < len(self.sections):
            self._load(self.index + 1)
        else:
            self.app.finish_form(self.sections)  # type: ignore[attr-defined]

    def action_back(self) -> None:
        self._save_current()
        if self.index > 0:
            self._load(self.index - 1)


class ReflectApp(App):
    """Screen 1 (pick target) -> screens 2..N (fill sections) -> exit.

    `result` is (target, sections) on completion, None if the user quit
    (ctrl+q) before finishing the form.
    """

    def __init__(self, ctx: EngineCtx, targets: list[ReflectTarget], today: date) -> None:
        super().__init__()
        self.ctx = ctx
        self.targets = targets
        self.today = today
        self.result: tuple[ReflectTarget, str, list[Section]] | None = None
        self._target: ReflectTarget | None = None
        self._fm: str = ""

    def on_mount(self) -> None:
        self.push_screen(ListScreen(self.targets))

    def start_form(self, target: ReflectTarget) -> None:
        self._target = target
        self._fm, sections = initial_sections(self.ctx, target, self.today)
        self.push_screen(FormScreen(sections))

    def finish_form(self, sections: list[Section]) -> None:
        self.result = (self._target, self._fm, sections)
        self.exit()


def run_reflect(repo_root: Path, only: list[ReflectTarget] | None = None) -> int:
    ctx = load_engine(repo_root)
    today = date.today()
    targets = only if only is not None else reflect_targets(ctx, today)
    if not targets:
        print("No reflection targets due today.")
        return 0

    app = ReflectApp(ctx, targets, today)
    app.run()
    if app.result is None:
        return 1
    target, rendered_fm, sections = app.result

    # Existing files keep their on-disk frontmatter verbatim; new files use
    # the template-rendered frontmatter the form was seeded from.
    if target.stub_path.exists():
        fm_block = raw_frontmatter_block(target.stub_path.read_text(encoding="utf-8"))
    else:
        fm_block = rendered_fm
    target.stub_path.parent.mkdir(parents=True, exist_ok=True)
    target.stub_path.write_text(assemble(fm_block, sections), encoding="utf-8")

    editor = os.environ.get("EDITOR") or "vi"
    subprocess.run([editor, str(target.stub_path)])

    commit_and_push(
        repo_root, [target.stub_path],
        f"reflect({target.key}): {target.cadence} {target.stub_path.stem}",
    )
    return 0
