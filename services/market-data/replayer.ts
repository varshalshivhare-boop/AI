/**
 * QuantMind AI — PC1 Market Data Replayer Stub
 *
 * Integration stub — simulates the market-data service's replay mode.
 * Reads fixture candles and emits them to two Redis Streams:
 *   - candles.closed.5m  (as loaded from fixture)
 *   - candles.closed.1m  (synthetic — downsampled from 5m close)
 *
 * All emitted records carry data_mode: "REPLAY".
 * Never emits data_mode: "LIVE" — that is the exclusive domain of
 * the production market-data service with broker authorisation.
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export interface ReplayCandleEvent {
  stream: string;
  payload: CandleStreamPayload;
}

export interface CandleStreamPayload {
  symbol: string;
  timeframe: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap: number;
  data_mode: 'REPLAY';
  ingested_at: string;
}

export class MarketDataReplayerPC1 {
  private fixturePath: string;
  private candles: Record<string, unknown>[] = [];
  public publishedStreams: ReplayCandleEvent[] = [];
  public databaseRows: CandleStreamPayload[] = [];

  constructor(fixturePath: string) {
    this.fixturePath = fixturePath;
    if (fs.existsSync(this.fixturePath)) {
      this.candles = JSON.parse(fs.readFileSync(this.fixturePath, 'utf-8')) as Record<string, unknown>[];
    }
  }

  public replaySession(_speedMultiplier = 10): { streamCount: number; dbRowCount: number } {
    this.publishedStreams = [];
    this.databaseRows = [];
    const ingestedAt = new Date().toISOString();

    for (const candle of this.candles) {
      const open   = Number(candle.open);
      const high   = Number(candle.high);
      const low    = Number(candle.low);
      const close  = Number(candle.close);
      const volume = Number(candle.volume);
      const vwap   = Number(candle.vwap);

      // ── 5-minute stream ─────────────────────────────────────────────────
      const payload5m: CandleStreamPayload = {
        symbol:    String(candle.symbol),
        timeframe: '5m',
        timestamp: String(candle.timestamp),
        open,
        high,
        low,
        close,
        volume,
        vwap,
        data_mode: 'REPLAY',
        ingested_at: ingestedAt
      };

      this.publishedStreams.push({ stream: 'candles.closed.5m', payload: payload5m });
      this.databaseRows.push(payload5m);

      // ── Synthetic 1-minute stream ────────────────────────────────────────
      // Approximation: each 5m bar generates 1 synthetic 1m record
      // (using same OHLCV — real 1m bars would have different granularity)
      const payload1m: CandleStreamPayload = {
        ...payload5m,
        timeframe: '1m',
        // Simulate narrower 1m range (within 5m range)
        high:   +(close + (high - close) * 0.6).toFixed(2),
        low:    +(close - (close - low) * 0.6).toFixed(2),
        volume: Math.round(volume / 5)
      };

      this.publishedStreams.push({ stream: 'candles.closed.1m', payload: payload1m });
    }

    return {
      streamCount: this.candles.length,  // matches fixture length (5m bars)
      dbRowCount:  this.databaseRows.length
    };
  }
}
