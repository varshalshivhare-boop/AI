"""Stale-data detection. Only meaningful during a regular session; the caller supplies that flag."""

from __future__ import annotations

from datetime import datetime, timedelta


class StaleMonitor:
    def __init__(self, threshold: timedelta) -> None:
        if threshold <= timedelta(0):
            raise ValueError("threshold must be positive")
        self._threshold = threshold

    def is_stale(
        self, *, now: datetime, reference_ts: datetime | None, in_regular_session: bool
    ) -> bool:
        """reference_ts is the last tick's ingest time, or the connection time if none arrived.

        Returns False outside the regular session. Stale means: no data for longer than the
        threshold while the market is open.
        """
        if not in_regular_session or reference_ts is None:
            return False
        return now - reference_ts > self._threshold
