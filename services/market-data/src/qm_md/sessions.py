"""NSE cash-equity session calendar.

Regular session: 09:15 to 15:30 IST, close exclusive. Weekends and dates listed in the
holiday file are closed. Pre-open is not part of the regular session and never produces candles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .errors import ConfigurationError

IST = ZoneInfo("Asia/Kolkata")
REGULAR_OPEN = time(9, 15)
REGULAR_CLOSE = time(15, 30)


@dataclass(frozen=True, slots=True)
class Session:
    session_date: date
    open_utc: datetime
    close_utc: datetime


class SessionCalendar:
    def __init__(self, *, calendar_version: str, holidays: frozenset[date], status: str) -> None:
        self.calendar_version = calendar_version
        self.holidays = holidays
        self.status = status

    @classmethod
    def from_yaml(cls, path: Path, *, allow_test: bool = False) -> SessionCalendar:
        """Load a holiday file.

        Refuses placeholder files (status != POPULATED). Refuses TEST calendars unless
        allow_test is set, so a test file cannot reach production by accident.
        """
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigurationError(f"cannot read calendar {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigurationError(f"calendar {path} must be a mapping")

        status = str(raw.get("status", ""))
        version = str(raw.get("calendar_version", ""))
        if status != "POPULATED":
            raise ConfigurationError(
                f"calendar {path} has status {status!r}. Populate it from the NSE holiday "
                "circular before running sessions."
            )
        if version.upper().startswith("TEST") and not allow_test:
            raise ConfigurationError(
                f"calendar {path} is a TEST calendar. Pass allow_test explicitly to use it."
            )

        dates: list[date] = []
        for item in raw.get("holidays") or []:
            value = item.get("date") if isinstance(item, dict) else None
            if not isinstance(value, date) or isinstance(value, datetime):
                raise ConfigurationError(
                    f"calendar {path}: holiday entry has no valid date: {item}"
                )
            dates.append(value)
        if len(set(dates)) != len(dates):
            raise ConfigurationError(f"calendar {path}: duplicate holiday dates")

        return cls(calendar_version=version, holidays=frozenset(dates), status=status)

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5 and day not in self.holidays

    def session_for_date(self, day: date) -> Session:
        open_utc = datetime.combine(day, REGULAR_OPEN, tzinfo=IST).astimezone(UTC)
        close_utc = datetime.combine(day, REGULAR_CLOSE, tzinfo=IST).astimezone(UTC)
        return Session(session_date=day, open_utc=open_utc, close_utc=close_utc)

    def session_for(self, ts: datetime) -> Session | None:
        """Return the regular session containing ts, or None if the market is closed then."""
        if ts.tzinfo is None:
            raise ValueError("session_for requires a timezone-aware timestamp")
        local_day = ts.astimezone(IST).date()
        if not self.is_trading_day(local_day):
            return None
        session = self.session_for_date(local_day)
        if session.open_utc <= ts < session.close_utc:
            return session
        return None
