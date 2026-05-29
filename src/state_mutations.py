"""Pure-function state mutations dispatched by the state-review phase.

Each handler takes the current State (and any action args), returns a
MutationResult bundling the new State, a log_entry suitable for
state_log.yaml, and a short user_message for the cron log. Handlers do
no IO and never observe a clock — the orchestrator passes `today` and
`todoist_task_id` so handlers stay deterministic.

The dispatch table at the bottom keys action `type` values to handlers.
The orchestrator routes by that table; any unknown type is rejected at
validator time (rule 13), so this dispatch is total at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Callable

from src.state import PauseInterval, SharedState, SyllabusState
from src.syllabus import Syllabus


@dataclass(frozen=True)
class MutationResult:
    new_state: SyllabusState | SharedState
    log_entry: dict[str, Any]
    user_message: str


def _entry(action: str, todoist_task_id: str, today: date, **extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "timestamp": today.isoformat(),
        "action": action,
        "todoist_task_id": todoist_task_id,
    }
    base.update(extra)
    return base


def advance_module(
    state: SyllabusState,
    syllabus: Syllabus,
    *,
    todoist_task_id: str,
    today: date,
) -> MutationResult:
    total = len(syllabus.modules)
    if state.current_module >= total:
        entry = _entry(
            "advance_module", todoist_task_id, today,
            noop=True, message=f"already on last module ({total})",
        )
        return MutationResult(state, entry, f"no-op: already on last module ({total})")
    prior = {
        "current_module": state.current_module,
        "completed_modules": list(state.completed_modules),
    }
    new_completed = list(state.completed_modules) + [state.current_module]
    new_state = replace(
        state,
        current_module=state.current_module + 1,
        completed_modules=new_completed,
    )
    entry = _entry(
        "advance_module", todoist_task_id, today,
        prior=prior,
        new={"current_module": new_state.current_module, "completed_modules": new_completed},
        message=f"advanced to module {new_state.current_module}",
    )
    return MutationResult(new_state, entry, entry["message"])


def mark_book_finished(
    state: SyllabusState,
    *,
    book: str,
    todoist_task_id: str,
    today: date,
) -> MutationResult:
    return _set_book_state(state, book, "done", todoist_task_id, today)


def mark_book_started(
    state: SyllabusState,
    *,
    book: str,
    todoist_task_id: str,
    today: date,
) -> MutationResult:
    return _set_book_state(state, book, "current", todoist_task_id, today)


def _set_book_state(
    state: SyllabusState,
    book: str,
    new_value: str,
    todoist_task_id: str,
    today: date,
) -> MutationResult:
    prior_value = state.books_state.get(book, "not_started")
    new_books = dict(state.books_state)
    new_books[book] = new_value
    new_state = replace(state, books_state=new_books)
    action = "mark_book_finished" if new_value == "done" else "mark_book_started"
    entry = _entry(
        action, todoist_task_id, today,
        book=book,
        prior={"books_state": {book: prior_value}},
        new={"books_state": {book: new_value}},
        message=f"{book!r}: {prior_value} -> {new_value}",
    )
    return MutationResult(new_state, entry, entry["message"])


def set_pause(
    state: SyllabusState,
    *,
    days: int,
    reason: str,
    todoist_task_id: str,
    today: date,
) -> MutationResult:
    until = today + timedelta(days=int(days))
    prior = {
        "paused": state.paused,
        "paused_since": state.paused_since,
        "paused_until": state.paused_until,
    }
    new_state = replace(state, paused=True, paused_since=today, paused_until=until)
    entry = _entry(
        "set_pause", todoist_task_id, today,
        days=int(days), reason=str(reason),
        prior=prior,
        new={"paused": True, "paused_since": today, "paused_until": until},
        message=f"paused for {days}d ({reason or 'no reason'}), until {until.isoformat()}",
    )
    return MutationResult(new_state, entry, entry["message"])


def unset_pause(
    state: SyllabusState,
    *,
    todoist_task_id: str,
    today: date,
) -> MutationResult:
    if not state.paused:
        entry = _entry(
            "unset_pause", todoist_task_id, today,
            noop=True, message="not currently paused",
        )
        return MutationResult(state, entry, "no-op: not currently paused")
    start = state.paused_since or today
    new_history = list(state.pause_history) + [PauseInterval(start=start, end=today, reason="")]
    prior = {
        "paused": state.paused,
        "paused_since": state.paused_since,
        "paused_until": state.paused_until,
        "pause_history": [
            {"start": iv.start, "end": iv.end, "reason": iv.reason}
            for iv in state.pause_history
        ],
    }
    new_state = replace(
        state,
        paused=False,
        paused_since=None,
        paused_until=None,
        pause_history=new_history,
    )
    entry = _entry(
        "unset_pause", todoist_task_id, today,
        prior=prior,
        new={
            "paused": False,
            "paused_since": None,
            "paused_until": None,
            "pause_history": [
                {"start": iv.start, "end": iv.end, "reason": iv.reason}
                for iv in new_history
            ],
        },
        message=f"resumed (paused {start.isoformat()}..{today.isoformat()})",
    )
    return MutationResult(new_state, entry, entry["message"])


def increment_counter(
    shared: SharedState,
    *,
    counter: str,
    delta: int,
    todoist_task_id: str,
    today: date,
) -> MutationResult:
    prior_value = int(shared.manual_counters.get(counter, 0) or 0)
    new_value = prior_value + int(delta)
    new_counters = dict(shared.manual_counters)
    new_counters[counter] = new_value
    new_shared = replace(shared, manual_counters=new_counters)
    entry = _entry(
        "increment_counter", todoist_task_id, today,
        counter=counter, delta=int(delta),
        prior={counter: prior_value},
        new={counter: new_value},
        message=f"{counter}: {prior_value} -> {new_value} (+{delta})",
    )
    return MutationResult(new_shared, entry, entry["message"])


def mark_track_started(
    state: SyllabusState,
    *,
    category: str,
    item: str,
    todoist_task_id: str,
    today: date,
) -> MutationResult:
    return _set_track_state(state, category, item, "current", todoist_task_id, today)


def mark_track_finished(
    state: SyllabusState,
    *,
    category: str,
    item: str,
    todoist_task_id: str,
    today: date,
) -> MutationResult:
    return _set_track_state(state, category, item, "done", todoist_task_id, today)


def _set_track_state(
    state: SyllabusState,
    category: str,
    item: str,
    new_value: str,
    todoist_task_id: str,
    today: date,
) -> MutationResult:
    cat_dict = state.learning_tracks.get(category, {})
    prior_value = cat_dict.get(item, "not_started")
    action = "mark_track_started" if new_value == "current" else "mark_track_finished"
    if prior_value == new_value:
        entry = _entry(
            action, todoist_task_id, today,
            category=category, item=item,
            noop=True, message=f"{category}/{item} already {new_value}",
        )
        return MutationResult(state, entry, entry["message"])
    new_tracks = {k: dict(v) for k, v in state.learning_tracks.items()}
    new_tracks.setdefault(category, {})[item] = new_value
    new_state = replace(state, learning_tracks=new_tracks)
    entry = _entry(
        action, todoist_task_id, today,
        category=category, item=item,
        prior={"learning_tracks": {category: {item: prior_value}}},
        new={"learning_tracks": {category: {item: new_value}}},
        message=f"{category}/{item}: {prior_value} -> {new_value}",
    )
    return MutationResult(new_state, entry, entry["message"])


def revert_last(
    state: SyllabusState,
    log_entries: list[dict[str, Any]],
    *,
    todoist_task_id: str,
    today: date,
) -> MutationResult:
    # Skip past prior reverts so we never re-revert a revert.
    target: dict[str, Any] | None = None
    for entry in reversed(log_entries):
        if entry.get("action") == "revert_last":
            continue
        if entry.get("noop"):
            continue
        target = entry
        break

    if target is None:
        entry = _entry(
            "revert_last", todoist_task_id, today,
            noop=True, message="nothing to revert",
        )
        return MutationResult(state, entry, "no-op: nothing to revert")

    if target.get("action") == "increment_counter":
        msg = "cannot revert: increment_counter targets are shared state, not per-syllabus"
        entry = _entry(
            "revert_last", todoist_task_id, today,
            noop=True,
            reverted_action="increment_counter",
            message=msg,
        )
        return MutationResult(state, entry, msg)

    prior = target.get("prior") or {}
    new_state = state
    if "current_module" in prior:
        new_state = replace(
            new_state,
            current_module=int(prior["current_module"]),
            completed_modules=list(prior.get("completed_modules", new_state.completed_modules)),
        )
    if "books_state" in prior:
        merged = dict(new_state.books_state)
        for k, v in prior["books_state"].items():
            merged[k] = v
        new_state = replace(new_state, books_state=merged)
    if "paused" in prior:
        new_state = replace(
            new_state,
            paused=bool(prior["paused"]),
            paused_since=prior.get("paused_since"),
            paused_until=prior.get("paused_until"),
        )
    if "pause_history" in prior:
        history = [
            PauseInterval(start=iv["start"], end=iv["end"], reason=iv.get("reason", ""))
            for iv in prior["pause_history"]
        ]
        new_state = replace(new_state, pause_history=history)
    if "learning_tracks" in prior:
        merged = {k: dict(v) for k, v in new_state.learning_tracks.items()}
        for cat, items in prior["learning_tracks"].items():
            merged.setdefault(cat, {})
            for item, val in items.items():
                merged[cat][item] = val
        new_state = replace(new_state, learning_tracks=merged)

    entry = _entry(
        "revert_last", todoist_task_id, today,
        reverted_entry_timestamp=target.get("timestamp"),
        reverted_action=target.get("action"),
        message=f"reverted: {target.get('message', target.get('action'))}",
    )
    return MutationResult(new_state, entry, entry["message"])


ACTION_HANDLERS: dict[str, Callable[..., MutationResult]] = {
    "advance_module": advance_module,
    "mark_book_finished": mark_book_finished,
    "mark_book_started": mark_book_started,
    "mark_track_started": mark_track_started,
    "mark_track_finished": mark_track_finished,
    "set_pause": set_pause,
    "unset_pause": unset_pause,
    "increment_counter": increment_counter,
    "revert_last": revert_last,
}
