"""Reflection stubs and metadata maintenance.

Phase C bridges Todoist tasks to version-controlled markdown reflections.

Public functions:
  - create_stub(...)     — write a stub file from cadence template if absent.
  - update_metadata(...) — walk the four cadence dirs, update frontmatter
                           word_count, edge-trigger status stub→filled.

Edge-triggered toggle: status flips stub→filled only when the previous
word_count was below `baseline + WORD_COUNT_THRESHOLD` and the new count
is at or above it. This makes manual `status: stub` reverts sticky:
setting status=stub on a high-word-count file leaves it stub until the
count drops and rises again across the threshold. Documented in
reflections/README.md.

Stub creation is decoupled from Todoist task creation — it runs whenever
the *template* would fire, regardless of whether the task was newly
created, marker-deduped, or cache-hit. Never overwrites existing files.
"""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from src.config import Config
from src.state import State
from src.templates import MissingVariable, Template, resolve_string

logger = logging.getLogger(__name__)

WORD_COUNT_THRESHOLD = 50  # baseline + this many words → flip stub to filled
CADENCE_DIRS = ("weekly", "monthly", "quarterly", "annual")


@dataclass
class StubResult:
    path: Path
    decision: str  # "created" | "exists" | "pending" | "would_create" | "would_skip_exists" | "would_skip_pending"


def create_stub(
    template: Template,
    state: State,
    config: Config,
    today: date,
    reflections_root: Path,
    reflection_templates_root: Path,
    pending_paths: set[Path],
    dry_run: bool = False,
) -> StubResult | None:
    """Create the cadence stub file if absent. Idempotent.

    Returns None if the template doesn't request a stub. Otherwise returns
    a StubResult naming the resolved path and what happened.

    `pending_paths` is mutated: any path this call would create is added
    to the set so a later call in the same run can detect collisions.
    """
    reflection = template.raw.get("reflection") or {}
    if not reflection.get("create_stub"):
        return None

    stub_path_template = reflection.get("stub_path")
    if not stub_path_template:
        logger.warning(
            "template %s has reflection.create_stub but no stub_path; skipping",
            template.id,
        )
        return None

    try:
        resolved = resolve_string(stub_path_template, state, config, today)
    except MissingVariable as e:
        logger.warning(
            "template %s stub_path references missing variable %s; skipping",
            template.id,
            e,
        )
        return None

    path = reflections_root / resolved.removeprefix("reflections/")

    if dry_run:
        # Dry-run uses an in-memory pending set to model "another template in
        # this run already decided to write this path" — disk isn't touched.
        if path in pending_paths:
            logger.info("stub already pending in this run: %s", path)
            return StubResult(path=path, decision="would_skip_pending")
        if path.exists():
            logger.info("stub already exists: %s", path)
            return StubResult(path=path, decision="would_skip_exists")
        pending_paths.add(path)
        return StubResult(path=path, decision="would_create")

    # Real run: disk is the source of truth. After a successful write the
    # file exists, so the next call in the same run sees it via path.exists().
    if path.exists():
        logger.info("stub already exists: %s", path)
        return StubResult(path=path, decision="exists")

    body = _render_template(
        reflection_templates_root, template.cadence, state, config, today, template.id
    )
    if body is None:
        return None  # render error already logged
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    logger.info("stub created: %s", path)
    return StubResult(path=path, decision="created")


def update_metadata(reflections_root: Path, reflection_templates_root: Path) -> int:
    """Walk the four cadence dirs, update word_count, edge-trigger status.

    Returns count of files updated (frontmatter rewritten). Files with
    malformed frontmatter log a warning and are skipped. Files outside
    the four cadence dirs (private/, debugging/, pairing/) are not
    touched.
    """
    touched = 0
    for cadence in CADENCE_DIRS:
        dir_path = reflections_root / cadence
        if not dir_path.exists():
            continue
        baseline = _baseline_word_count(reflection_templates_root, cadence)
        if baseline is None:
            continue
        threshold = baseline + WORD_COUNT_THRESHOLD
        for path in sorted(dir_path.glob("*.md")):
            if _update_one(path, threshold):
                touched += 1
    return touched


# --- internals -----------------------------------------------------------------


def _render_template(
    reflection_templates_root: Path,
    cadence: str,
    state: State,
    config: Config,
    today: date,
    template_id: str,
) -> str | None:
    template_path = reflection_templates_root / f"{cadence}.md"
    if not template_path.exists():
        logger.warning(
            "reflection template %s not found for cadence %s (template %s); skipping",
            template_path,
            cadence,
            template_id,
        )
        return None
    raw = template_path.read_text(encoding="utf-8")
    try:
        return resolve_string(raw, state, config, today)
    except MissingVariable as e:
        logger.warning(
            "reflection template %s references missing variable %s; skipping",
            template_path,
            e,
        )
        return None


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split `---`-delimited YAML frontmatter from the body.

    Returns ({}, original_text) when the frontmatter is missing or malformed.
    """
    if not text.startswith("---"):
        return {}, text
    # Find the end of the frontmatter block.
    rest = text[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    end_marker = rest.find("\n---")
    if end_marker == -1:
        return {}, text
    fm_text = rest[:end_marker]
    body_start = end_marker + len("\n---")
    body = rest[body_start:]
    if body.startswith("\n"):
        body = body[1:]
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return {}, text
    if not isinstance(fm, dict):
        return {}, text
    return fm, body


def render_frontmatter(fm: dict[str, Any], body: str) -> str:
    fm_yaml = yaml.safe_dump(fm, sort_keys=False).rstrip()
    return f"---\n{fm_yaml}\n---\n{body}"


def count_words_in_body(body: str) -> int:
    return len(body.split())


@functools.lru_cache(maxsize=8)
def _baseline_word_count(reflection_templates_root: Path, cadence: str) -> int | None:
    template_path = reflection_templates_root / f"{cadence}.md"
    if not template_path.exists():
        logger.warning("reflection template missing for cadence %s", cadence)
        return None
    text = template_path.read_text(encoding="utf-8")
    _, body = split_frontmatter(text)
    return count_words_in_body(body)


def _update_one(path: Path, threshold: int) -> bool:
    """Update one reflection file's frontmatter. Returns True if file was rewritten."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("could not read reflection %s: %s", path, e)
        return False

    fm, body = split_frontmatter(text)
    if not fm:
        logger.warning("reflection %s has malformed frontmatter; skipping", path)
        return False

    new_count = count_words_in_body(body)
    old_count = int(fm.get("word_count", 0) or 0)
    status = str(fm.get("status", "stub"))

    # Edge-triggered toggle: only flip on a fresh upward crossing.
    if status == "stub" and old_count < threshold <= new_count:
        fm["status"] = "filled"
        logger.info(
            "reflection %s: status stub -> filled (word_count %d -> %d, threshold %d)",
            path,
            old_count,
            new_count,
            threshold,
        )

    fm["word_count"] = new_count

    new_text = render_frontmatter(fm, body)
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True
