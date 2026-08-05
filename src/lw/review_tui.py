"""lw review — deadline gate + per-curriculum questionnaire. Zero business
logic: everything decidable lives in review_logic.py. This module only wires
widgets to it."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label

from src.lw.gitops import commit_and_push
from src.lw.review_logic import (
    DeadlineGate,
    Question,
    apply_answers,
    apply_gate,
    build_deadline_gate,
    build_questions,
)
from src.lw.status_logic import EngineCtx, load_engine


class GateScreen(Screen):
    """Shipped / Extend(reason, days) / Failed for the picked rung's deadline."""

    def __init__(self, key: str, gate: DeadlineGate) -> None:
        super().__init__()
        self.key = key
        self.gate = gate

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label(
                f"{self.key}: rung {self.gate.meta['rung']} option {self.gate.meta['option']}"
                " is past its deadline"
            ),
            Horizontal(
                Button("Shipped", id="shipped", variant="success"),
                Button("Extend", id="extend"),
                Button("Failed", id="failed", variant="error"),
            ),
            Vertical(
                Input(placeholder="reason", id="reason"),
                Input(placeholder="extra days", id="extra_days"),
                Button("Submit extension", id="submit_extend"),
                id="extend_form",
            ),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#extend_form").display = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "extend":
            self.query_one("#extend_form").display = True
        elif event.button.id == "submit_extend":
            reason = self.query_one("#reason", Input).value.strip()
            days_str = self.query_one("#extra_days", Input).value.strip()
            if not reason or not days_str.isdigit() or int(days_str) <= 0:
                return
            self.app.resolve_gate(self.gate, "extend", reason=reason, extra_days=int(days_str))  # type: ignore[attr-defined]
        elif event.button.id in ("shipped", "failed"):
            self.app.resolve_gate(self.gate, event.button.id)  # type: ignore[attr-defined]


class QuestionScreen(Screen):
    """One state_review sub_task: Yes/No, or an int Input for wants_count."""

    def __init__(self, question: Question, default_yes: bool) -> None:
        super().__init__()
        self.question = question
        self.default_yes = default_yes

    def compose(self) -> ComposeResult:
        yield Header()
        if self.question.wants_count:
            yield Vertical(
                Label(self.question.sub.title),
                Input(placeholder="count", id="count"),
                Button("Submit", id="submit"),
            )
        else:
            title = self.question.sub.title
            if self.default_yes:
                title += "  [pre-checked: yes]"
            yield Vertical(
                Label(title),
                Horizontal(
                    Button("Yes", id="yes", variant="success"),
                    Button("No", id="no"),
                ),
            )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            count_str = self.query_one("#count", Input).value.strip()
            self.app.answer_question(self.question, int(count_str) if count_str.isdigit() else 0)  # type: ignore[attr-defined]
        elif event.button.id == "yes":
            self.app.answer_question(self.question, True)  # type: ignore[attr-defined]
        elif event.button.id == "no":
            self.app.answer_question(self.question, False)  # type: ignore[attr-defined]


class SummaryScreen(Screen):
    """Recap of this curriculum's checked answers; confirm to apply."""

    def __init__(self, key: str, answers: list[tuple[Question, "bool | int"]]) -> None:
        super().__init__()
        self.key = key
        self.answers = answers

    def compose(self) -> ComposeResult:
        yield Header()
        lines = [f"{q.sub.title}: {a}" for q, a in self.answers]
        yield Vertical(
            Label(f"{self.key} — summary"),
            Label("\n".join(lines) or "(nothing checked)"),
            Button("Confirm", id="confirm", variant="primary"),
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.app.confirm_summary()  # type: ignore[attr-defined]


@dataclass
class CurriculumResult:
    key: str
    answers: list[tuple[Question, "bool | int"]]
    gate_meta_path: Path | None


class ReviewApp(App):
    """One gate+questionnaire+summary flow per cli_review curriculum, in order.

    `results` accumulates a CurriculumResult per curriculum the user confirmed;
    quitting (ctrl+q) mid-flow drops whatever curriculum was in progress.
    """

    def __init__(self, ctx: EngineCtx, keys: list[str], today: date) -> None:
        super().__init__()
        self.ctx = ctx
        self.keys = keys
        self.today = today
        self.results: list[CurriculumResult] = []
        self._idx = 0
        self._key: str | None = None
        self._gate_meta_path: Path | None = None
        self._gate_advance = False
        self._questions: list[Question] = []
        self._q_idx = 0
        self._answers: list[tuple[Question, "bool | int"]] = []

    def on_mount(self) -> None:
        self._start_next()

    def _start_next(self) -> None:
        if self._idx >= len(self.keys):
            self.exit()
            return
        self._key = self.keys[self._idx]
        self._idx += 1
        self._gate_meta_path = None
        self._gate_advance = False
        cur = self.ctx.per_key[self._key]
        gate = build_deadline_gate(self.ctx.repo_root, cur, self.today)
        if gate is not None:
            self.push_screen(GateScreen(self._key, gate))
        else:
            self._start_questions()

    def resolve_gate(self, gate: DeadlineGate, choice: str, *, reason: str = "", extra_days: int = 0) -> None:
        outcome = apply_gate(gate, choice, reason=reason, extra_days=extra_days, today=self.today)
        self._gate_meta_path = gate.meta_path
        self._gate_advance = outcome.advance
        self.pop_screen()
        self._start_questions()

    def _start_questions(self) -> None:
        cur = self.ctx.per_key[self._key]
        self._questions = build_questions(cur, self.today)
        self._answers = []
        self._q_idx = 0
        self._next_question()

    def _next_question(self) -> None:
        if self._q_idx >= len(self._questions):
            self.push_screen(SummaryScreen(self._key, self._answers))
            return
        question = self._questions[self._q_idx]
        self._q_idx += 1
        default_yes = self._gate_advance and question.sub.action.get("type") == "advance_module"
        self.push_screen(QuestionScreen(question, default_yes))

    def answer_question(self, question: Question, value: "bool | int") -> None:
        self._answers.append((question, value))
        self.pop_screen()
        self._next_question()

    def confirm_summary(self) -> None:
        self.results.append(CurriculumResult(self._key, list(self._answers), self._gate_meta_path))
        self.pop_screen()
        self._start_next()


def run_review(repo_root: Path) -> int:
    ctx = load_engine(repo_root)
    today = date.today()
    keys = [key for key, cur in ctx.per_key.items() if cur.entry.cli_review]
    if not keys:
        print("No curriculum has cli_review enabled.")
        return 0

    app = ReviewApp(ctx, keys, today)
    app.run()
    if not app.results:
        return 1

    for result in app.results:
        cur = ctx.per_key[result.key]
        messages = apply_answers(ctx, result.key, result.answers, today)
        paths = [
            repo_root / cur.entry.state_file,
            repo_root / "state" / "shared.yaml",
            repo_root / "state" / f"{result.key}_state_log.yaml",
        ]
        if result.gate_meta_path is not None:
            paths.append(result.gate_meta_path)
        commit_and_push(repo_root, paths, f"review({result.key}): {today.isoformat()} state review via lw")
        for message in messages:
            print(message)
    return 0
