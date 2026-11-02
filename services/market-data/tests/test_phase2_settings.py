import pytest

from qm_md.errors import ConfigurationError
from qm_md.settings import load_settings

BASE = {
    "MARKET_DATA_WATCHLIST": "RELIANCE, HDFCBANK,INFY",
    "TRADING_CALENDAR_FILE": "calendars/nse_holidays.yaml",
    "REDIS_URL": "redis://localhost:6379/0",
    "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
}


def test_valid_minimal_environment_loads_with_defaults() -> None:
    s = load_settings(BASE)
    assert s.watchlist == ("RELIANCE", "HDFCBANK", "INFY")
    assert s.tick_persistence_enabled is False
    assert s.shutdown_timeout_seconds == 10
    assert s.http_port == 8001


def test_missing_required_variables_are_all_named() -> None:
    with pytest.raises(ConfigurationError, match="REDIS_URL, DATABASE_URL"):
        load_settings({"MARKET_DATA_WATCHLIST": "A", "TRADING_CALENDAR_FILE": "x"})


def test_tick_persistence_without_licence_flag_is_refused() -> None:
    with pytest.raises(ConfigurationError, match="TICK_LICENCE_CONFIRMED"):
        load_settings({**BASE, "TICK_PERSISTENCE_ENABLED": "true"})


def test_tick_persistence_with_licence_flag_loads() -> None:
    s = load_settings({**BASE, "TICK_PERSISTENCE_ENABLED": "true",
                       "TICK_LICENCE_CONFIRMED": "true"})
    assert s.tick_persistence_enabled and s.tick_licence_confirmed


@pytest.mark.parametrize("name,value", [
    ("MARKET_DATA_HTTP_PORT", "70000"),
    ("MARKET_DATA_HTTP_PORT", "abc"),
    ("TICK_BATCH_SIZE", "0"),
    ("STALE_DATA_THRESHOLD_SECONDS", "fifteen"),
])
def test_bad_numeric_values_fail_fast(name: str, value: str) -> None:
    with pytest.raises(ConfigurationError):
        load_settings({**BASE, name: value})


def test_empty_watchlist_is_refused() -> None:
    with pytest.raises(ConfigurationError, match="no symbols"):
        load_settings({**BASE, "MARKET_DATA_WATCHLIST": " , "})
