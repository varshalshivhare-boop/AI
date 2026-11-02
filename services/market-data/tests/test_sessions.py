from datetime import date, datetime

import pytest
import yaml
from support import PLACEHOLDER_CALENDAR, TEST_CALENDAR, calendar, ist

from qm_md.errors import ConfigurationError
from qm_md.sessions import SessionCalendar


def test_saturday_and_sunday_have_no_session() -> None:
    cal = calendar()
    assert cal.session_for(ist(2026, 10, 24, 10, 0)) is None  # Saturday
    assert cal.session_for(ist(2026, 10, 25, 10, 0)) is None  # Sunday


def test_listed_holiday_has_no_session() -> None:
    cal = calendar((date(2026, 10, 21),))
    assert cal.is_trading_day(date(2026, 10, 20))
    assert cal.session_for(ist(2026, 10, 21, 10, 0)) is None
    assert cal.session_for(ist(2026, 10, 22, 10, 0)) is not None


def test_regular_session_boundaries_are_half_open() -> None:
    cal = calendar()
    assert cal.session_for(ist(2026, 10, 19, 9, 14, 59, 999999)) is None
    assert cal.session_for(ist(2026, 10, 19, 9, 15, 0)) is not None
    assert cal.session_for(ist(2026, 10, 19, 15, 29, 59, 999999)) is not None
    assert cal.session_for(ist(2026, 10, 19, 15, 30, 0)) is None


def test_session_times_are_correct_in_utc() -> None:
    session = calendar().session_for_date(date(2026, 10, 19))
    assert session.open_utc == ist(2026, 10, 19, 9, 15)
    assert session.close_utc == ist(2026, 10, 19, 15, 30)
    assert session.open_utc.isoformat() == "2026-10-19T03:45:00+00:00"


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        calendar().session_for(datetime(2026, 10, 19, 10, 0))


def test_placeholder_calendar_is_refused() -> None:
    with pytest.raises(ConfigurationError, match="status 'UNPOPULATED'"):
        SessionCalendar.from_yaml(PLACEHOLDER_CALENDAR)


def test_test_calendar_requires_explicit_opt_in() -> None:
    with pytest.raises(ConfigurationError, match="TEST calendar"):
        SessionCalendar.from_yaml(TEST_CALENDAR)
    assert SessionCalendar.from_yaml(TEST_CALENDAR, allow_test=True).holidays == frozenset()


def test_holidays_load_from_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "cal.yaml"
    path.write_text(yaml.safe_dump({
        "calendar_version": "2026-v1", "status": "POPULATED",
        "holidays": [{"date": date(2026, 10, 21), "name": "Test holiday"}],
    }))
    cal = SessionCalendar.from_yaml(path)
    assert date(2026, 10, 21) in cal.holidays


@pytest.mark.parametrize("holidays,expected", [
    ([{"date": "2026-10-21"}], "no valid date"),  # string, not a YAML date
    ([{"name": "x"}], "no valid date"),
])
def test_malformed_holiday_file_is_rejected(tmp_path, holidays, expected) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "cal.yaml"
    path.write_text(yaml.safe_dump({"calendar_version": "v", "status": "POPULATED",
                                    "holidays": holidays}))
    with pytest.raises(ConfigurationError, match=expected):
        SessionCalendar.from_yaml(path)


def test_duplicate_holiday_is_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "cal.yaml"
    path.write_text(yaml.safe_dump({
        "calendar_version": "v", "status": "POPULATED",
        "holidays": [{"date": date(2026, 10, 21)}, {"date": date(2026, 10, 21)}],
    }))
    with pytest.raises(ConfigurationError, match="duplicate"):
        SessionCalendar.from_yaml(path)


def test_unreadable_calendar_is_a_configuration_error(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ConfigurationError, match="cannot read"):
        SessionCalendar.from_yaml(tmp_path / "missing.yaml")
