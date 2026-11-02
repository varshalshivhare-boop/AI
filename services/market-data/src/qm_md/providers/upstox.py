"""Upstox Market Data Feed V3 adapter. SCAFFOLD. It cannot produce data yet.

What exists:
  * Credentials are read from the environment. Missing credentials raise ConfigurationError
    at construction. There is no fallback to replay or demo data.

What does not exist yet (Milestone 1.2 is not complete):
  * The feed is Protobuf-encoded. The official .proto file is published by Upstox. It has not
    been vendored here and has not been compiled into a Python module.
  * No recorded binary frames exist in this repository. The decoder cannot be unit-tested until
    frames are captured from an authorised session and committed as fixtures.
  * connect() raises ProviderNotImplementedError. It does not open a socket.

Before implementation, verify the current official documentation for the subscription request
format, the auth flow, the market-status messages and the connection limits. Record the
documentation version in this module's header when it lands.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Mapping
from dataclasses import dataclass

from ..errors import ConfigurationError, ProviderNotImplementedError
from ..models import DataMode, ProviderState, RawTick
from .base import MarketDataProvider


@dataclass(frozen=True, slots=True)
class UpstoxConfig:
    api_key: str
    access_token: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> UpstoxConfig:
        required = ("UPSTOX_API_KEY", "UPSTOX_ACCESS_TOKEN")
        missing = [name for name in required if not env.get(name, "").strip()]
        if missing:
            raise ConfigurationError(
                f"Upstox provider requires {', '.join(missing)} in the environment. "
                "Refusing to start: this adapter never falls back to fake data."
            )
        return cls(api_key=env["UPSTOX_API_KEY"].strip(),
                   access_token=env["UPSTOX_ACCESS_TOKEN"].strip())

    def __repr__(self) -> str:
        # Never print secrets, even in tracebacks or logs.
        return "UpstoxConfig(api_key='***', access_token='***')"


class UpstoxProvider(MarketDataProvider):
    name = "UPSTOX"
    data_mode = DataMode.LIVE

    def __init__(self, config: UpstoxConfig) -> None:
        self._config = config
        self._state = ProviderState.DISCONNECTED

    def health(self) -> ProviderState:
        return self._state

    async def connect(self) -> None:
        self._state = ProviderState.ERROR
        raise ProviderNotImplementedError(
            "Upstox feed decoder is not implemented. The official Market Data Feed V3 .proto "
            "is not vendored and no recorded frames exist. See Milestone 1.2."
        )

    async def disconnect(self) -> None:
        self._state = ProviderState.STOPPED

    async def subscribe(self, symbols: Iterable[str]) -> None:
        raise ProviderNotImplementedError("subscribe is unavailable until the decoder lands")

    async def unsubscribe(self, symbols: Iterable[str]) -> None:
        raise ProviderNotImplementedError("unsubscribe is unavailable until the decoder lands")

    def stream(self) -> AsyncIterator[RawTick]:
        raise ProviderNotImplementedError("stream is unavailable until the decoder lands")

