#!/usr/bin/env python3
"""Generate SYNTHETIC 1-minute OHLCV fixtures for NSE symbols.

These are NOT real market prices. They exist so that tests and demo modes can run
offline and deterministically. Every file is labelled SYNTHETIC in its name and in
the data_source column.

Deterministic: same seed -> byte-identical output. Re-run and compare SHA256SUMS.

Session model (NSE cash equity, regular session only):
  09:15 to 15:29 IST, 375 one-minute bars per session.
  Five consecutive weekdays, 2026-10-19 (Mon) to 2026-10-23 (Fri).
  No holidays are inside this window, so no bars are skipped.

Price model: geometric random walk with a U-shaped intraday volume profile,
so that relative-volume baselines in later phases have something realistic to fit.
"""
from __future__ import annotations

import csv
import hashlib
import math
import random
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

SEED = 20261019
IST = timezone(timedelta(hours=5, minutes=30))
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "fixtures"

SESSIONS = [date(2026, 10, 19) + timedelta(days=i) for i in range(5)]  # Mon..Fri
SESSION_START = time(9, 15)
BARS_PER_SESSION = 375  # 09:15 .. 15:29 inclusive

# symbol, exchange, starting price (INR), annualised vol, base daily volume
SYMBOLS = [
    ("RELIANCE", "NSE", 1400.00, 0.22, 9_000_000),
    ("HDFCBANK", "NSE", 1700.00, 0.19, 7_500_000),
    ("INFY", "NSE", 1600.00, 0.24, 6_000_000),
]

MINUTES_PER_YEAR = 252 * 375


def _tick(price: float) -> float:
    """Round to the NSE tick size of 0.05 INR."""
    return round(round(price / 0.05) * 0.05, 2)


def _u_shape(i: int, n: int) -> float:
    """Intraday volume multiplier: high at open and close, low at midday."""
    x = i / (n - 1)
    return 1.0 + 1.6 * ((2 * x - 1) ** 2)


def generate_symbol(rng: random.Random, symbol: str, start_price: float,
                    ann_vol: float, base_volume: int) -> list[dict]:
    minute_vol = ann_vol / math.sqrt(MINUTES_PER_YEAR)
    rows: list[dict] = []
    last_close = start_price

    for session in SESSIONS:
        # Overnight gap, small and symmetric
        last_close = _tick(last_close * math.exp(rng.gauss(0.0, 0.006)))
        price = last_close
        session_start_dt = datetime.combine(session, SESSION_START, tzinfo=IST)

        for i in range(BARS_PER_SESSION):
            open_ = price
            # Intrabar path: 4 sub-steps give realistic high and low excursions
            path = [open_]
            for _ in range(4):
                price = price * math.exp(rng.gauss(0.0, minute_vol / 2.0))
                path.append(price)

            high = _tick(max(path))
            low = _tick(min(path))
            open_ = _tick(open_)
            close = _tick(path[-1])
            # Enforce OHLC invariants after rounding
            high = max(high, open_, close)
            low = min(low, open_, close)
            if low <= 0:
                low = min(open_, close)

            volume = int(base_volume / BARS_PER_SESSION * _u_shape(i, BARS_PER_SESSION)
                          * rng.uniform(0.7, 1.3))
            bar_start_ist = session_start_dt + timedelta(minutes=i)

            rows.append({
                "data_source": "SYNTHETIC",
                "symbol": symbol,
                "exchange": "NSE",
                "session_date": session.isoformat(),
                "bar_start_utc": bar_start_ist.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": f"{open_:.2f}",
                "high": f"{high:.2f}",
                "low": f"{low:.2f}",
                "close": f"{close:.2f}",
                "volume": volume,
            })
            price = close  # next bar opens at prior close (no artificial gap intrabar)
        last_close = price
    return rows


FIELDS = ["data_source", "symbol", "exchange", "session_date", "bar_start_utc",
          "open", "high", "low", "close", "volume"]


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Independent RNG per symbol, derived from the master seed, so adding a
    # symbol later does not change existing symbols' output.
    checksums: list[str] = []
    for idx, (symbol, _exch, start, vol, base_vol) in enumerate(SYMBOLS):
        rng = random.Random(SEED + idx)
        rows = generate_symbol(rng, symbol, start, vol, base_vol)
        fname = f"SYNTHETIC_{symbol}_1m_{SESSIONS[0].isoformat()}_{SESSIONS[-1].isoformat()}.csv"
        path = OUT_DIR / fname
        write_csv(path, rows)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksums.append(f"{digest}  {fname}")
        print(f"wrote {fname}: {len(rows)} rows, sha256={digest[:16]}...")

    (OUT_DIR / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print("wrote SHA256SUMS")


if __name__ == "__main__":
    main()
