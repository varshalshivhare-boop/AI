'use client';

import React, { useState } from 'react';
import { usePolling } from '../../hooks/useApi';
import { SectionHeader, LoadingState, EmptyState, StatRow } from '../../components/ui';
import { Wallet, ShieldAlert, TrendingUp, TrendingDown } from 'lucide-react';

export default function PaperTradingPage() {
  const { data: account, loading: accLoading } = usePolling<any>('/paper-trading/positions', 4000);
  const { data: trades, loading: tradesLoading } = usePolling<any[]>('/paper-trading/trades', 6000);

  const openPositions = (trades || []).filter((t: any) => t.status === 'OPEN');
  const closedTrades = (trades || []).filter((t: any) => t.status === 'CLOSED');

  return (
    <div className="space-y-5 max-w-screen-xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div>
          <h1 className="text-base font-bold uppercase tracking-wider text-zinc-100 flex items-center gap-2">
            <Wallet className="w-4 h-4 text-emerald-400" aria-hidden /> Paper Trading Terminal
          </h1>
          <p className="text-[11px] text-zinc-500">
            Simulated execution with full brokerage, STT, GST, stamp duty, and slippage model. Session auto-close at 15:15 IST.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-500/10 border border-amber-500/30 rounded text-[11px] font-mono text-amber-400">
          <ShieldAlert className="w-3.5 h-3.5" aria-label="Paper trading warning" />
          STRICT PAPER EXECUTION — NO REAL BROKER
        </div>
      </div>

      {/* Capital Summary */}
      {accLoading && !account ? <LoadingState label="Loading account..." /> : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Virtual Capital', value: `₹${(account?.virtual_capital || 1000000).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, color: 'text-zinc-100' },
            { label: 'Available Margin', value: `₹${((account?.available_margin) || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, color: 'text-zinc-100' },
            { label: 'Realized P&L', value: `+₹${(account?.realized_pnl || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, color: 'text-emerald-400' },
            { label: 'Unrealized P&L', value: `+₹${(account?.unrealized_pnl || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, color: 'text-emerald-400' },
          ].map(({ label, value, color }) => (
            <div key={label} className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
              <span className="text-[10px] text-zinc-600 uppercase tracking-wider block mb-1">{label}</span>
              <span className={`text-lg font-bold font-mono tabular-nums ${color}`}>{value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Open Positions */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
        <div className="px-5 py-3 border-b border-zinc-800">
          <SectionHeader
            title="Open Paper Positions"
            subtitle={`${openPositions.length} open · Auto-square-off at 15:15 IST`}
            right={<span className="text-[10px] font-mono text-zinc-600">PAPER FLAG = TRUE on all rows</span>}
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono text-left" aria-label="Open paper positions">
            <thead className="bg-zinc-900/50 text-zinc-500">
              <tr>
                {['Symbol','Strategy','Action','Qty','Entry ₹','SL ₹','Target ₹','Unreal P&L','Slippage','Fees','Flag'].map(h => (
                  <th key={h} scope="col" className="py-2.5 px-3 text-right first:text-left">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-900">
              {tradesLoading && openPositions.length === 0 ? (
                <tr><td colSpan={11}><LoadingState /></td></tr>
              ) : openPositions.length === 0 ? (
                <tr><td colSpan={11}><EmptyState label="No open paper positions this session." /></td></tr>
              ) : openPositions.map((p: any) => (
                <tr key={p.id} className="hover:bg-zinc-900/30">
                  <td className="py-3 px-3 font-bold text-zinc-100">{p.symbol}</td>
                  <td className="py-3 px-3 text-zinc-400">{p.strategy}</td>
                  <td className="py-3 px-3">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${p.action === 'BUY' ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'}`}>
                      {p.action}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-right tabular-nums text-zinc-300">{p.quantity}</td>
                  <td className="py-3 px-3 text-right tabular-nums text-zinc-300">{p.entry_price?.toFixed(2)}</td>
                  <td className="py-3 px-3 text-right tabular-nums text-rose-400">{p.stop_loss?.toFixed(2)}</td>
                  <td className="py-3 px-3 text-right tabular-nums text-emerald-400">{p.target?.toFixed(2)}</td>
                  <td className={`py-3 px-3 text-right tabular-nums font-bold ${(p.unrealized_pnl || p.pnl) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    +₹{(p.unrealized_pnl || p.pnl)?.toFixed(2)}
                  </td>
                  <td className="py-3 px-3 text-right tabular-nums text-zinc-500">{p.slippage} pts</td>
                  <td className="py-3 px-3 text-right tabular-nums text-zinc-500">₹{p.brokerage_fees?.toFixed(2)}</td>
                  <td className="py-3 px-3 text-center">
                    <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] font-bold text-zinc-400">PAPER</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Closed Trades */}
      {closedTrades.length > 0 && (
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-800">
            <SectionHeader title="Closed Paper Trades" subtitle="Session history" />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono text-left" aria-label="Closed paper trades">
              <thead className="bg-zinc-900/50 text-zinc-500">
                <tr>
                  {['Symbol','Strategy','Action','Qty','Entry ₹','Exit ₹','P&L ₹','Net (after fees)','Flag'].map(h => (
                    <th key={h} scope="col" className="py-2.5 px-3 text-right first:text-left">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900">
                {closedTrades.map((t: any) => {
                  const netPnl = (t.pnl || 0) - (t.brokerage_fees || 0);
                  return (
                    <tr key={t.id} className="hover:bg-zinc-900/30">
                      <td className="py-2.5 px-3 font-bold text-zinc-100">{t.symbol}</td>
                      <td className="py-2.5 px-3 text-zinc-400">{t.strategy}</td>
                      <td className="py-2.5 px-3">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${t.action === 'BUY' ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'}`}>
                          {t.action}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-zinc-300">{t.quantity}</td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-zinc-300">{t.entry_price?.toFixed(2)}</td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-zinc-300">{t.exit_price?.toFixed(2)}</td>
                      <td className={`py-2.5 px-3 text-right tabular-nums font-bold ${t.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {t.pnl >= 0 ? '+' : ''}₹{t.pnl?.toFixed(2)}
                      </td>
                      <td className={`py-2.5 px-3 text-right tabular-nums ${netPnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                        {netPnl >= 0 ? '+' : ''}₹{netPnl.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] font-bold text-zinc-400">PAPER</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
