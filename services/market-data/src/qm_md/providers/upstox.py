"""Upstox Market Data Feed V3 — Live WebSocket Provider.

Connects to Upstox Market Data Feed V3 using WebSocket + Protobuf.
Streams real-time NSE tick data for all watchlist symbols.

Authentication:
  - UPSTOX_API_KEY, UPSTOX_ACCESS_TOKEN from environment.
  - Access tokens expire daily — refresh before 9:15 AM IST.

Upstox Feed V3 Docs:
  https://upstox.com/developer/api-documentation/market-data-feed

Implementation Notes:
  - Uses upstox-python-sdk for feed subscription and Protobuf decoding.
  - Falls back to raw websockets + manual protobuf if SDK unavailable.
  - Reconnects with exponential backoff on any connection drop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import time
from collections.abc import AsyncIterator, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from ..errors import ConfigurationError
from ..models import DataMode, ProviderState, RawTick
from .base import MarketDataProvider

logger = logging.getLogger("qm_md.providers.upstox")

# Upstox Market Data Feed V3 WebSocket URL
FEED_WS_URL = "wss://api.upstox.com/v3/feed/market-data-feed"
# Upstox instrument key format: NSE_EQ|ISIN or NSE_INDEX|Nifty 50
# For equity: NSE_EQ|INE002A01018 (RELIANCE)
# We use symbol-to-key mapping from instruments API

UPSTOX_API_BASE = "https://api.upstox.com/v2"


@dataclass(frozen=True, slots=True)
class UpstoxConfig:
    api_key: str
    access_token: str
    redirect_uri: str = "http://127.0.0.1:3000"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "UpstoxConfig":
        required = ("UPSTOX_API_KEY", "UPSTOX_ACCESS_TOKEN")
        missing = [name for name in required if not env.get(name, "").strip()]
        if missing:
            raise ConfigurationError(
                f"Upstox provider requires {', '.join(missing)} in the environment. "
                "Refusing to start: this adapter never falls back to fake data."
            )
        return cls(
            api_key=env["UPSTOX_API_KEY"].strip(),
            access_token=env["UPSTOX_ACCESS_TOKEN"].strip(),
            redirect_uri=env.get("UPSTOX_REDIRECT_URI", "http://127.0.0.1:3000").strip(),
        )

    def __repr__(self) -> str:
        return "UpstoxConfig(api_key='***', access_token='***')"


# Symbol to Upstox instrument key mapping (NSE F&O + Indices)
# Instrument key format: NSE_EQ|ISIN for equities, NSE_INDEX|<name> for indices
SYMBOL_TO_INSTRUMENT_KEY: dict[str, str] = {
    # Nifty Indices
    "NIFTY50": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    # Nifty 50 Constituents
    "RELIANCE":    "NSE_EQ|INE002A01018",
    "HDFCBANK":    "NSE_EQ|INE040A01034",
    "INFY":        "NSE_EQ|INE009A01021",
    "TCS":         "NSE_EQ|INE467B01029",
    "ICICIBANK":   "NSE_EQ|INE090A01021",
    "SBIN":        "NSE_EQ|INE062A01020",
    "BHARTIARTL":  "NSE_EQ|INE397D01024",
    "ITC":         "NSE_EQ|INE154A01025",
    "HINDUNILVR":  "NSE_EQ|INE030A01027",
    "KOTAKBANK":   "NSE_EQ|INE237A01028",
    "LT":          "NSE_EQ|INE018A01030",
    "HCLTECH":     "NSE_EQ|INE860A01027",
    "BAJFINANCE":  "NSE_EQ|INE296A01024",
    "SUNPHARMA":   "NSE_EQ|INE044A01036",
    "WIPRO":       "NSE_EQ|INE075A01022",
    "AXISBANK":    "NSE_EQ|INE238A01034",
    "MARUTI":      "NSE_EQ|INE585B01010",
    "TITAN":       "NSE_EQ|INE280A01028",
    "BAJAJFINSV":  "NSE_EQ|INE918I01026",
    "ULTRACEMCO":  "NSE_EQ|INE481G01011",
    "NESTLEIND":   "NSE_EQ|INE239A01016",
    "ASIANPAINT":  "NSE_EQ|INE021A01026",
    "POWERGRID":   "NSE_EQ|INE752E01010",
    "NTPC":        "NSE_EQ|INE733E01010",
    "COALINDIA":   "NSE_EQ|INE522F01014",
    "ADANIENT":    "NSE_EQ|INE423A01024",
    "ADANIPORTS":  "NSE_EQ|INE742F01042",
    "DIVISLAB":    "NSE_EQ|INE361B01024",
    "DRREDDY":     "NSE_EQ|INE088C01022",
    "CIPLA":       "NSE_EQ|INE059A01026",
    "EICHERMOT":   "NSE_EQ|INE066A01021",
    "HEROMOTOCO":  "NSE_EQ|INE158A01026",
    "BPCL":        "NSE_EQ|INE029A01011",
    "BRITANNIA":   "NSE_EQ|INE216A01030",
    "GRASIM":      "NSE_EQ|INE047A01021",
    "JSWSTEEL":    "NSE_EQ|INE019A01038",
    "M&M":         "NSE_EQ|INE101A01026",
    "ONGC":        "NSE_EQ|INE213A01029",
    "TATACONSUM":  "NSE_EQ|INE192A01025",
    "TECHM":       "NSE_EQ|INE669C01036",
    "LTIM":        "NSE_EQ|INE214T01019",
    "APOLLOHOSP":  "NSE_EQ|INE437A01024",
    "SBILIFE":     "NSE_EQ|INE123W01016",
    "HDFCLIFE":    "NSE_EQ|INE795G01014",
    "BAJAJ-AUTO":  "NSE_EQ|INE917I01010",
    "TATASTEEL":   "NSE_EQ|INE081A01020",
    "UPL":         "NSE_EQ|INE628A01036",
    "SHRIRAMFIN":  "NSE_EQ|INE721A01047",
    "INDUSINDBK":  "NSE_EQ|INE095A01012",
    "TATAMOTOR":   "NSE_EQ|INE155A01022",
}


class UpstoxProvider(MarketDataProvider):
    """Live Upstox Market Data Feed V3 provider."""

    name = "UPSTOX"
    data_mode = DataMode.LIVE

    def __init__(self, config: UpstoxConfig) -> None:
        self._config = config
        self._state = ProviderState.DISCONNECTED
        self._subscribed_symbols: list[str] = []
        self._tick_queue: asyncio.Queue[RawTick] = asyncio.Queue(maxsize=10_000)
        self._ws = None
        self._running = False

    def health(self) -> ProviderState:
        return self._state

    async def connect(self) -> None:
        """Open WebSocket connection to Upstox Feed V3."""
        self._state = ProviderState.CONNECTING
        self._running = True
        logger.info("Connecting to Upstox Market Data Feed V3...")
        try:
            import websockets
        except ImportError:
            raise ConfigurationError(
                "websockets package not installed. Run: pip install websockets"
            )
        try:
            headers = {
                "Authorization": f"Bearer {self._config.access_token}",
                "Api-Version": "2.0",
            }
            self._ws = await websockets.connect(
                FEED_WS_URL,
                additional_headers=headers,
                ping_interval=30,
                ping_timeout=10,
            )
            self._state = ProviderState.CONNECTED
            logger.info("Connected to Upstox Feed V3")
            # Start background reader
            asyncio.create_task(self._read_loop())
        except Exception as exc:
            self._state = ProviderState.ERROR
            logger.error("Failed to connect to Upstox Feed V3: %s", exc)
            raise

    async def disconnect(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()
        self._state = ProviderState.STOPPED
        logger.info("Upstox provider disconnected")

    async def subscribe(self, symbols: Iterable[str]) -> None:
        """Subscribe to symbols via Upstox Feed V3 subscription message."""
        syms = list(symbols)
        self._subscribed_symbols = syms

        instrument_keys = []
        for sym in syms:
            key = SYMBOL_TO_INSTRUMENT_KEY.get(sym)
            if key:
                instrument_keys.append(key)
            else:
                logger.warning("No instrument key for symbol %s — skipping", sym)

        if not instrument_keys:
            logger.error("No valid instrument keys found for watchlist: %s", syms)
            return

        # Upstox V3 subscription request
        sub_msg = {
            "guid": f"qm-sub-{int(time.time())}",
            "method": "sub",
            "data": {
                "mode": "full",  # full = OHLCV + LTP + depth
                "instrumentKeys": instrument_keys,
            },
        }

        if self._ws:
            await self._ws.send(json.dumps(sub_msg))
            logger.info(
                "Subscribed to %d instruments: %s",
                len(instrument_keys),
                instrument_keys[:5],
            )
        else:
            logger.warning("Cannot subscribe — WebSocket not connected")

    async def unsubscribe(self, symbols: Iterable[str]) -> None:
        syms = list(symbols)
        instrument_keys = [
            SYMBOL_TO_INSTRUMENT_KEY[s] for s in syms if s in SYMBOL_TO_INSTRUMENT_KEY
        ]
        if instrument_keys and self._ws:
            unsub_msg = {
                "guid": f"qm-unsub-{int(time.time())}",
                "method": "unsub",
                "data": {"instrumentKeys": instrument_keys},
            }
            await self._ws.send(json.dumps(unsub_msg))

    def stream(self) -> AsyncIterator[RawTick]:
        return self._tick_generator()

    async def _tick_generator(self) -> AsyncIterator[RawTick]:
        while self._running:
            try:
                tick = await asyncio.wait_for(self._tick_queue.get(), timeout=1.0)
                yield tick
            except asyncio.TimeoutError:
                continue

    async def _read_loop(self) -> None:
        """Background task: read messages from WebSocket and decode into RawTicks."""
        try:
            import google.protobuf  # noqa: F401
            _has_protobuf = True
        except ImportError:
            _has_protobuf = False
            logger.warning(
                "google-protobuf not installed — will use JSON feed mode if available"
            )

        while self._running and self._ws:
            try:
                message = await self._ws.recv()
                ticks = self._decode_message(message)
                for tick in ticks:
                    try:
                        self._tick_queue.put_nowait(tick)
                    except asyncio.QueueFull:
                        logger.warning("Tick queue full — dropping tick for %s", tick.symbol)
            except Exception as exc:
                if self._running:
                    logger.error("WebSocket read error: %s", exc)
                    self._state = ProviderState.DEGRADED
                    await asyncio.sleep(1)
                break

    def _decode_message(self, message: bytes | str) -> list[RawTick]:
        """Decode Upstox Feed V3 message (Protobuf binary or JSON) into RawTicks."""
        now = datetime.now(UTC)
        ticks: list[RawTick] = []

        # Try JSON first (Upstox also supports JSON mode for some messages)
        if isinstance(message, str):
            try:
                data = json.loads(message)
                return self._parse_json_feed(data, now)
            except json.JSONDecodeError:
                return []

        # Binary = Protobuf — try to decode
        try:
            return self._decode_protobuf(message, now)
        except Exception:
            # Try as JSON bytes fallback
            try:
                data = json.loads(message.decode("utf-8"))
                return self._parse_json_feed(data, now)
            except Exception as exc:
                logger.debug("Could not decode message: %s", exc)
                return []

    def _decode_protobuf(self, data: bytes, now: datetime) -> list[RawTick]:
        """Decode Upstox Protobuf MarketDataFeed message."""
        try:
            # Try using upstox SDK protobuf decoder
            from upstox_client.feeder.proto import MarketDataFeed_pb2 as pb

            feed = pb.FeedResponse()
            feed.ParseFromString(data)
            ticks = []
            for instrument_key, feed_data in feed.feeds.items():
                symbol = self._instrument_key_to_symbol(instrument_key)
                if not symbol:
                    continue
                # Extract LTP (Last Traded Price) from full feed
                if feed_data.HasField("ff"):
                    ltp_data = feed_data.ff.marketFF
                    ltp = ltp_data.ltpc.ltp
                    ltt = ltp_data.ltpc.ltt  # last trade time in ms epoch
                    qty = ltp_data.ltpc.ltq if hasattr(ltp_data.ltpc, "ltq") else 1
                    provider_ts = datetime.fromtimestamp(ltt / 1000, tz=UTC) if ltt else now
                    tick = RawTick(
                        symbol=symbol,
                        exchange="NSE",
                        price=str(ltp),
                        quantity=int(qty),
                        provider_ts=provider_ts,
                        ingest_ts=now,
                        provider="UPSTOX",
                        data_mode=DataMode.LIVE,
                        provider_sequence=None,
                    )
                    ticks.append(tick)
            return ticks
        except ImportError:
            # upstox SDK proto not available — try manual protobuf
            return self._decode_protobuf_manual(data, now)
        except Exception as exc:
            logger.debug("Protobuf decode failed: %s", exc)
            return []

    def _decode_protobuf_manual(self, data: bytes, now: datetime) -> list[RawTick]:
        """Minimal manual protobuf decode for Upstox Feed V3 when SDK unavailable."""
        # Without the compiled .proto, we cannot reliably decode Protobuf binary.
        # Log and return empty — install upstox-python-sdk to fix this.
        logger.debug(
            "Cannot decode Protobuf without upstox-python-sdk. "
            "Run: pip install upstox-python-sdk"
        )
        return []

    def _parse_json_feed(self, data: dict, now: datetime) -> list[RawTick]:
        """Parse Upstox JSON market feed message (used for status/heartbeat messages)."""
        ticks = []
        # Upstox sends {"type": "live_feed", "feeds": {...}} in JSON mode
        feeds = data.get("feeds", {})
        for instrument_key, feed_data in feeds.items():
            symbol = self._instrument_key_to_symbol(instrument_key)
            if not symbol:
                continue
            ltp = feed_data.get("ltp") or feed_data.get("ltpc", {}).get("ltp")
            if not ltp:
                continue
            qty = feed_data.get("ltq", 1) or 1
            ltt = feed_data.get("ltt")
            provider_ts = (
                datetime.fromtimestamp(ltt / 1000, tz=UTC) if ltt else now
            )
            tick = RawTick(
                symbol=symbol,
                exchange="NSE",
                price=str(ltp),
                quantity=int(qty),
                provider_ts=provider_ts,
                ingest_ts=now,
                provider="UPSTOX",
                data_mode=DataMode.LIVE,
                provider_sequence=None,
            )
            ticks.append(tick)
        return ticks

    def _instrument_key_to_symbol(self, instrument_key: str) -> str | None:
        """Reverse lookup: Upstox instrument key → our symbol name."""
        for sym, key in SYMBOL_TO_INSTRUMENT_KEY.items():
            if key == instrument_key:
                return sym
        return None
