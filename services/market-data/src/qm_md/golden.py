"""Writes candles to CSV in a stable format. Used for committed expected-output files."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

from .models import Candle

COLUMNS = ("symbol", "timeframe", "session_date", "bar_start_ts", "bar_end_ts",
           "open", "high", "low", "close", "volume", "tick_count", "is_final")


def _row(c: Candle) -> dict[str, str]:
    return {
        "symbol": c.symbol,
        "timeframe": c.timeframe.value,
        "session_date": c.session_date.isoformat(),
        "bar_start_ts": c.bar_start_ts.isoformat(),
        "bar_end_ts": c.bar_end_ts.isoformat(),
        "open": format(c.open, "f"),
        "high": format(c.high, "f"),
        "low": format(c.low, "f"),
        "close": format(c.close, "f"),
        "volume": str(c.volume),
        "tick_count": str(c.tick_count),
        "is_final": "true" if c.is_final else "false",
    }


def write_candles_csv(path: Path, candles: Sequence[Candle]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for candle in candles:
            writer.writerow(_row(candle))
