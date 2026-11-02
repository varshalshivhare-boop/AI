from datetime import UTC, datetime, timedelta

import pytest

from qm_md.health import ProviderHealthTracker
from qm_md.models import DataMode, ProviderState
from qm_md.stale import StaleMonitor

T0 = datetime(2026, 10, 19, 4, 0, tzinfo=UTC)


def test_stale_only_inside_regular_session_and_past_threshold() -> None:
    m = StaleMonitor(timedelta(seconds=15))
    assert m.is_stale(now=T0 + timedelta(seconds=16), reference_ts=T0, in_regular_session=True)
    assert not m.is_stale(now=T0 + timedelta(seconds=14), reference_ts=T0,
                          in_regular_session=True)
    assert not m.is_stale(now=T0 + timedelta(seconds=60), reference_ts=T0,
                          in_regular_session=False)


def test_no_reference_is_not_reported_as_stale() -> None:
    m = StaleMonitor(timedelta(seconds=15))
    assert not m.is_stale(now=T0, reference_ts=None, in_regular_session=True)


def test_threshold_must_be_positive() -> None:
    with pytest.raises(ValueError):
        StaleMonitor(timedelta(0))


def test_health_tracker_emits_only_on_change() -> None:
    h = ProviderHealthTracker("UPSTOX", DataMode.LIVE)
    first = h.transition(ProviderState.CONNECTED, None, now=T0)
    again = h.transition(ProviderState.CONNECTED, None, now=T0)
    degraded = h.transition(ProviderState.DEGRADED, "STALE_DATA", now=T0,
                            seconds_since_last_tick=17.3)
    assert first is not None and first["previous_state"] is None
    assert again is None
    assert degraded is not None
    assert degraded["previous_state"] == "CONNECTED"
    assert degraded["state"] == "DEGRADED"
    assert degraded["reason_code"] == "STALE_DATA"
    assert degraded["data_mode"] == "LIVE"
    assert h.state is ProviderState.DEGRADED
