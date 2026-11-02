import random

import pytest

from qm_md.backoff import Backoff


def test_ceiling_doubles_then_caps() -> None:
    b = Backoff(base=1.0, cap=10.0, rng=random.Random(0))
    ceilings = []
    for _ in range(6):
        ceilings.append(b.ceiling())
        b.next_delay()
    assert ceilings == [1.0, 2.0, 4.0, 8.0, 10.0, 10.0]


def test_delay_is_jittered_within_bounds() -> None:
    b = Backoff(base=1.0, cap=60.0, rng=random.Random(42))
    for _ in range(200):
        ceiling = b.ceiling()
        delay = b.next_delay()
        assert 0.0 <= delay <= ceiling


def test_same_seed_gives_same_sequence() -> None:
    a = Backoff(base=0.5, cap=30.0, rng=random.Random(7))
    c = Backoff(base=0.5, cap=30.0, rng=random.Random(7))
    assert [a.next_delay() for _ in range(10)] == [c.next_delay() for _ in range(10)]


def test_reset_restarts_the_schedule() -> None:
    b = Backoff(base=1.0, cap=100.0, rng=random.Random(1))
    for _ in range(5):
        b.next_delay()
    assert b.attempt == 5
    b.reset()
    assert b.attempt == 0
    assert b.ceiling() == 1.0


def test_very_large_attempt_does_not_overflow() -> None:
    b = Backoff(base=1.0, cap=5.0, rng=random.Random(3))
    for _ in range(5000):
        b.next_delay()
    assert b.ceiling() == 5.0


@pytest.mark.parametrize("base,cap", [(0, 1), (1, 0), (-1, 1)])
def test_invalid_parameters_are_rejected(base: float, cap: float) -> None:
    with pytest.raises(ValueError):
        Backoff(base=base, cap=cap)
