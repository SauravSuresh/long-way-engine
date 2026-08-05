"""lw rung start — pick a/b/c, confirm code path, scaffold. Zero business
logic: everything decidable lives in rung_logic.py. This module only wires
widgets to it."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Markdown

from src.lw.gitops import commit_and_push
from src.lw.rung_logic import RungOption, ScaffoldResult, rung_options, scaffold
from src.lw.status_logic import CurriculumCtx, _has_rungs, load_engine


class OptionItem(ListItem):
    def __init__(self, opt: RungOption) -> None:
        super().__init__(Label(f"{opt.option} — {opt.title}"))
        self.opt = opt


class PickScreen(Screen):
    """Screen 1: pick an option, brief preview on the right."""

    def __init__(self, opts: list[RungOption]) -> None:
        super().__init__()
        self.opts = opts

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            ListView(*(OptionItem(o) for o in self.opts), id="options"),
            Markdown(id="preview"),
        )
        yield Footer()

    def on_mount(self) -> None:
        if self.opts:
            self._preview(self.opts[0])

    def _preview(self, opt: RungOption) -> None:
        self.query_one("#preview", Markdown).update(opt.brief_path.read_text(encoding="utf-8"))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is not None:
            self._preview(event.item.opt)  # type: ignore[attr-defined]

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.app.pick_option(event.item.opt)  # type: ignore[attr-defined]


class ConfirmScreen(Screen):
    """Screen 2: editable code path, confirm to scaffold."""

    def __init__(self, opt: RungOption, default_code_path: str) -> None:
        super().__init__()
        self.opt = opt
        self.default_code_path = default_code_path

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label(f"Rung option {self.opt.option} — {self.opt.title}"),
            Label("Code path:"),
            Input(value=self.default_code_path, id="code_path"),
            Button("Confirm", id="confirm", variant="primary"),
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            code_path = self.query_one("#code_path", Input).value
            self.app.confirm_pick(self.opt, code_path)  # type: ignore[attr-defined]


class RungApp(App):
    """Screen 1 (pick option) -> screen 2 (confirm code path) -> exit.

    `result` is (opt, code_path) on completion, None if the user quit
    (ctrl+q) before confirming.
    """

    def __init__(self, opts: list[RungOption]) -> None:
        super().__init__()
        self.opts = opts
        self.result: tuple[RungOption, str] | None = None

    def on_mount(self) -> None:
        self.push_screen(PickScreen(self.opts))

    def pick_option(self, opt: RungOption) -> None:
        default_code_path = str(Path.home() / "workspace" / "personal" / "ladder" / opt.slug)
        self.push_screen(ConfirmScreen(opt, default_code_path))

    def confirm_pick(self, opt: RungOption, code_path: str) -> None:
        self.result = (opt, code_path)
        self.exit()


def run_rung_start(repo_root: Path) -> int:
    ctx = load_engine(repo_root)
    cur = _rung_curriculum(ctx.per_key)
    if cur is None:
        print("No curriculum with a ladder is configured.")
        return 1

    opts = rung_options(repo_root, cur)
    if not opts:
        print(f"No briefs found for rung {cur.state.current_module}.")
        return 1

    app = RungApp(opts)
    app.run()
    if app.result is None:
        return 1
    opt, code_path = app.result

    code_dir = Path(code_path).expanduser()
    result: ScaffoldResult = scaffold(repo_root, cur, opt, code_dir.parent, date.today())

    commit_and_push(
        repo_root, [result.paper_dir],
        f"ladder: pick rung {cur.state.current_module:02d} option {opt.option} — {opt.slug}",
    )
    print(f"paper dir: {result.paper_dir}")
    print(f"code dir: {result.code_dir}")
    print(f"ADR first: {result.paper_dir / 'adr.md'}")
    return 0


def _rung_curriculum(per_key: dict[str, CurriculumCtx]) -> CurriculumCtx | None:
    for cur in per_key.values():
        if _has_rungs(cur.templates):
            return cur
    return None
