"""Milestone 2.4: stale-data detection and recovery, driven by a fake clock."""

from datetime import timedelta

from phase2_support import FakeClock, RecordingPublisher, ScriptedLiveProvider, utc_ist
from support import calendar

from qm_md.candles import CandleBuilder
from qm_md.dedupe import LruDeduper
from qm_md.metrics import MarketDataMetrics
from qm_md.models import Timeframe
from qm_md.normalize import TickNormalizer
from qm_md.pipeline import LivenessConfig, MarketDataPipeline
from qm_md.store import InMemoryCandleStore

CAL = calendar()


def build(provider, clock, publisher):  # type: ignore[no-untyped-def]
    return MarketDataPipeline(
        provider=provider,
        normalizer=TickNormalizer(["RELIANCE"]),
        deduper=LruDeduper(1000),
        builders=[CandleBuilder(Timeframe.M1, CAL)],
        store=InMemoryCandleStore(),
        metrics=MarketDataMetrics(),
        clock=clock,
        publisher=publisher,  # type: ignore[arg-type]
        liveness=LivenessConfig(
            threshold=timedelta(seconds=15),
            in_regular_session=lambda t: CAL.session_for(t) is not None,
            check_interval_seconds=0.01,
        ),
    )


async def test_one_degraded_then_one_connected_during_session() -> None:
    clock = FakeClock(utc_ist(9, 20))
    publisher = RecordingPublisher()
    provider = ScriptedLiveProvider(clock, [
        ("tick", None),
        ("silence", 30),   # 30s without data inside the session: stale
        ("tick", None),    # data resumes
    ], real_hold_seconds=0.2)
    await build(provider, clock, publisher).run()

    states = [(h["previous_state"], h["state"], h["reason_code"]) for h in publisher.health]
    assert states == [
        (None, "CONNECTED", "CONNECTED"),
        ("CONNECTED", "DEGRADED", "STALE_DATA"),
        ("DEGRADED", "CONNECTED", "DATA_RESUMED"),
        ("CONNECTED", "STOPPED", "STREAM_END"),
    ]


async def test_no_health_events_outside_regular_session() -> None:
    clock = FakeClock(utc_ist(16, 0))  # after the close
    publisher = RecordingPublisher()
    provider = ScriptedLiveProvider(
        clock, [("tick", None), ("silence", 600)], real_hold_seconds=0.1
    )
    await build(provider, clock, publisher).run()
    assert [h["state"] for h in publisher.health] == ["CONNECTED", "STOPPED"]


async def test_no_degraded_while_data_keeps_arriving() -> None:
    clock = FakeClock(utc_ist(9, 20))
    publisher = RecordingPublisher()
    script: list[tuple[str, float | None]] = []
    for _ in range(5):
        script += [("tick", None), ("silence", 5)]  # 5s gaps, under the 15s threshold
    provider = ScriptedLiveProvider(clock, script, real_hold_seconds=0.05)
    await build(provider, clock, publisher).run()
    assert "DEGRADED" not in [h["state"] for h in publisher.health]
