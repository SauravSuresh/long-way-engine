"""Deterministic external IDs for Todoist task idempotency.

Same template + same due date -> same id, so a second run on the same day
will not create duplicate tasks.
"""

from __future__ import annotations

import hashlib
from datetime import date

ID_LENGTH = 16


def external_id(template_id: str, due_date: date) -> str:
    """Return a 16-char hex id for (template_id, due_date)."""
    payload = f"{template_id}|{due_date.isoformat()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:ID_LENGTH]


def module_external_id(template_id: str, module_number: int) -> str:
    """Phase D: id for once-per-module tasks. Stubbed here for shape."""
    payload = f"{template_id}|module:{module_number}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:ID_LENGTH]
