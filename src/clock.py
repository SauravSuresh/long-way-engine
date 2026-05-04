"""The single point where the system clock is read.

Every other module that needs to know "what time is it" takes a Clock.
The real clock reads the OS clock in the owner's timezone; FrozenClock
returns a fixed value, used by --today and by tests.

Pass instances through the call chain. No globals.
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

DEFAULT_TIME = time(5, 30)


class Clock:
    """Reads the OS clock in the given timezone."""

    def __init__(self, tz: ZoneInfo) -> None:
        self._tz = tz

    @property
    def tz(self) -> ZoneInfo:
        return self._tz

    def now(self) -> datetime:
        return datetime.now(tz=self._tz)

    def today(self) -> date:
        return self.now().astimezone(self._tz).date()


class FrozenClock(Clock):
    """Returns a fixed datetime.

    `when` may be a date (combined with DEFAULT_TIME = 05:30 in `tz`) or
    a datetime (made aware in `tz` if naive, otherwise used as-is).
    """

    def __init__(self, when: date | datetime, tz: ZoneInfo) -> None:
        super().__init__(tz)
        if isinstance(when, datetime):
            if when.tzinfo is None:
                self._frozen = when.replace(tzinfo=tz)
            else:
                self._frozen = when
        else:
            self._frozen = datetime.combine(when, DEFAULT_TIME, tzinfo=tz)

    def now(self) -> datetime:
        return self._frozen
