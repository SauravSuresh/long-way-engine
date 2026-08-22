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
    forced_advance_answer,
    is_review_time,
    review_day,
    preview_gate_outcome,
)
from src.lw.status_logic import EngineCtx, load_engine


class GateScreen(Screen):
    """Shipped / Extend(reason, days) / Failed for the picked rung's deadline.
    Failed asks a follow-up: move on (advance, outcome=failed) or retry
    (failure logged, rung stays open with a new deadline)."""

    def __init__(self, key: str, gate: DeadlineGate) -> None:
        super().__init__()
        self.key = key
        self.gate = gate

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label(f"[b]{self.key}[/b]"),
            Label(
                f"Rung {self.gate.meta['rung']} option {self.gate.meta['option']}"
                " went past its deadline. What happened?"
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
            Vertical(
                Label("Failed — what now?"),
                Horizontal(
                    Button("Move on (advance)", id="failed_move_on", variant="error"),
                    Button("Retry — new deadline", id="failed_retry_reveal"),
                ),
                id="failed_form",
            ),
            Vertical(
                Input(placeholder="retry days", id="retry_days"),
                Button("Submit retry", id="submit_retry"),
                id="retry_form",
            ),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#extend_form").display = False
        self.query_one("#failed_form").display = False
        self.query_one("#retry_form").display = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "extend":
            self.query_one("#extend_form").display = True
            self.query_one("#failed_form").display = False
            self.query_one("#retry_form").display = False
        elif event.button.id == "submit_extend":
            reason = self.query_one("#reason", Input).value.strip()
            days_str = self.query_one("#extra_days", Input).value.strip()
            if not reason or not days_str.isdigit() or int(days_str) <= 0:
                return
            self.app.resolve_gate(self.gate, "extend", reason=reason, extra_days=int(days_str))  # type: ignore[attr-defined]
        elif event.button.id == "failed":
            self.query_one("#failed_form").display = True
            self.query_one("#extend_form").display = False
        elif event.button.id == "failed_move_on":
            self.app.resolve_gate(self.gate, "failed_move_on")  # type: ignore[attr-defined]
        elif event.button.id == "failed_retry_reveal":
            self.query_one("#retry_form").display = True
        elif event.button.id == "submit_retry":
            days_str = self.query_one("#retry_days", Input).value.strip()
            if not days_str.isdigit() or int(days_str) <= 0:
                return
            self.app.resolve_gate(self.gate, "failed_retry", extra_days=int(days_str))  # type: ignore[attr-defined]
        elif event.button.id == "shipped":
            self.app.resolve_gate(self.gate, "shipped")  # type: ignore[attr-defined]


class QuestionScreen(Screen):
    """One state_review sub_task: Yes/No, or an int Input for wants_count.

    Every screen leads with which curriculum is asking and how far along
    the questionnaire is, so back-to-back reviews can't blur together.

    `forced` means the deadline gate already decided this answer (fail-forward
    advance) — rendered as informational text with no Yes/No choice, per the
    spec's "failed (logged, advance anyway)"."""

    def __init__(
        self, question: Question, key: str, number: int, total: int, forced: bool = False
    ) -> None:
        super().__init__()
        self.question = question
        self.key = key
        self.number = number
        self.total = total
        self.forced = forced

    def compose(self) -> ComposeResult:
        yield Header()
        context = Label(f"[b]{self.key}[/b] — question {self.number} of {self.total}")
        if self.forced:
            yield Vertical(
                context,
                Label(self.question.sub.title),
                Label("(Already settled by the deadline gate — this rung advances.)"),
                Button("Got it, continue", id="continue", variant="primary"),
            )
        elif self.question.wants_count:
            yield Vertical(
                context,
                Label(self.question.sub.title),
                Input(placeholder="type a number, 0 for none — Enter to submit", id="count"),
                Button("Submit", id="submit"),
            )
        else:
            yield Vertical(
                context,
                Label(self.question.sub.title),
                Horizontal(
                    Button("Yes", id="yes", variant="success"),
                    Button("No", id="no"),
                ),
            )
        yield Footer()

    def _submit_count(self) -> None:
        count_str = self.query_one("#count", Input).value.strip()
        self.app.answer_question(self.question, int(count_str) if count_str.isdigit() else 0)  # type: ignore[attr-defined]

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit_count()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self.app.answer_question(self.question, True)  # type: ignore[attr-defined]
        elif event.button.id == "submit":
            self._submit_count()
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

    @staticmethod
    def _fmt(answer: "bool | int") -> str:
        if isinstance(answer, bool):
            return "✓ yes" if answer else "· no"
        return f"✓ {answer}" if answer > 0 else "· 0"

    def compose(self) -> ComposeResult:
        yield Header()
        lines = [f"{self._fmt(a)}  {q.sub.title}" for q, a in self.answers]
        acted_on = sum(1 for _, a in self.answers if (a if isinstance(a, bool) else a > 0))
        yield Vertical(
            Label(f"[b]{self.key}[/b] — here's what you said"),
            Label("\n".join(lines) or "(no questions this week)"),
            Label(
                f"{acted_on} answer(s) will change state; the rest change nothing."
                if acted_on
                else "Nothing to change — a quiet week is fine."
            ),
            Button("Looks right — save it", id="confirm", variant="primary"),
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
        # (gate, choice, reason, extra_days) once the user has picked one on
        # GateScreen — NOT persisted to meta.yaml until confirm_summary, so
        # quitting mid-curriculum leaves meta.yaml untouched.
        self._pending_gate: tuple[DeadlineGate, str, str, int] | None = None
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
        self._pending_gate = None
        self._gate_advance = False
        cur = self.ctx.per_key[self._key]
        gate = build_deadline_gate(self.ctx.repo_root, cur, self.today)
        if gate is not None:
            self.push_screen(GateScreen(self._key, gate))
        else:
            self._start_questions()

    def resolve_gate(self, gate: DeadlineGate, choice: str, *, reason: str = "", extra_days: int = 0) -> None:
        outcome = preview_gate_outcome(choice, reason=reason, extra_days=extra_days, today=self.today)
        self._pending_gate = (gate, choice, reason, extra_days)
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
        forced = forced_advance_answer(question, self._gate_advance)
        self.push_screen(
            QuestionScreen(
                question,
                key=self._key or "",
                number=self._q_idx,
                total=len(self._questions),
                forced=forced is not None,
            )
        )

    def answer_question(self, question: Question, value: "bool | int") -> None:
        self._answers.append((question, value))
        self.pop_screen()
        self._next_question()

    def confirm_summary(self) -> None:
        gate_meta_path = None
        if self._pending_gate is not None:
            gate, choice, reason, extra_days = self._pending_gate
            apply_gate(gate, choice, reason=reason, extra_days=extra_days, today=self.today)
            gate_meta_path = gate.meta_path
        self.results.append(CurriculumResult(self._key, list(self._answers), gate_meta_path))
        self._pending_gate = None
        self.pop_screen()
        self._start_next()


def run_review(repo_root: Path) -> int:
    ctx = load_engine(repo_root)
    today = date.today()
    enabled = [key for key, cur in ctx.per_key.items() if cur.entry.cli_review]
    if not enabled:
        print("No curriculum has cli_review enabled.")
        return 0

    keys = [key for key in enabled if is_review_time(ctx.per_key[key], today)]
    if not keys:
        for key in enabled:
            day = review_day(ctx.per_key[key]) or "any day"
            print(
                f"Not review time — {key} reviews on {day}"
                f" (today is {today.strftime('%A').lower()})."
            )
        return 1

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
        if messages:
            print(f"{result.key}:")
            for message in messages:
                print(f"  {message}")
        else:
            print(f"{result.key}: nothing changed this week — noted.")
    print("Review saved. Enjoy the rest of your Saturday.")
    return 0
