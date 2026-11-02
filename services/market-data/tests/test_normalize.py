from datetime import UTC, datetime, timedelta, timezone

import pytest
from support import ist

from qm_md.models import DataMode, RawTick, Rejection, RejectReason, Tick
from qm_md.normalize import TickNormalizer

WATCH = ("RELIANCE", "INFY")


def raw(**overrides: object) -> RawTick:
    base: dict[str, object] = {
        "symbol": "RELIANCE", "exchange": "NSE", "price": "1412.50", "quantity": 25,
        "provider_ts": ist(2026, 10, 19, 10, 0, 0), "ingest_ts": ist(2026, 10, 19, 10, 0, 0),
        "provider": "REPLAY", "data_mode": DataMode.REPLAY, "provider_sequence": 1,
    }
    base.update(overrides)
    return RawTick.model_validate(base)


def norm() -> TickNormalizer:
    return TickNormalizer(WATCH)


def test_valid_tick_is_normalized_to_utc_decimal() -> None:
    result = norm().normalize(raw())
    assert isinstance(result, Tick)
    assert result.price.as_tuple().exponent == -4
    assert str(result.price) == "1412.5000"
    assert result.provider_ts.tzinfo is not None
    assert result.provider_ts.utcoffset() == timedelta(0)


def test_non_utc_offset_is_converted_to_utc() -> None:
    ist_offset = timezone(timedelta(hours=5, minutes=30))
    local = datetime(2026, 10, 19, 15, 29, 0, tzinfo=ist_offset)  # 09:59 UTC
    result = norm().normalize(raw(provider_ts=local, ingest_ts=local))
    assert isinstance(result, Tick)
    assert result.provider_ts == datetime(2026, 10, 19, 9, 59, 0, tzinfo=UTC)
    assert result.provider_ts.utcoffset() == timedelta(0)


def test_trailing_zeros_are_accepted() -> None:
    result = norm().normalize(raw(price="1412.50000"))
    assert isinstance(result, Tick)
    assert str(result.price) == "1412.5000"


@pytest.mark.parametrize("bad_price", ["abc", "", "NaN", "Infinity", "0", "-1", "1412.00001"])
def test_invalid_prices_are_rejected(bad_price: str) -> None:
    result = norm().normalize(raw(price=bad_price))
    assert isinstance(result, Rejection)
    assert result.reason is RejectReason.INVALID_PRICE


def test_unknown_symbol_is_rejected() -> None:
    result = norm().normalize(raw(symbol="TCS"))
    assert isinstance(result, Rejection)
    assert result.reason is RejectReason.UNKNOWN_SYMBOL


def test_wrong_exchange_is_rejected() -> None:
    result = norm().normalize(raw(exchange="BSE"))
    assert isinstance(result, Rejection)
    assert result.reason is RejectReason.UNSUPPORTED_EXCHANGE


def test_missing_provider_timestamp_is_rejected() -> None:
    result = norm().normalize(raw(provider_ts=None))
    assert isinstance(result, Rejection)
    assert result.reason is RejectReason.MISSING_PROVIDER_TS


def test_naive_provider_timestamp_is_rejected() -> None:
    result = norm().normalize(raw(provider_ts=datetime(2026, 10, 19, 10, 0)))
    assert isinstance(result, Rejection)
    assert result.reason is RejectReason.NAIVE_TIMESTAMP


def test_naive_ingest_timestamp_is_rejected() -> None:
    result = norm().normalize(raw(ingest_ts=datetime(2026, 10, 19, 10, 0)))
    assert isinstance(result, Rejection)
    assert result.reason is RejectReason.NAIVE_TIMESTAMP


def test_provider_clock_ahead_beyond_tolerance_is_rejected() -> None:
    ingest = ist(2026, 10, 19, 10, 0, 0)
    result = norm().normalize(raw(provider_ts=ingest + timedelta(seconds=30), ingest_ts=ingest))
    assert isinstance(result, Rejection)
    assert result.reason is RejectReason.FUTURE_TIMESTAMP


def test_small_provider_clock_skew_is_tolerated() -> None:
    ingest = ist(2026, 10, 19, 10, 0, 0)
    result = norm().normalize(raw(provider_ts=ingest + timedelta(seconds=2), ingest_ts=ingest))
    assert isinstance(result, Tick)


def test_negative_quantity_is_rejected() -> None:
    result = norm().normalize(raw(quantity=-1))
    assert isinstance(result, Rejection)
    assert result.reason is RejectReason.INVALID_QUANTITY


def test_negative_cumulative_volume_is_rejected() -> None:
    result = norm().normalize(raw(cumulative_volume=-5))
    assert isinstance(result, Rejection)
    assert result.reason is RejectReason.INVALID_QUANTITY


def test_zero_quantity_is_valid() -> None:
    result = norm().normalize(raw(quantity=0))
    assert isinstance(result, Tick)
    assert result.quantity == 0


def test_watchlist_can_be_replaced() -> None:
    n = norm()
    n.set_watchlist(["TCS"])
    assert n.watchlist == frozenset({"TCS"})
    assert isinstance(n.normalize(raw()), Rejection)
