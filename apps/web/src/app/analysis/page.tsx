'use client';

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import { useApi, usePolling } from '../../hooks/useApi';
import { SectionHeader, StatRow, EmptyState, LoadingState, SignalBadge } from '../../components/ui';
import { ShieldAlert } from 'lucide-react';

// Dynamic import — chart requires browser APIs
const CandlestickChart = dynamic(
  () => import('../../components/CandlestickChart').then(m => m.CandlestickChart),
  { ssr: false, loading: () => <div className="h-[380px] bg-zinc-950 rounded flex items-center justify-center text-zinc-600 text-xs font-mono">Loading chart engine...</div> }
);

const TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h'];
const SYMBOLS = ['NIFTY50', 'BANKNIFTY', 'RELIANCE'];

export default function AnalysisPage() {
  const [symbol, setSymbol] = useState('NIFTY50');
  const [timeframe, setTimeframe] = useState('5m');

  const { data: candles, loading } = usePolling<any[]>(`/candles?symbol=${symbol}&limit=50`, 10000);
  const { data: regime } = usePolling<any>(`/regime?symbol=${symbol}`, 8000);
  const { data: signals } = useApi<any[]>(`/signals?symbol=${symbol}`);

  const lastCandle = candles && candles.length > 0 ? candles[candles.length - 1] : null;
  const prevCandle = candles && candles.length > 1 ? candles[candles.length - 2] : null;
  const priceChange = lastCandle && prevCandle ? lastCandle.close - prevCandle.close : 0;
  const priceChangePct = prevCandle ? (priceChange / prevCandle.close) * 100 : 0;

  const activeSignal = (signals || []).find((s: any) => s.action !== 'NO_TRADE');

  return (
    <div className="space-y-4 max-w-screen-2xl mx-auto">
      {/* ── Header Controls ──────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-bold uppercase tracking-wider text-zinc-100">
            Instrument Analysis
          </h1>
          <p className="text-[11px] text-zinc-500">Multi-timeframe · VWAP · ATR Zones · Order Flow Heuristics</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={symbol}
            onChange={e => setSymbol(e.target.value)}
            className="bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs font-mono px-2.5 py-1.5 rounded focus:outline-none focus:border-zinc-600"
            aria-label="Select instrument"
          >
            {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <div className="flex gap-1">
            {TIMEFRAMES.map(tf => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                aria-pressed={tf === timeframe}
                className={`px-2.5 py-1 text-[11px] font-mono rounded border transition-colors ${
                  tf === timeframe
                    ? 'bg-blue-600 border-blue-500 text-white font-bold'
                    : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:border-zinc-600'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {/* ── Chart + Volume ───────────────────────────────────────────────── */}
        <div className="xl:col-span-3 space-y-2">
          {/* Price Strip */}
          <div className="flex items-center gap-4 px-4 py-2.5 bg-zinc-950 border border-zinc-800 rounded-lg font-mono text-xs">
            <span className="text-zinc-400 font-bold text-sm">{symbol}</span>
            {lastCandle ? (
              <>
                <span className={`text-xl font-bold tabular-nums ${priceChange >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {lastCandle.close.toFixed(2)}
                </span>
                <span className={priceChange >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                  {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)} ({priceChangePct.toFixed(3)}%)
                </span>
                <span className="text-zinc-600">O:{lastCandle.open.toFixed(2)} H:{lastCandle.high.toFixed(2)} L:{lastCandle.low.toFixed(2)} C:{lastCandle.close.toFixed(2)}</span>
                <span className="text-zinc-600">Vol:{(lastCandle.volume/1000).toFixed(0)}K</span>
              </>
            ) : <span className="text-zinc-600">Loading prices...</span>}
          </div>

          {/* Candlestick Chart */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
            {loading && !candles ? (
              <LoadingState label="Loading candles..." />
            ) : candles && candles.length > 0 ? (
              <CandlestickChart candles={candles} symbol={symbol} height={400} />
            ) : (
              <EmptyState label="No candle data available" />
            )}
          </div>

          {/* Indicator Quick Strip */}
          {lastCandle && (
            <div className="grid grid-cols-6 gap-2">
              {[
                { label: 'RSI(14)', value: lastCandle.rsi14?.toFixed(1), color: lastCandle.rsi14 > 70 ? 'text-amber-400' : lastCandle.rsi14 < 30 ? 'text-rose-400' : 'text-zinc-300' },
                { label: 'MACD', value: lastCandle.macd?.toFixed(1), color: lastCandle.macd > 0 ? 'text-emerald-400' : 'text-rose-400' },
                { label: 'ADX', value: lastCandle.adx?.toFixed(1), color: lastCandle.adx > 25 ? 'text-blue-400' : 'text-zinc-400' },
                { label: 'ATR(14)', value: lastCandle.atr14?.toFixed(2), color: 'text-zinc-300' },
                { label: 'EMA9', value: lastCandle.ema9?.toFixed(2), color: 'text-indigo-400' },
                { label: 'BB Upper', value: lastCandle.bb_upper?.toFixed(2), color: 'text-zinc-400' },
              ].map(({ label, value, color }) => (
                <div key={label} className="p-2.5 bg-zinc-950 border border-zinc-800 rounded text-center">
                  <span className="text-[9px] text-zinc-600 block uppercase">{label}</span>
                  <span className={`text-xs font-bold font-mono tabular-nums ${color}`}>{value ?? '—'}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Side Panels ──────────────────────────────────────────────────── */}
        <div className="space-y-4">
          {/* Regime */}
          <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-2">
            <SectionHeader title="Market Regime" subtitle={`${symbol} · 5m`} />
            {regime ? (
              <>
                <StatRow label="Regime" value={regime.regime} />
                <StatRow label="ADX" value={`${regime.adx} (threshold: ${regime.adx_threshold})`} />
                <StatRow label="Dir. Efficiency" value={regime.directional_efficiency} />
                <StatRow label="Vol Percentile" value={`${regime.volatility_pct}th`} />
                <StatRow label="Vol Regime" value={regime.vol_regime} />
                <StatRow label="Pressure" value={regime.pressure} />
                <StatRow label="Confident" value={regime.confident ? 'Yes' : 'UNCERTAIN — No forced classification'} />
              </>
            ) : <LoadingState label="Detecting regime..." />}
          </div>

          {/* Order Flow — always shows Unavailable state */}
          <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3">
            <SectionHeader title="Order Flow" subtitle="Heuristic only" />
            <div className="p-2.5 bg-amber-500/5 border border-amber-500/20 rounded text-[11px] text-amber-400/80 leading-relaxed">
              <ShieldAlert className="w-3.5 h-3.5 inline mr-1 text-amber-500" aria-label="Warning" />
              Trade-level aggressor data not authorized. Aggressor estimation returns
              <strong> Unavailable</strong>. Institutional accumulation is NOT inferred.
            </div>
            <StatRow label="Bid-Ask Spread" value={lastCandle ? `${(lastCandle.atr14 * 0.04).toFixed(2)} pts` : '—'} />
            <StatRow label="Depth Ratio (B/A)" value="Unavailable" />
            <StatRow label="Aggressor Side" value="Unavailable" />
            <StatRow label="Absorption Signal" value="Heuristic — Not confirmed" />
          </div>

          {/* Signal for this symbol */}
          <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-2">
            <SectionHeader title="Active Signal" />
            {activeSignal ? (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <SignalBadge action={activeSignal.action} size="md" />
                  <span className="text-xs text-zinc-400">{activeSignal.strategy}</span>
                </div>
                <StatRow label="Entry Zone" value={`₹${activeSignal.entry_zone.min}–${activeSignal.entry_zone.max}`} />
                <StatRow label="Stop Loss" value={`₹${activeSignal.stop_loss}`} />
                <StatRow label="Target 1" value={`₹${activeSignal.targets[0]}`} />
                <StatRow label="R:R" value={`1:${activeSignal.risk_reward_ratio}`} />
                <StatRow label="Score" value={`${activeSignal.uncalibrated_score} (Uncalibrated)`} />
              </>
            ) : (
              <EmptyState label="No active signal for this instrument" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
