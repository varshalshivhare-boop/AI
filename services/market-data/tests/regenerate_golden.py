"""Regenerate expected-output CSVs. Run only after a deliberate, reviewed change to candle rules.

    cd services/market-data && python tests/regenerate_golden.py
Oracle tests in test_golden.py check these values independently. Golden files alone are not proof.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from support import DAY, EXPECTED, run_replay

from qm_md.golden import write_candles_csv


async def main() -> None:
    _summary, store, _m = await run_replay(("RELIANCE",), dates=(DAY,))
    for tf in ("1m", "5m", "15m", "30m", "1d"):
        rows = [c for c in store.sorted_rows() if c.timeframe.value == tf]  # type: ignore[attr-defined]
        path = EXPECTED / f"RELIANCE_2026-10-19_{tf}.csv"
        write_candles_csv(path, rows)
        print(f"wrote {path.name}: {len(rows)} rows")


if __name__ == "__main__":
    asyncio.run(main())
