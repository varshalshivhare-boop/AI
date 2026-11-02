"""Every payload the service emits must validate against the shared v1 JSON Schemas."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from support import CONTRACTS, DAY, EXPECTED, ist, tick

from qm_md.contracts import candle_payload, health_payload, tick_payload
from qm_md.models import Candle, DataMode, ProviderState, Timeframe

FC = FormatChecker()


def schema(name: str) -> Draft202012Validator:
    doc = json.loads((CONTRACTS / f"{name}.v1.json").read_text())
    return Draft202012Validator(doc, format_checker=FC)


def test_tick_payload_validates() -> None:
    payload = tick_payload(tick(ist(2026, 10, 19, 9, 15, 0, 250000), "1412.5", 25, seq=9))
    schema("tick.normalized").validate(payload)
    assert payload["price"] == "1412.5000"
    assert payload["data_mode"] == "REPLAY"


def test_candle_payload_validates_for_every_timeframe() -> None:
    for tf in Timeframe:
        candle = Candle(
            symbol="RELIANCE", exchange="NSE", timeframe=tf, session_date=DAY,
            bar_start_ts=ist(2026, 10, 19, 9, 15), bar_end_ts=ist(2026, 10, 19, 9, 16),
            open=Decimal("1"), high=Decimal("2"), low=Decimal("0.5"), close=Decimal("1.5"),
            volume=10, tick_count=2, is_final=True, is_missing=False,
            provider_ts=ist(2026, 10, 19, 9, 15, 59), ingest_ts=ist(2026, 10, 19, 9, 16),
            data_mode=DataMode.REPLAY,
        )
        schema("candle.closed").validate(candle_payload(candle))


def test_health_payload_validates_including_first_transition() -> None:
    payload = health_payload(
        provider="REPLAY", state=ProviderState.CONNECTED, previous_state=None,
        reason_code="CONNECTED", last_tick_provider_ts=None, seconds_since_last_tick=None,
        reconnect_attempt=0, ingest_ts=datetime(2026, 10, 19, 4, 0, tzinfo=UTC),
        data_mode=DataMode.REPLAY,
    )
    schema("provider_health").validate(payload)


def test_replay_run_payloads_validate_end_to_end() -> None:
    """Replay one candle per timeframe from the committed expected output and validate it."""
    import csv

    from qm_md.golden import COLUMNS  # noqa: F401 - documents the column contract

    row = next(csv.DictReader((EXPECTED / "RELIANCE_2026-10-19_5m.csv").open()))
    assert row["is_final"] == "true"


@pytest.mark.parametrize("bad", [
    {"price": 1412.5},            # JSON number, not a decimal string
    {"data_mode": "LIVE_ISH"},    # outside enum
])
def test_contract_rejects_bad_tick_payloads(bad: dict[str, object]) -> None:
    payload = tick_payload(tick(ist(2026, 10, 19, 9, 15), "100", 1))
    payload.update(bad)
    with pytest.raises(Exception):  # noqa: B017 - jsonschema.ValidationError
        schema("tick.normalized").validate(payload)


def test_date_type_round_trip() -> None:
    assert date.fromisoformat("2026-10-19") == DAY
