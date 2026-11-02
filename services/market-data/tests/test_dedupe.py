import pytest
from support import ist, tick

from qm_md.dedupe import LruDeduper, dedupe_key


def test_same_sequence_is_duplicate() -> None:
    d = LruDeduper(10)
    at = ist(2026, 10, 19, 10, 0)
    assert d.check_and_add(tick(at, seq=7)) is False
    assert d.check_and_add(tick(at, price="999", seq=7)) is True  # sequence wins


def test_different_sequence_same_time_is_not_duplicate() -> None:
    d = LruDeduper(10)
    at = ist(2026, 10, 19, 10, 0)
    assert d.check_and_add(tick(at, seq=1)) is False
    assert d.check_and_add(tick(at, seq=2)) is False


def test_without_sequence_identical_content_is_duplicate() -> None:
    d = LruDeduper(10)
    at = ist(2026, 10, 19, 10, 0)
    assert d.check_and_add(tick(at, "100", 10)) is False
    assert d.check_and_add(tick(at, "100", 10)) is True
    assert d.check_and_add(tick(at, "100", 11)) is False  # different quantity


def test_key_differs_by_symbol() -> None:
    at = ist(2026, 10, 19, 10, 0)
    assert dedupe_key(tick(at, seq=1, symbol="RELIANCE")) != dedupe_key(
        tick(at, seq=1, symbol="INFY"))


def test_lru_eviction_forgets_oldest() -> None:
    d = LruDeduper(2)
    a, b, c = (tick(ist(2026, 10, 19, 10, m), seq=m) for m in (0, 1, 2))
    d.check_and_add(a)
    d.check_and_add(b)
    d.check_and_add(c)  # evicts a
    assert len(d) == 2
    assert d.check_and_add(a) is False  # a is no longer remembered
    assert d.check_and_add(c) is True


def test_recent_hit_refreshes_recency() -> None:
    d = LruDeduper(2)
    a, b, c = (tick(ist(2026, 10, 19, 10, m), seq=m) for m in (0, 1, 2))
    d.check_and_add(a)
    d.check_and_add(b)
    assert d.check_and_add(a) is True  # touch a, now b is the oldest
    d.check_and_add(c)  # evicts b, not a
    assert d.check_and_add(a) is True


def test_invalid_size_is_rejected() -> None:
    with pytest.raises(ValueError):
        LruDeduper(0)
