'use client';

import React, { useState, useCallback } from 'react';
import { useApi } from '../../hooks/useApi';
import { EquityChart } from '../../components/EquityChart';
import { MetricCard, SectionHeader, LoadingState } from '../../components/ui';
import { History, Play, CheckCircle2, Clock, AlertCircle, RefreshCw } from 'lucide-react';

const STATUS_ICONS: Record<string, React.ReactNode> = {
  QUEUED:    <Clock className="w-4 h-4 text-zinc-400" aria-label="Queued" />,
  RUNNING:   <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" aria-label="Running" />,
  COMPLETED: <CheckCircle2 className="w-4 h-4 text-emerald-400" aria-label="Completed" />,
  FAILED:    <AlertCircle  className="w-4 h-4 text-rose-400"    aria-label="Failed"    />,
};

const STATUS_LABEL_STYLES: Record<string, string> = {
  QUEUED:    'text-zinc-400',
  RUNNING:   'text-blue-400',
  COMPLETED: 'text-emerald-400',
  FAILED:    'text-rose-400',
};

function MetricsGrid({ label, data, headline }: { label: string; data: Record<string, unknown>; headline?: boolean }) {
  if (!data) return null;
  return (
    <div className={`p-5 rounded-lg border space-y-4 ${headline ? 'bg-zinc-950 border-blue-500/40' : 'bg-zinc-950 border-zinc-800 opacity-80'}`}>
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div>
          <p className={`text-xs font-bold uppercase tracking-wider ${headline ? 'text-blue-400' : 'text-zinc-500'}`}>
            {label}
          </p>
          <p className="text-[10px] text-zinc-600">
            {headline
              ? 'Use as headline performance metric'
              : 'For reference only — NOT headline metric. In-sample data is seen during training.'}
          </p>
          {data.period_start && (
            <p className="text-[10px] text-zinc-700 font-mono mt-0.5">
              Period: {String(data.period_start).slice(0,10)} → {String(data.period_end ?? '').slice(0,10)}
            </p>
          )}
        </div>
        <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
          headline
            ? 'bg-blue-500/10 text-blue-300 border-blue-500/30'
            : 'bg-zinc-800 text-zinc-500 border-zinc-700'
        }`}>
          {headline ? 'WALK-FORWARD OOS' : 'IN-SAMPLE'}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2.5">
        <MetricCard label="Win Rate"      value={`${((data.win_rate as number) * 100).toFixed(1)}%`}
          color={(data.win_rate as number) > 0.5 ? 'green' : 'red'} />
        <MetricCard label="Profit Factor" value={(data.profit_factor as number).toFixed(2)}
          color={(data.profit_factor as number) > 1.5 ? 'green' : 'amber'} />
        <MetricCard label="Sharpe"        value={(data.sharpe as number).toFixed(2)}
          color={(data.sharpe as number) > 1.5 ? 'blue' : 'default'}
          sub={`Annualized ${(data.annualization_factor as number) ?? 252}d`} />
        <MetricCard label="Sortino"       value={(data.sortino as number).toFixed(2)} />
        <MetricCard label="Max Drawdown"  value={`-${((data.max_drawdown as number) * 100).toFixed(1)}%`} color="red" />
        <MetricCard label="Total Return"  value={`${(data.total_return as number) >= 0 ? '+' : ''}${((data.total_return as number) * 100).toFixed(1)}%`}
          color={(data.total_return as number) >= 0 ? 'green' : 'red'} />
        <MetricCard label="Trades"        value={data.total_trades as number} />
        <MetricCard label="Expectancy"    value={`₹${(data.expectancy as number)?.toFixed(0) ?? '—'}`} color="default" sub="per trade" />
        <MetricCard label="Avg Win / Loss"
          value={`₹${(data.avg_win as number)?.toFixed(0) ?? '—'} / ₹${(data.avg_loss as number)?.toFixed(0) ?? '—'}`} />
      </div>
      {data.risk_free_rate && (
        <p className="text-[10px] text-zinc-600 font-mono">
          Sharpe/Sortino annualized at {data.annualization_factor as number} trading days.
          Risk-free rate: {((data.risk_free_rate as number) * 100).toFixed(1)}% p.a. (Indian T-bill proxy — not guaranteed).
        </p>
      )}
    </div>
  );
}

export default function BacktestingPage() {
  const [symbol,    setSymbol]    = useState('NIFTY50');
  const [strategy,  setStrategy]  = useState('Breakout');
  const [timeframe, setTimeframe] = useState('5m');
  const [startDate, setStartDate] = useState('2026-09-01');
  const [endDate,   setEndDate]   = useState('2026-11-01');
  const [jobId,     setJobId]     = useState<string | null>(null);
  const [running,   setRunning]   = useState(false);

  const { data: allJobs,  refetch: refetchJobs  } = useApi<Record<string, unknown>[]>('/backtests');
  const { data: job, loading: jobLoading }         = useApi<Record<string, unknown>>(
    jobId ? `/backtests/${jobId}` : '',
    [jobId]
  );

  const handleRun = useCallback(async () => {
    setRunning(true);
    setJobId(null);
    try {
      const res = await fetch('http://localhost:4000/backtests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          strategy,
          timeframe,
          start_date: new Date(startDate).toISOString(),
          end_date:   new Date(endDate).toISOString(),
          parameters: { atr_multiplier: 1.5, rr_min: 1.5, volume_threshold: 1.8 }
        })
      });
      const json = await res.json();
      setJobId(json.data.job_id);
      refetchJobs?.();
    } finally {
      setRunning(false);
    }
  }, [symbol, strategy, timeframe, startDate, endDate, refetchJobs]);

  const results = job?.results as Record<string, unknown> | undefined;

  return (
    <div className="space-y-5 max-w-screen-xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-4">
        <div>
          <h1 className="text-base font-bold uppercase tracking-wider text-zinc-100 flex items-center gap-2">
            <History className="w-4 h-4 text-blue-400" aria-hidden /> Backtesting Laboratory
          </h1>
          <p className="text-[11px] text-zinc-500">
            Event-driven · Signals fired on bar close · Execution at next-bar open ·
            Conservative same-bar stop resolution · Walk-forward OOS separation
          </p>
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          aria-busy={running}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded text-xs font-bold uppercase tracking-wider transition-colors"
        >
          <Play className="w-3.5 h-3.5 fill-current" aria-hidden />
          {running ? 'Queuing Job...' : 'Run Backtest'}
        </button>
      </div>

      {/* Configuration */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
        {[
          { label: 'Instrument', value: symbol,   options: ['NIFTY50','BANKNIFTY','RELIANCE','INFY','HDFCBANK'], set: setSymbol },
          { label: 'Strategy',   value: strategy,  options: ['Breakout','FalseBreakout','TrendContinuation','Pullback','Reversal','VolumeExpansion'], set: setStrategy },
          { label: 'Timeframe',  value: timeframe, options: ['1m','3m','5m','15m'], set: setTimeframe },
        ].map(({ label, value, options, set }) => (
          <div key={label}>
            <label className="text-[10px] text-zinc-600 uppercase block mb-1">{label}</label>
            <select
              value={value}
              onChange={e => set(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs font-mono px-2 py-1.5 rounded focus:outline-none focus:border-zinc-600"
            >
              {options.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
        ))}

        <div>
          <label className="text-[10px] text-zinc-600 uppercase block mb-1" htmlFor="bt-start">Start Date</label>
          <input
            id="bt-start"
            type="date"
            value={startDate}
            onChange={e => setStartDate(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs font-mono px-2 py-1.5 rounded focus:outline-none focus:border-zinc-600"
          />
        </div>
        <div>
          <label className="text-[10px] text-zinc-600 uppercase block mb-1" htmlFor="bt-end">End Date</label>
          <input
            id="bt-end"
            type="date"
            value={endDate}
            onChange={e => setEndDate(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs font-mono px-2 py-1.5 rounded focus:outline-none focus:border-zinc-600"
          />
        </div>
        <div>
          <label className="text-[10px] text-zinc-600 uppercase block mb-1">Execution Rule</label>
          <p className="text-[11px] text-zinc-500 font-mono pt-1.5">Next-Bar Open<br/>(No Look-Ahead)</p>
        </div>
      </div>

      {/* Active Job Status */}
      {jobId && (
        <div className="flex items-center gap-3 p-3 bg-zinc-950 border border-zinc-800 rounded-lg text-xs font-mono">
          {STATUS_ICONS[job?.status as string ?? 'QUEUED']}
          <span className="text-zinc-400">Job: <span className="text-zinc-200">{jobId}</span></span>
          <span className={STATUS_LABEL_STYLES[job?.status as string ?? 'QUEUED'] ?? 'text-zinc-400'}>
            {job?.status ?? 'QUEUED'}
          </span>
          {job?.config_hash && (
            <span className="text-zinc-700 font-mono text-[10px]" title="Configuration hash for reproducibility">
              config: {String(job.config_hash).slice(0, 16)}…
            </span>
          )}
          {job?.data_hash && (
            <span className="text-zinc-700 font-mono text-[10px]" title="Data hash for reproducibility">
              data: {String(job.data_hash).slice(0, 16)}…
            </span>
          )}
          {job?.code_version && (
            <span className="text-zinc-700 font-mono text-[10px]" title="Code version (git SHA)">
              ver: {String(job.code_version).slice(0, 12)}
            </span>
          )}
        </div>
      )}

      {/* Results */}
      {results ? (
        <div className="space-y-5">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <MetricsGrid label="Out-Of-Sample (Headline)" data={results.out_of_sample as Record<string, unknown>} headline />
            <MetricsGrid label="In-Sample (Training Reference)" data={results.in_sample as Record<string, unknown>} />
          </div>

          {/* Walk-forward disclaimer */}
          <div className="p-3 bg-amber-500/5 border border-amber-500/20 rounded-lg text-[11px] text-amber-400/80 font-mono">
            ⚠ In-sample equity may appear smoother due to curve-fitting. The Out-Of-Sample curve (blue) is the
            only reliable performance estimate. Do NOT use in-sample metrics to claim strategy profitability.
            {(results.lookahead_bias_check) && (
              <span className="ml-2 text-emerald-400">Look-ahead bias check: {results.lookahead_bias_check as string}</span>
            )}
          </div>

          {/* Equity Curves */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-5 space-y-4">
            <SectionHeader
              title="Walk-Forward Equity Curves"
              subtitle="Blue = OOS Headline (chronologically after IS) · Grey dashed = In-Sample"
            />
            <EquityChart
              inSample={results.equity_curve as { timestamp: string; equity: number; drawdown: number }[] ?? []}
              outOfSample={results.oos_equity_curve as { timestamp: string; equity: number; drawdown: number }[] ?? []}
              height={260}
            />
          </div>

          {/* Trade Table */}
          {Array.isArray(results.trades) && (results.trades as unknown[]).length > 0 && (
            <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
              <div className="px-5 py-3 border-b border-zinc-800">
                <SectionHeader title="Simulated Trade Log" subtitle="Paper execution · All trades labelled PAPER — no real-money execution" />
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono text-left">
                  <thead className="bg-zinc-900/50 text-zinc-500">
                    <tr>
                      {['#', 'Symbol', 'Action', 'Entry ₹', 'Exit ₹', 'Qty', 'P&L ₹', 'Duration (bars)'].map(h => (
                        <th key={h} scope="col" className="py-2 px-3">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-900">
                    {(results.trades as Record<string, unknown>[]).map((t, i) => (
                      <tr key={i} className="hover:bg-zinc-900/30">
                        <td className="py-2 px-3 text-zinc-600">{i + 1}</td>
                        <td className="py-2 px-3 text-zinc-100 font-bold">{t.symbol as string}</td>
                        <td className="py-2 px-3">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            t.action === 'BUY'
                              ? 'bg-emerald-500/10 text-emerald-400'
                              : 'bg-rose-500/10 text-rose-400'
                          }`}>
                            {t.action as string}
                          </span>
                        </td>
                        <td className="py-2 px-3 tabular-nums text-zinc-300">{(t.entry_price as number)?.toFixed(2)}</td>
                        <td className="py-2 px-3 tabular-nums text-zinc-300">{(t.exit_price  as number)?.toFixed(2)}</td>
                        <td className="py-2 px-3 tabular-nums text-zinc-400">{t.quantity as number}</td>
                        <td className={`py-2 px-3 tabular-nums font-bold ${(t.pnl as number) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {(t.pnl as number) >= 0 ? '+' : ''}{(t.pnl as number)?.toFixed(2)}
                        </td>
                        <td className="py-2 px-3 text-zinc-500">{t.duration_bars as number}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : jobId && jobLoading ? (
        <LoadingState label="Fetching backtest results..." />
      ) : null}

      {/* Job History */}
      {allJobs && allJobs.length > 0 && (
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-800 flex items-center justify-between">
            <SectionHeader title="Backtest Job History" subtitle="All submitted jobs this session" />
            <button
              onClick={() => refetchJobs?.()}
              className="text-zinc-500 hover:text-zinc-300 transition-colors"
              aria-label="Refresh job list"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono text-left">
              <thead className="bg-zinc-900/50 text-zinc-500">
                <tr>
                  {['Job ID', 'Symbol', 'Strategy', 'TF', 'Status', 'OOS Sharpe', 'Config Hash'].map(h => (
                    <th key={h} scope="col" className="py-2 px-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900">
                {allJobs.map((j) => {
                  const jr = j.results as Record<string, unknown> | undefined;
                  return (
                    <tr
                      key={j.job_id as string}
                      className={`hover:bg-zinc-900/30 cursor-pointer ${jobId === j.job_id ? 'bg-blue-500/5' : ''}`}
                      onClick={() => setJobId(j.job_id as string)}
                    >
                      <td className="py-2 px-3 text-zinc-400">{String(j.job_id).slice(0, 14)}…</td>
                      <td className="py-2 px-3 text-zinc-100 font-bold">{j.symbol as string}</td>
                      <td className="py-2 px-3 text-zinc-300">{j.strategy as string}</td>
                      <td className="py-2 px-3 text-zinc-500">{j.timeframe as string}</td>
                      <td className="py-2 px-3">
                        <span className={`flex items-center gap-1 ${STATUS_LABEL_STYLES[j.status as string] ?? 'text-zinc-400'}`}>
                          {STATUS_ICONS[j.status as string]}
                          {j.status as string}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-blue-300">
                        {jr?.out_of_sample
                          ? (jr.out_of_sample as Record<string, number>).sharpe?.toFixed(2)
                          : '—'}
                      </td>
                      <td className="py-2 px-3 text-zinc-700 text-[10px]">
                        {j.config_hash ? String(j.config_hash).slice(0, 14) + '…' : '—'}
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
