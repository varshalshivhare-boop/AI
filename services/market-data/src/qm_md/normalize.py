"""Tick validation and normalization.

Every rejection carries a reason code. Nothing is dropped silently.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, timedelta
from decimal import Decimal, InvalidOperation
from typing import Final

from .models import RawTick, Rejection, RejectReason, Tick

PRICE_QUANT: Final = Decimal("0.0001")
PRICE_DECIMALS: Final = 4
DEFAULT_CLOCK_SKEW: Final = timedelta(seconds=5)


class TickNormalizer:
    def __init__(
        self,
        watchlist: Iterable[str],
        *,
        exchange: str = "NSE",
        clock_skew_tolerance: timedelta = DEFAULT_CLOCK_SKEW,
    ) -> None:
        self._watchlist = frozenset(watchlist)
        self._exchange = exchange
        self._skew = clock_skew_tolerance

    @property
    def watchlist(self) -> frozenset[str]:
        return self._watchlist

    def set_watchlist(self, symbols: Iterable[str]) -> None:
        self._watchlist = frozenset(symbols)

    def normalize(self, raw: RawTick) -> Tick | Rejection:
        reject = self._reject
        if raw.symbol not in self._watchlist:
            return reject(RejectReason.UNKNOWN_SYMBOL, raw.symbol, "symbol not in watchlist")
        if raw.exchange != self._exchange:
            return reject(RejectReason.UNSUPPORTED_EXCHANGE, raw.symbol, f"exchange={raw.exchange}")

        if raw.provider_ts is None:
            return reject(RejectReason.MISSING_PROVIDER_TS, raw.symbol, "no provider timestamp")
        if raw.provider_ts.utcoffset() is None:
            return reject(RejectReason.NAIVE_TIMESTAMP, raw.symbol, "provider_ts has no timezone")
        if raw.ingest_ts.utcoffset() is None:
            return reject(RejectReason.NAIVE_TIMESTAMP, raw.symbol, "ingest_ts has no timezone")

        provider_ts = raw.provider_ts.astimezone(UTC)
        ingest_ts = raw.ingest_ts.astimezone(UTC)
        if provider_ts - ingest_ts > self._skew:
            return reject(
                RejectReason.FUTURE_TIMESTAMP,
                raw.symbol,
                f"provider_ts {provider_ts.isoformat()} is ahead of ingest by more than "
                f"{self._skew}",
            )

        price = self._parse_price(raw.price)
        if price is None:
            return reject(
                RejectReason.INVALID_PRICE, raw.symbol, f"unparseable price {raw.price!r}"
            )

        if raw.quantity < 0:
            return reject(RejectReason.INVALID_QUANTITY, raw.symbol, f"quantity={raw.quantity}")
        if raw.cumulative_volume is not None and raw.cumulative_volume < 0:
            return reject(RejectReason.INVALID_QUANTITY, raw.symbol, "negative cumulative volume")

        return Tick(
            symbol=raw.symbol,
            exchange=raw.exchange,
            price=price,
            quantity=raw.quantity,
            provider=raw.provider,
            provider_ts=provider_ts,
            ingest_ts=ingest_ts,
            data_mode=raw.data_mode,
            provider_sequence=raw.provider_sequence,
            cumulative_volume=raw.cumulative_volume,
        )

    @staticmethod
    def _parse_price(text: str) -> Decimal | None:
        try:
            value = Decimal(text.strip())
        except (InvalidOperation, AttributeError):
            return None
        if not value.is_finite() or value <= 0:
            return None
        # Reject more precision than the contract allows, judged on the normalized value
        # so that trailing zeros such as "1412.50000" are accepted.
        exponent = value.normalize().as_tuple().exponent
        if isinstance(exponent, int) and exponent < -PRICE_DECIMALS:
            return None
        return value.quantize(PRICE_QUANT)

    def _reject(self, reason: RejectReason, symbol: str, detail: str) -> Rejection:
        return Rejection(reason=reason, symbol=symbol, detail=detail)
