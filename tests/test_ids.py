import re
from datetime import date

from src.ids import ID_LENGTH, external_id, module_external_id


def test_external_id_is_16_hex_chars():
    out = external_id("daily-anki", date(2026, 5, 4))
    assert re.fullmatch(r"[0-9a-f]{16}", out)
    assert len(out) == ID_LENGTH


def test_external_id_deterministic():
    a = external_id("daily-anki", date(2026, 5, 4))
    b = external_id("daily-anki", date(2026, 5, 4))
    assert a == b


def test_external_id_changes_with_template_id():
    a = external_id("daily-anki", date(2026, 5, 4))
    b = external_id("daily-morning-reading", date(2026, 5, 4))
    assert a != b


def test_external_id_changes_with_date():
    a = external_id("daily-anki", date(2026, 5, 4))
    b = external_id("daily-anki", date(2026, 5, 5))
    assert a != b


def test_module_external_id_deterministic_and_distinct_from_date_form():
    a = module_external_id("module-onboarding", 1)
    b = module_external_id("module-onboarding", 1)
    c = module_external_id("module-onboarding", 2)
    assert a == b
    assert a != c
    assert re.fullmatch(r"[0-9a-f]{16}", a)
