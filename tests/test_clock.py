from datetime import date, datetime

from zoneinfo import ZoneInfo

from src.clock import DEFAULT_TIME, Clock, FrozenClock

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")


def test_real_clock_returns_aware_datetime_in_tz():
    c = Clock(IST)
    n = c.now()
    assert n.tzinfo is not None
    assert n.utcoffset() == IST.utcoffset(n)
    assert c.today() == n.date()


def test_frozen_clock_from_date_uses_default_time():
    c = FrozenClock(date(2026, 5, 4), IST)
    assert c.today() == date(2026, 5, 4)
    n = c.now()
    assert n.time() == DEFAULT_TIME
    assert n.tzinfo is not None
    assert n.date() == date(2026, 5, 4)


def test_frozen_clock_now_is_stable():
    c = FrozenClock(date(2026, 5, 4), IST)
    assert c.now() == c.now()


def test_frozen_clock_from_naive_datetime_attaches_tz():
    naive = datetime(2026, 5, 4, 9, 0)
    c = FrozenClock(naive, IST)
    n = c.now()
    assert n.tzinfo is not None
    assert n.replace(tzinfo=None) == naive


def test_frozen_clock_from_aware_datetime_preserved():
    aware = datetime(2026, 5, 4, 9, 0, tzinfo=UTC)
    c = FrozenClock(aware, IST)
    assert c.now() == aware
    # today() respects the construction tz, not the datetime's tz.
    # In IST, 2026-05-04 09:00 UTC is 14:30 IST, still 2026-05-04.
    assert c.today() == date(2026, 5, 4)


def test_frozen_clock_today_reflects_owner_tz():
    # 2026-05-04 23:00 UTC is 2026-05-05 04:30 IST.
    aware = datetime(2026, 5, 4, 23, 0, tzinfo=UTC)
    c = FrozenClock(aware, IST)
    assert c.today() == date(2026, 5, 5)
