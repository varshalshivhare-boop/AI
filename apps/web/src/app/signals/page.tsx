'use client';

import React, { useState } from 'react';
import { useApi } from '../../hooks/useApi';
import { SignalBadge, RegimeBadge, SectionHeader, LoadingState, EmptyState } from '../../components/ui';
import { Radio, ChevronDown, ChevronUp, Clock, AlertTriangle } from 'lucide-react';

const ACTION_FILTER = ['ALL', 'BUY', 'SELL', 'NO_TRADE'] as const;

type SignalStatus = 'GENERATED' | 'DELIVERED' | 'INVALIDATED' | 'EXPIRED' | 'CLOSED';

function getSignalStatus(sig: Record<string, unknown>): SignalStatus {
  if (sig.status) return sig.status as SignalStatus;
  const ts = new Date(sig.timestamp as string).getTime();
  const ageMs = Date.now() - ts;
  if (ageMs > 30 * 60 * 1000) return 'EXPIRED';
  return 'GENERATED';
}

function getSignalAge(timestamp: string): { label: string; urgent: boolean } {
  const ageMs = Date.now() - new Date(timestamp).getTime();
  const mins = Math.floor(ageMs / 60_000);
  if (mins < 1)  return { label: 'Just now', urgent: false };
  if (mins < 5)  return { label: `${mins}m ago`, urgent: false };
  if (mins < 15) return { label: `${mins}m ago — Approaching expiry`, urgent: true };
  return { label: `${mins}m ago — EXPIRED`, urgent: true };
}

const STATUS_STYLES: Record<SignalStatus, string> = {
  GENERATED:   'bg-blue-500/10 text-blue-300 border-blue-500/30',
  DELIVERED:   'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
  INVALIDATED: 'bg-rose-500/10 text-rose-300 border-rose-500/30',
  EXPIRED:     'bg-zinc-700/40 text-zinc-500 border-zinc-700',
  CLOSED:      'bg-zinc-700/40 text-zinc-400 border-zinc-700',
};

export default function SignalsPage() {
  const { data: signals, loading } = useApi<Record<string, unknown>[]>('/signals');
  const [filter, setFilter]     = useState<string>('ALL');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggleExpand = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const filtered = (signals ?? []).filter(
    s => filter === 'ALL' || s.action === filter
  );

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-bold uppercase tracking-wider text-zinc-100 flex items-center gap-2">
            <Radio className="w-4 h-4 text-blue-400" aria-hidden />
            Signal Intelligence Feed
          </h1>
          <p className="text-[11px] text-zinc-500">
            All signals include entry zone, stop, targets, fee breakdown, R:R ratio, and explicit
            invalidation criteria. Signals expire after 30 minutes.
          </p>
        </div>
        <div className="flex gap-1">
          {ACTION_FILTER.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              aria-pressed={filter === f}
              className={`px-2.5 py-1 text-[10px] font-mono font-bold rounded border uppercase transition-colors ${
                filter === f
                  ? 'bg-blue-600 border-blue-500 text-white'
                  : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-200'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingState label="Fetching signals..." />
      ) : filtered.length === 0 ? (
        <EmptyState label="No signals match filter" />
      ) : (
        <div className="space-y-3" role="feed" aria-label="Signal feed">
          {filtered.map((sig) => {
            const id         = sig.signal_id as string;
            const isExpanded = expanded.has(id);
            const isNoTrade  = sig.action === 'NO_TRADE';
            const status     = getSignalStatus(sig);
            const age        = getSignalAge(sig.timestamp as string);
            const isExpired  = status === 'EXPIRED';

            return (
              <article
                key={id}
                className={`bg-zinc-950 border rounded-lg overflow-hidden transition-opacity ${
                  isExpired  ? 'border-zinc-800/40 opacity-60' :
                  isNoTrade  ? 'border-zinc-800/60 opacity-80' :
                               'border-zinc-800'
                }`}
                aria-label={`${sig.action as string} signal for ${sig.symbol as string}`}
              >
                {/* Header Row */}
                <button
                  className="w-full text-left px-5 py-4 flex items-center justify-between hover:bg-zinc-900/30 transition-colors"
                  onClick={() => toggleExpand(id)}
                  aria-expanded={isExpanded}
                >
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="font-bold text-sm text-zinc-100 tabular-nums">{sig.symbol as string}</span>
                    <SignalBadge action={sig.action as string} size="md" />
                    <span className="text-[10px] text-zinc-600 font-mono px-1.5 py-0.5 bg-zinc-900 rounded border border-zinc-800">
                      {sig.strategy as string} · {sig.timeframe as string}
                    </span>
                    <RegimeBadge regime={sig.regime as string} />

                    {/* Status badge */}
                    <span className={`text-[10px] font-mono font-bold border px-1.5 py-0.5 rounded ${STATUS_STYLES[status]}`}>
                      {status}
                    </span>

                    {isNoTrade && (
                      <span className="text-[10px] text-amber-400 font-mono font-bold border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 rounded flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" aria-hidden />
                        INSUFFICIENT EVIDENCE
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-3 text-[11px] font-mono text-zinc-500 shrink-0">
                    {/* Freshness indicator */}
                    <span className={`flex items-center gap-1 ${age.urgent ? 'text-amber-400' : ''}`}>
                      <Clock className="w-3 h-3" aria-hidden />
                      {age.label}
                    </span>
                    {isExpanded
                      ? <ChevronUp  className="w-4 h-4" aria-label="Collapse" />
                      : <ChevronDown className="w-4 h-4" aria-label="Expand" />}
                  </div>
                </button>

                {/* Collapsed Quick Row */}
                {!isExpanded && !isNoTrade && !isExpired && (
                  <div className="px-5 pb-3 grid grid-cols-2 sm:grid-cols-5 gap-3 text-[11px] font-mono">
                    <div><span className="text-zinc-600 block text-[9px] uppercase">Entry</span>
                      <span className="text-zinc-200">₹{(sig.entry_zone as Record<string, number>).min}–{(sig.entry_zone as Record<string, number>).max}</span></div>
                    <div><span className="text-zinc-600 block text-[9px] uppercase">Stop</span>
                      <span className="text-rose-400">₹{sig.stop_loss as number}</span></div>
                    <div><span className="text-zinc-600 block text-[9px] uppercase">T1 / T2</span>
                      <span className="text-emerald-400">₹{(sig.targets as number[])[0]}{(sig.targets as number[])[1] ? ` / ₹${(sig.targets as number[])[1]}` : ''}</span></div>
                    <div><span className="text-zinc-600 block text-[9px] uppercase">R:R</span>
                      <span className="text-blue-400">1:{sig.risk_reward_ratio as number}</span></div>
                    <div><span className="text-zinc-600 block text-[9px] uppercase">Net Return est.</span>
                      <span className="text-zinc-300">{(((sig.net_expected_return_pct as number) ?? 0) * 100).toFixed(2)}%</span></div>
                  </div>
                )}

                {/* Full Expanded Panel */}
                {isExpanded && (
                  <div className="px-5 pb-5 space-y-4 border-t border-zinc-800/60">
                    {/* Price Levels */}
                    {!isNoTrade && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-4 text-[11px] font-mono">
                        <div className="p-3 bg-zinc-900 rounded border border-zinc-800">
                          <span className="text-zinc-600 block text-[9px] uppercase mb-0.5">Entry Zone</span>
                          <span className="text-zinc-100 font-semibold">₹{(sig.entry_zone as Record<string, number>).min} – ₹{(sig.entry_zone as Record<string, number>).max}</span>
                        </div>
                        <div className="p-3 bg-zinc-900 rounded border border-zinc-800">
                          <span className="text-zinc-600 block text-[9px] uppercase mb-0.5">Stop Loss</span>
                          <span className="text-rose-400 font-semibold">₹{sig.stop_loss as number}</span>
                        </div>
                        <div className="p-3 bg-zinc-900 rounded border border-zinc-800">
                          <span className="text-zinc-600 block text-[9px] uppercase mb-0.5">Targets</span>
                          <span className="text-emerald-400 font-semibold">{(sig.targets as number[]).map(t => `₹${t}`).join(' / ')}</span>
                        </div>
                        <div className="p-3 bg-zinc-900 rounded border border-zinc-800">
                          <span className="text-zinc-600 block text-[9px] uppercase mb-0.5">Risk / Reward</span>
                          <span className="text-blue-400 font-semibold">1 : {sig.risk_reward_ratio as number}</span>
                        </div>
                      </div>
                    )}

                    {/* Evidence */}
                    <div>
                      <p className="text-[10px] text-zinc-500 uppercase font-bold mb-1.5">Supporting Evidence</p>
                      <ul className="space-y-1" aria-label="Signal evidence">
                        {(sig.supporting_evidence as string[]).map((ev, i) => (
                          <li key={i} className="text-[11px] text-zinc-400 flex gap-2">
                            <span className="text-blue-400 shrink-0">{i + 1}.</span>
                            <span>{ev}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Structure & Order Flow */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <p className="text-[10px] text-zinc-500 uppercase font-bold mb-1">Market Structure</p>
                        <p className="text-[11px] text-zinc-400 leading-relaxed">{sig.structure_explanation as string}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-zinc-500 uppercase font-bold mb-1">Order Flow</p>
                        <p className="text-[11px] text-zinc-500 italic">
                          {sig.order_flow_evidence as string}
                          {sig.order_flow_evidence === 'Unavailable' && (
                            <span className="block mt-1 text-zinc-600 not-italic">
                              No trade-level data available. Institutional accumulation and hidden orders are not inferred.
                            </span>
                          )}
                        </p>
                      </div>
                    </div>

                    {/* Invalidation */}
                    <div>
                      <p className="text-[10px] text-zinc-500 uppercase font-bold mb-1">Invalidation Conditions</p>
                      <ul className="space-y-0.5">
                        {(sig.invalidation_conditions as string[]).map((c, i) => (
                          <li key={i} className="text-[11px] text-amber-400/90 flex gap-2">
                            <span className="text-amber-600 shrink-0">✕</span>{c}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Fee Breakdown */}
                    {sig.fee_breakdown && (
                      <div className="p-3 bg-zinc-900/60 rounded border border-zinc-800 text-[11px] font-mono">
                        <p className="text-[10px] text-zinc-500 uppercase font-bold mb-2">Transaction Costs (Per Lot)</p>
                        <div className="grid grid-cols-3 gap-2 text-zinc-500">
                          <span>Brokerage: <span className="text-zinc-300">₹{(sig.fee_breakdown as Record<string, number>).brokerage}</span></span>
                          <span>STT: <span className="text-zinc-300">₹{(sig.fee_breakdown as Record<string, number>).stt}</span></span>
                          <span>Exch: <span className="text-zinc-300">₹{(sig.fee_breakdown as Record<string, number>).exchange_charges}</span></span>
                          <span>GST: <span className="text-zinc-300">₹{(sig.fee_breakdown as Record<string, number>).gst}</span></span>
                          <span>Stamp: <span className="text-zinc-300">₹{(sig.fee_breakdown as Record<string, number>).stamp_duty}</span></span>
                          <span className="font-bold">Total: <span className="text-zinc-200">₹{(sig.fee_breakdown as Record<string, number>).total_cost}</span></span>
                        </div>
                        <p className="text-zinc-600 mt-2">
                          Slippage est: {sig.slippage_pts as number} pts · Net return after all costs: {(((sig.net_expected_return_pct as number) ?? 0) * 100).toFixed(2)}%
                        </p>
                      </div>
                    )}

                    {/* Calibration footer */}
                    <div className="text-[11px] text-zinc-600 border-t border-zinc-800/60 pt-3 flex justify-between flex-wrap gap-2">
                      <span>
                        {sig.calibrated
                          ? `Calibrated model probability: ${(((sig as Record<string, unknown>).probability as number) * 100).toFixed(1)}%`
                          : `Uncalibrated rule score: ${sig.uncalibrated_score as number} — This is NOT a probability`}
                      </span>
                      <span className="font-mono">[{sig.data_mode as string}] · {sig.source_ts as string}</span>
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
