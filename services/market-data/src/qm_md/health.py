"""Provider health state machine. It emits an event only when the state changes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .contracts import health_payload
from .models import DataMode, ProviderState


class ProviderHealthTracker:
    def __init__(self, provider: str, data_mode: DataMode) -> None:
        self._provider = provider
        self._data_mode = data_mode
        self._state: ProviderState | None = None

    @property
    def state(self) -> ProviderState | None:
        return self._state

    def transition(
        self,
        state: ProviderState,
        reason_code: str | None,
        *,
        now: datetime,
        last_tick_provider_ts: datetime | None = None,
        seconds_since_last_tick: float | None = None,
        reconnect_attempt: int = 0,
    ) -> dict[str, Any] | None:
        """Return a provider.health payload if the state changed, otherwise None."""
        if state == self._state:
            return None
        previous = self._state
        self._state = state
        return health_payload(
            provider=self._provider,
            state=state,
            previous_state=previous,
            reason_code=reason_code,
            last_tick_provider_ts=last_tick_provider_ts,
            seconds_since_last_tick=seconds_since_last_tick,
            reconnect_attempt=reconnect_attempt,
            ingest_ts=now,
            data_mode=self._data_mode,
        )
