'use client';

import React from 'react';
import { usePolling, useApi } from '../hooks/useApi';
import { SignalBadge, RegimeBadge, MetricCard, SectionHeader, LoadingState, EmptyState } from '../components/ui';
import { Activity, ShieldCheck, Zap, Wifi } from 'lucide-react';

function fmt(n: number, dec = 2): string {
  return n.toLocaleString('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function pct(n: number): string {
  return (n >= 0 ? '+' : '') + (n * 100).toFixed(2) + '%';
}

export default function DashboardPage() {
  const { data: watchlist, loading: wlLoading } = usePolling<any[]>('/market/watchlist', 3000);
  const { data: regime } = useApi<any>('/regime?symbol=NIFTY50');
  const { data: positions } = usePolling<any>('/paper-trading/positions', 5000);
  const { data: signals } = useApi<any[]>('/signals');
  const { data: health } = usePolling<any>('/health', 8000);

  const activeSignals = (signals || []).filter((s: any) => s.action !== 'NO_TRADE');

  return (
    <div className="space-y-5 max-w-screen-2xl mx-auto">

      {/* ── Status Strip ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
          <div className="flex items-center justify-between text-zinc-500 text-[10px] uppercase tracking-wider mb-2">
            <span>NSE Market</span>
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
          </div>
          <p className="text-base font-bold text-zinc-100">REGULAR SESSION</p>
          <p className="text-[11px] text-zinc-600 mt-0.5">09:15 – 15:30 IST</p>
        </div>

        <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
          <div className="flex items-center justify-between text-zinc-500 text-[10px] uppercase tracking-wider mb-2">
            <span>NIFTY50 Regime</span>
            <Activity className="w-3.5 h-3.5 text-blue-400" />
          </div>
          {regime ? (
            <>
              <div className="mb-1"><RegimeBadge regime={regime.regime} /></div>
              <p className="text-[11px] text-zinc-500 mt-1">
                ADX {regime.adx} | DE Ratio {regime.directional_efficiency} | Vol {regime.volatility_pct}th %tile
              </p>
            </>
          ) : (
            <p className="text-base font-bold text-blue-400">TRENDING (BULLISH)</p>
          )}
        </div>

        <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
          <div className="flex items-center justify-between text-zinc-500 text-[10px] uppercase tracking-wider mb-2">
            <span>Paper Capital</span>
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <p className="text-base font-bold text-zinc-100">
            ₹{positions ? fmt(positions.virtual_capital, 0) : '10,00,000'}
          </p>
          <p className="text-[11px] text-emerald-400 mt-0.5">
            Total P&L: +₹{positions ? fmt(positions.total_pnl) : '0.00'} [PAPER]
          </p>
        </div>

        <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
          <div className="flex items-center justify-between text-zinc-500 text-[10px] uppercase tracking-wider mb-2">
            <span>Feed Health</span>
            <Wifi className="w-3.5 h-3.5 text-purple-400" />
          </div>
          <p className="text-base font-bold text-zinc-100">
            {health?.status || 'HEALTHY'}
          </p>
          <p className="text-[11px] text-zinc-500 mt-0.5">
            Latency: {health?.latency_ms ?? '1.2'}ms | Mode: [DEMO]
          </p>
        </div>
      </div>

      {/* ── Watchlist ─────────────────────────────────────────────────────── */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
        <div className="px-5 py-3 border-b border-zinc-800 flex items-center justify-between">
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-200">Intraday Watchlist</h2>
            <p className="text-[10px] text-zinc-600">Live ticker / 5m indicators — refreshes every 3s</p>
          </div>
          <span className="text-[10px] font-mono text-zinc-600 px-2 py-0.5 bg-zinc-900 rounded border border-zinc-800">DEMO FEED</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono" role="table" aria-label="Instrument watchlist">
            <thead className="bg-zinc-900/60 text-zinc-500">
              <tr>
                {['Symbol','LTP (₹)','Chg %','Session VWAP','RSI(14)','RVOL','ADX','Signal','Regime'].map(h => (
                  <th key={h} scope="col" className="py-2.5 px-3 font-semibold text-right first:text-left">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-900">
              {wlLoading ? (
                <tr><td colSpan={9}><LoadingState label="Fetching watchlist..." /></td></tr>
              ) : (watchlist || []).map((row: any) => {
                const chgPos = row.change_pct >= 0;
                return (
                  <tr key={row.symbol} className="hover:bg-zinc-900/40 transition-colors">
                    <td className="py-2.5 px-3 font-bold text-zinc-100">{row.symbol}</td>
                    <td className={`py-2.5 px-3 text-right font-bold tabular-nums ${chgPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {fmt(row.ltp)}
                    </td>
                    <td className={`py-2.5 px-3 text-right tabular-nums ${chgPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {chgPos ? '+' : ''}{row.change_pct?.toFixed(3)}%
                    </td>
                    <td className="py-2.5 px-3 text-right text-zinc-300 tabular-nums">{fmt(row.vwap)}</td>
                    <td className="py-2.5 px-3 text-right text-zinc-300 tabular-nums">{row.rsi14}</td>
                    <td className={`py-2.5 px-3 text-right font-semibold tabular-nums ${row.rvol >= 2 ? 'text-blue-400' : row.rvol < 1 ? 'text-zinc-600' : 'text-zinc-300'}`}>
                      {row.rvol}x
                    </td>
                    <td className="py-2.5 px-3 text-right text-zinc-400 tabular-nums">{row.adx}</td>
                    <td className="py-2.5 px-3"><SignalBadge action={row.signal} /></td>
                    <td className="py-2.5 px-3"><RegimeBadge regime={row.regime} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Active Signals ────────────────────────────────────────────────── */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-5">
        <SectionHeader
          title="Active Strategy Signals"
          subtitle="Explainable evidence — NO uncalibrated score presented as probability"
          right={<span className="text-[10px] font-mono text-zinc-600">{activeSignals.length} active</span>}
        />

        {!signals ? <LoadingState /> : activeSignals.length === 0 ? <EmptyState label="No active BUY/SELL signals" /> : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {activeSignals.map((sig: any) => (
              <div key={sig.signal_id} className="p-4 bg-zinc-900/40 border border-zinc-800/70 rounded-lg space-y-3">
                <div className="flex items-center gap-2 justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-zinc-100">{sig.symbol}</span>
                    <span className="text-[10px] text-zinc-500 px-1.5 py-0.5 bg-zinc-900 rounded border border-zinc-800">{sig.strategy} • {sig.timeframe}</span>
                    <SignalBadge action={sig.action} size="md" />
                  </div>
                  <span className="text-[10px] font-mono text-zinc-500">{new Date(sig.timestamp).toLocaleTimeString('en-IN')}</span>
                </div>

                <div className="grid grid-cols-4 gap-2 text-[11px] font-mono">
                  <div className="p-2 bg-zinc-900 rounded">
                    <span className="text-zinc-600 block text-[9px] uppercase">Entry</span>
                    <span className="text-zinc-200">₹{sig.entry_zone.min}–{sig.entry_zone.max}</span>
                  </div>
                  <div className="p-2 bg-zinc-900 rounded">
                    <span className="text-zinc-600 block text-[9px] uppercase">SL</span>
                    <span className="text-rose-400">₹{sig.stop_loss}</span>
                  </div>
                  <div className="p-2 bg-zinc-900 rounded">
                    <span className="text-zinc-600 block text-[9px] uppercase">T1</span>
                    <span className="text-emerald-400">₹{sig.targets[0]}</span>
                  </div>
                  <div className="p-2 bg-zinc-900 rounded">
                    <span className="text-zinc-600 block text-[9px] uppercase">R:R</span>
                    <span className="text-blue-400">1:{sig.risk_reward_ratio}</span>
                  </div>
                </div>

                <div className="text-[11px] text-zinc-500">
                  <span className="text-zinc-400 font-semibold">Volume Confirmed: </span>
                  <span className={sig.volume_confirmation ? 'text-emerald-400' : 'text-rose-400'}>
                    {sig.volume_confirmation ? 'Yes' : 'No'}
                  </span>
                  {' · '}
                  <span className="text-zinc-400 font-semibold">Score: </span>
                  <span className="text-zinc-300">
                    {sig.calibrated ? `Calibrated ${(sig.probability * 100).toFixed(1)}%` : `Uncalibrated rule: ${sig.uncalibrated_score} (not a probability)`}
                  </span>
                </div>

                <p className="text-[11px] text-zinc-500 border-t border-zinc-800/60 pt-2">
                  <span className="text-zinc-400">Net expected return after costs: </span>
                  <span className="text-zinc-200">{(sig.net_expected_return_pct * 100).toFixed(2)}%</span>
                  {sig.fee_breakdown && (
                    <span className="text-zinc-600"> (fees ₹{sig.fee_breakdown.total_cost} total)</span>
                  )}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
