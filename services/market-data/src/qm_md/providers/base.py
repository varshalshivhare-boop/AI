"""Provider interface.

Every provider must set data_mode honestly and never use wall-clock time as provider_ts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterable

from ..models import DataMode, ProviderState, RawTick


class MarketDataProvider(ABC):
    name: str
    data_mode: DataMode

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def subscribe(self, symbols: Iterable[str]) -> None: ...

    @abstractmethod
    async def unsubscribe(self, symbols: Iterable[str]) -> None: ...

    @abstractmethod
    def stream(self) -> AsyncIterator[RawTick]: ...

    @abstractmethod
    def health(self) -> ProviderState: ...
