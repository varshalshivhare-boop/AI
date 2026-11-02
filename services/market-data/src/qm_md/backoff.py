"""Exponential backoff with full jitter: delay = uniform(0, min(cap, base * 2**attempt))."""

from __future__ import annotations

import random
from typing import Final

_MAX_EXPONENT: Final = 30


class Backoff:
    def __init__(self, *, base: float, cap: float, rng: random.Random | None = None) -> None:
        if base <= 0 or cap <= 0:
            raise ValueError("base and cap must be positive")
        self._base = base
        self._cap = cap
        self._rng = rng if rng is not None else random.Random()
        self._attempt = 0

    @property
    def attempt(self) -> int:
        return self._attempt

    def ceiling(self) -> float:
        exponent = min(self._attempt, _MAX_EXPONENT)
        ceiling = self._base * float(2**exponent)
        return min(self._cap, ceiling)

    def next_delay(self) -> float:
        delay = self._rng.uniform(0.0, self.ceiling())
        self._attempt += 1
        return delay

    def reset(self) -> None:
        self._attempt = 0
