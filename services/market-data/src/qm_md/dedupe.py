"""Bounded duplicate detection.

Key: (symbol, provider, provider_ts, provider_sequence) when the provider sends a sequence.
Otherwise (symbol, provider, provider_ts, price, quantity, cumulative_volume).
The window is an LRU of fixed size, so memory is bounded. A duplicate that arrives after
its key has been evicted is not detected. The window size is therefore a documented trade-off.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable

from .models import Tick


def dedupe_key(tick: Tick) -> tuple[Hashable, ...]:
    if tick.provider_sequence is not None:
        return (tick.symbol, tick.provider, tick.provider_ts, tick.provider_sequence)
    return (
        tick.symbol,
        tick.provider,
        tick.provider_ts,
        tick.price,
        tick.quantity,
        tick.cumulative_volume,
    )


class LruDeduper:
    def __init__(self, maxsize: int) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        self._maxsize = maxsize
        self._seen: OrderedDict[tuple[Hashable, ...], None] = OrderedDict()

    def __len__(self) -> int:
        return len(self._seen)

    def check_and_add(self, tick: Tick) -> bool:
        """Return True if the tick is a duplicate. Otherwise remember it."""
        key = dedupe_key(tick)
        if key in self._seen:
            self._seen.move_to_end(key)
            return True
        self._seen[key] = None
        if len(self._seen) > self._maxsize:
            self._seen.popitem(last=False)
        return False
