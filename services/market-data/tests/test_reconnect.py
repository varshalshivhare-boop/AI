import asyncio
import random

import pytest

from qm_md.backoff import Backoff
from qm_md.metrics import MarketDataMetrics
from qm_md.providers.reconnect import run_with_reconnect


class Flaky:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    async def __call__(self) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise ConnectionError(f"socket closed #{self.calls}")


async def no_sleep(delay: float) -> None:
    return None


def backoff() -> Backoff:
    return Backoff(base=0.1, cap=1.0, rng=random.Random(0))


async def test_recovers_after_transient_failures_and_counts_them() -> None:
    m = MarketDataMetrics()
    session = Flaky(failures=2)
    await run_with_reconnect(session, backoff=backoff(), metrics=m, sleep=no_sleep)
    assert session.calls == 3
    assert m.reconnects._value.get() == 2  # type: ignore[attr-defined]


async def test_sleeps_between_attempts_with_backoff_delays() -> None:
    delays: list[float] = []

    async def record(delay: float) -> None:
        delays.append(delay)

    await run_with_reconnect(Flaky(3), backoff=backoff(), metrics=MarketDataMetrics(),
                             sleep=record)
    assert len(delays) == 3
    assert all(0.0 <= d <= 1.0 for d in delays)


async def test_gives_up_after_budget_and_reraises_last_error() -> None:
    m = MarketDataMetrics()
    with pytest.raises(ConnectionError, match="#3"):
        await run_with_reconnect(Flaky(10), backoff=backoff(), metrics=m, max_attempts=3,
                                 sleep=no_sleep)
    assert m.reconnects._value.get() == 3  # type: ignore[attr-defined]


async def test_cancellation_is_never_swallowed() -> None:
    async def hang() -> None:
        await asyncio.sleep(10)

    task = asyncio.create_task(run_with_reconnect(hang, backoff=backoff(),
                                                  metrics=MarketDataMetrics(), sleep=no_sleep))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_clean_return_ends_the_loop_without_retry() -> None:
    session = Flaky(failures=0)
    await run_with_reconnect(session, backoff=backoff(), metrics=MarketDataMetrics(),
                             sleep=no_sleep)
    assert session.calls == 1
