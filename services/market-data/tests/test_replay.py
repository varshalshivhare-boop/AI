from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from support import DAY, FIXTURES, ist

from qm_md.models import DataMode, ProviderState
from qm_md.providers.replay import ReplayProvider, load_bars


async def collect(p: ReplayProvider) -> list:  # type: ignore[type-arg]
    return [t async for t in p.stream()]


async def test_replay_emits_only_replay_mode_and_fixture_timestamps() -> None:
    frozen = datetime(2030, 1, 1, tzinfo=UTC)  # wall clock is deliberately far away
    p = ReplayProvider(FIXTURES, ["RELIANCE"], session_dates=[DAY], clock=lambda: frozen)
    await p.connect()
    ticks = await collect(p)
    await p.disconnect()

    assert len(ticks) == 375 * 4
    assert all(t.data_mode is DataMode.REPLAY for t in ticks)
    assert all(t.ingest_ts == frozen for t in ticks)
    assert ticks[0].provider_ts == ist(2026, 10, 19, 9, 15, 0)
    assert all(t.provider_ts is not None and t.provider_ts.year == 2026 for t in ticks)


async def test_ticks_are_emitted_in_provider_time_order() -> None:
    p = ReplayProvider(FIXTURES, ["RELIANCE", "INFY"], session_dates=[DAY])
    await p.connect()
    ticks = await collect(p)
    stamps = [t.provider_ts for t in ticks]
    assert stamps == sorted(stamps)
    assert len({t.provider_sequence for t in ticks}) == len(ticks)


async def test_bar_volume_is_preserved_exactly() -> None:
    bars = load_bars(FIXTURES / "SYNTHETIC_RELIANCE_1m_2026-10-19_2026-10-23.csv")
    expected = sum(b.volume for b in bars if b.bar_start.date() == DAY
                   or _is_day(b.bar_start))
    p = ReplayProvider(FIXTURES, ["RELIANCE"], session_dates=[DAY])
    await p.connect()
    got = sum(t.quantity for t in await collect(p))
    assert got == expected


def _is_day(ts: datetime) -> bool:
    from zoneinfo import ZoneInfo

    return ts.astimezone(ZoneInfo("Asia/Kolkata")).date() == DAY


async def test_session_filter_excludes_other_days() -> None:
    p = ReplayProvider(FIXTURES, ["RELIANCE"], session_dates=[DAY])
    await p.connect()
    ticks = await collect(p)
    assert all(t.provider_ts is not None and t.provider_ts.date() <= (DAY + timedelta(days=1))
               for t in ticks)
    assert len(ticks) == 375 * 4


async def test_stream_before_connect_is_an_error() -> None:
    p = ReplayProvider(FIXTURES, ["RELIANCE"])
    with pytest.raises(RuntimeError, match="before connect"):
        await collect(p)


async def test_state_follows_lifecycle() -> None:
    p = ReplayProvider(FIXTURES, ["RELIANCE"], session_dates=[DAY])
    assert p.health() is ProviderState.DISCONNECTED
    await p.connect()
    assert p.health() is ProviderState.CONNECTED
    await p.disconnect()
    assert p.health() is ProviderState.STOPPED


async def test_subscribe_and_unsubscribe_change_output() -> None:
    p = ReplayProvider(FIXTURES, ["RELIANCE"], session_dates=[DAY])
    await p.subscribe(["INFY"])
    await p.connect()
    symbols = {t.symbol for t in await collect(p)}
    assert symbols == {"RELIANCE", "INFY"}
    await p.unsubscribe(["INFY"])
    await p.connect()
    assert {t.symbol for t in await collect(p)} == {"RELIANCE"}


async def test_missing_fixture_fails_loudly(tmp_path: Path) -> None:
    p = ReplayProvider(tmp_path, ["NOPE"])
    with pytest.raises(FileNotFoundError, match="NOPE"):
        await p.connect()


async def test_live_labelled_fixture_is_refused(tmp_path: Path) -> None:
    src = FIXTURES / "SYNTHETIC_RELIANCE_1m_2026-10-19_2026-10-23.csv"
    text = src.read_text().replace("SYNTHETIC", "LIVE")
    (tmp_path / "SYNTHETIC_RELIANCE_1m_x.csv").write_text(text)
    with pytest.raises(ValueError, match="unsupported data_source"):
        load_bars(tmp_path / "SYNTHETIC_RELIANCE_1m_x.csv")


def test_negative_speed_is_rejected() -> None:
    with pytest.raises(ValueError, match="speed"):
        ReplayProvider(FIXTURES, ["RELIANCE"], speed=-1)


async def test_positive_speed_paces_emission_without_changing_content() -> None:
    fast = ReplayProvider(FIXTURES, ["RELIANCE"], session_dates=[DAY], speed=0)
    paced = ReplayProvider(FIXTURES, ["RELIANCE"], session_dates=[DAY], speed=1e9)
    await fast.connect()
    await paced.connect()
    a = [(t.provider_ts, t.price, t.quantity) for t in await collect(fast)]
    b = [(t.provider_ts, t.price, t.quantity) for t in await collect(paced)]
    assert a == b
