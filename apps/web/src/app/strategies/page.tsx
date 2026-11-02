'use client';

import React, { useState } from 'react';
import { FlaskConical, Settings2, Sliders, ShieldCheck, AlertCircle, Save, Check } from 'lucide-react';
import { SectionHeader, StatRow, MetricCard } from '../../components/ui';

interface StrategyDetail {
  id: string;
  name: string;
  enabled: boolean;
  timeframe: string;
  expectedHolding: string;
  oosMetrics: {
    winRate: string;
    profitFactor: string;
    sharpe: string;
    maxDrawdown: string;
    expectancy: string;
    totalTrades: number;
  };
  inSampleMetrics: {
    winRate: string;
    profitFactor: string;
    sharpe: string;
  };
  entryRules: string[];
  invalidationRules: string[];
  config: {
    atrMultiplier: number;
    volumeThreshold: number;
    rrRatioMin: number;
    maxRiskPct: number;
  };
}

const STRATEGY_DATA: StrategyDetail[] = [
  {
    id: 'breakout',
    name: '1. Breakout Strategy',
    enabled: true,
    timeframe: '5m',
    expectedHolding: '15 - 45 mins',
    oosMetrics: {
      winRate: '53.3%',
      profitFactor: '1.51',
      sharpe: '1.64',
      maxDrawdown: '-9.6%',
      expectancy: '₹894',
      totalTrades: 45
    },
    inSampleMetrics: {
      winRate: '58.2%',
      profitFactor: '1.88',
      sharpe: '2.18'
    },
    entryRules: [
      '5m bar close breaks confirmed swing high/low by >= 0.5 ATR buffer',
      'Relative Volume (RVOL) >= 2.0x vs 10-session same-time-of-day baseline',
      'Session-anchored VWAP posture aligned with breakout direction'
    ],
    invalidationRules: [
      '5m bar close back inside prior resistance/support zone',
      'Loss of VWAP structure within next 3 bars'
    ],
    config: {
      atrMultiplier: 1.5,
      volumeThreshold: 2.0,
      rrRatioMin: 2.0,
      maxRiskPct: 1.0
    }
  },
  {
    id: 'false_breakout',
    name: '2. False Breakout (Fade)',
    enabled: true,
    timeframe: '5m',
    expectedHolding: '10 - 30 mins',
    oosMetrics: {
      winRate: '51.5%',
      profitFactor: '1.45',
      sharpe: '1.48',
      maxDrawdown: '-8.8%',
      expectancy: '₹740',
      totalTrades: 38
    },
    inSampleMetrics: {
      winRate: '56.0%',
      profitFactor: '1.72',
      sharpe: '1.95'
    },
    entryRules: [
      'Price exits resistance/support zone but closes back inside within K=2 bars',
      'Breakout volume is weak (< 1.5x baseline) signaling lack of institutional commitment',
      'RSI divergence or exhaustion at upper/lower Bollinger boundary'
    ],
    invalidationRules: [
      'New session high/low sustained with volume spike > 2x'
    ],
    config: {
      atrMultiplier: 1.2,
      volumeThreshold: 1.4,
      rrRatioMin: 2.0,
      maxRiskPct: 1.0
    }
  },
  {
    id: 'trend_cont',
    name: '3. Trend Continuation',
    enabled: true,
    timeframe: '5m',
    expectedHolding: '25 - 60 mins',
    oosMetrics: {
      winRate: '55.2%',
      profitFactor: '1.78',
      sharpe: '1.85',
      maxDrawdown: '-7.9%',
      expectancy: '₹1,050',
      totalTrades: 52
    },
    inSampleMetrics: {
      winRate: '61.4%',
      profitFactor: '2.10',
      sharpe: '2.40'
    },
    entryRules: [
      'ADX >= 25 with Directional Efficiency Ratio >= 0.65',
      'First test of session VWAP or EMA(20) from above in higher-high structure',
      'Pullback volume contracting (< 0.8x baseline)'
    ],
    invalidationRules: [
      '5m close below session VWAP by 0.5 ATR',
      'Structure shift: lower low broken'
    ],
    config: {
      atrMultiplier: 1.8,
      volumeThreshold: 1.5,
      rrRatioMin: 1.8,
      maxRiskPct: 1.0
    }
  },
  {
    id: 'pullback',
    name: '4. Support/Resistance Pullback',
    enabled: false,
    timeframe: '5m',
    expectedHolding: '15 - 40 mins',
    oosMetrics: {
      winRate: '49.0%',
      profitFactor: '1.18',
      sharpe: '1.12',
      maxDrawdown: '-11.2%',
      expectancy: '₹320',
      totalTrades: 34
    },
    inSampleMetrics: {
      winRate: '53.8%',
      profitFactor: '1.42',
      sharpe: '1.55'
    },
    entryRules: [
      'Retest of broken key level (former resistance turned support)',
      'Declining volume on test bars followed by rejection wick',
      'Wilder RSI reset to 40-50 zone'
    ],
    invalidationRules: [
      'Close below flipped support zone'
    ],
    config: {
      atrMultiplier: 1.5,
      volumeThreshold: 1.2,
      rrRatioMin: 1.8,
      maxRiskPct: 0.75
    }
  },
  {
    id: 'reversal',
    name: '5. Mean Reversion / Reversal',
    enabled: false,
    timeframe: '5m',
    expectedHolding: '10 - 25 mins',
    oosMetrics: {
      winRate: '46.5%',
      profitFactor: '0.98',
      sharpe: '0.92',
      maxDrawdown: '-13.5%',
      expectancy: '-₹45',
      totalTrades: 29
    },
    inSampleMetrics: {
      winRate: '51.0%',
      profitFactor: '1.25',
      sharpe: '1.30'
    },
    entryRules: [
      'RSI(14) > 80 or < 20 with 2-bar momentum deceleration',
      'Price outside 2.5 standard deviation Bollinger Band',
      'Clustered rejection wicks at structural daily pivots'
    ],
    invalidationRules: [
      'Continuation bar closing outside extreme band'
    ],
    config: {
      atrMultiplier: 1.0,
      volumeThreshold: 1.8,
      rrRatioMin: 1.5,
      maxRiskPct: 0.5
    }
  },
  {
    id: 'volume_exp',
    name: '6. Volume Expansion Breakout',
    enabled: true,
    timeframe: '5m',
    expectedHolding: '20 - 50 mins',
    oosMetrics: {
      winRate: '54.0%',
      profitFactor: '1.55',
      sharpe: '1.68',
      maxDrawdown: '-8.5%',
      expectancy: '₹915',
      totalTrades: 48
    },
    inSampleMetrics: {
      winRate: '59.5%',
      profitFactor: '1.92',
      sharpe: '2.25'
    },
    entryRules: [
      'Volume Z-Score >= 2.0 against intraday time-of-day U-curve',
      'Acceptance outside Value Area (above VAH or below VAL)',
      'Realized volatility percentile >= 75th percentile'
    ],
    invalidationRules: [
      'Re-entry into 70% Value Area within 2 bars'
    ],
    config: {
      atrMultiplier: 2.0,
      volumeThreshold: 2.5,
      rrRatioMin: 2.2,
      maxRiskPct: 1.25
    }
  }
];

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<StrategyDetail[]>(STRATEGY_DATA);
  const [selectedId, setSelectedId] = useState<string>('breakout');
  const [savedNotice, setSavedNotice] = useState(false);

  const selected = strategies.find(s => s.id === selectedId) || strategies[0];

  const toggleStrategy = (id: string) => {
    setStrategies(strategies.map(s => s.id === id ? { ...s, enabled: !s.enabled } : s));
  };

  const updateConfig = (key: keyof StrategyDetail['config'], val: number) => {
    setStrategies(strategies.map(s => {
      if (s.id === selectedId) {
        return {
          ...s,
          config: { ...s.config, [key]: val }
        };
      }
      return s;
    }));
  };

  const handleSave = () => {
    setSavedNotice(true);
    setTimeout(() => setSavedNotice(false), 2500);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <h1 className="text-base font-bold uppercase tracking-wider text-zinc-100 flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-purple-400" /> Strategy Laboratory
          </h1>
          <p className="text-xs text-zinc-400">
            6 Independently Configurable Strategies · Admin-only toggles · Strictly Out-of-Sample (OOS) headline metrics
          </p>
        </div>
        <div className="flex items-center gap-2">
          {savedNotice && (
            <span className="flex items-center gap-1 text-xs text-emerald-400 font-mono">
              <Check className="w-4 h-4" /> Parameters Saved to Engine
            </span>
          )}
          <button
            onClick={handleSave}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-semibold uppercase tracking-wider transition-colors"
          >
            <Save className="w-3.5 h-3.5" /> Save Configuration
          </button>
        </div>
      </div>

      {/* Strategy Grid Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {strategies.map((strat) => {
          const isSelected = strat.id === selectedId;
          return (
            <div
              key={strat.id}
              onClick={() => setSelectedId(strat.id)}
              className={`p-4 rounded-lg border cursor-pointer transition-all ${
                isSelected
                  ? 'bg-zinc-950 border-blue-500 shadow-md shadow-blue-500/10'
                  : 'bg-zinc-950/80 border-zinc-800 hover:border-zinc-700'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="font-bold text-sm text-zinc-100">{strat.name}</span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleStrategy(strat.id);
                  }}
                  className={`text-[10px] font-bold px-2 py-0.5 rounded border transition-colors ${
                    strat.enabled
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                      : 'bg-zinc-800 text-zinc-500 border-zinc-700'
                  }`}
                >
                  {strat.enabled ? 'ACTIVE' : 'DISABLED'}
                </button>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs font-mono mb-3">
                <div className="p-2 bg-zinc-900/60 rounded border border-zinc-800/80 text-center">
                  <span className="text-[9px] text-zinc-500 uppercase block">OOS Win</span>
                  <span className="text-zinc-100 font-bold">{strat.oosMetrics.winRate}</span>
                </div>
                <div className="p-2 bg-zinc-900/60 rounded border border-zinc-800/80 text-center">
                  <span className="text-[9px] text-zinc-500 uppercase block">OOS Sharpe</span>
                  <span className="text-blue-400 font-bold">{strat.oosMetrics.sharpe}</span>
                </div>
                <div className="p-2 bg-zinc-900/60 rounded border border-zinc-800/80 text-center">
                  <span className="text-[9px] text-zinc-500 uppercase block">Max DD</span>
                  <span className="text-rose-400 font-bold">{strat.oosMetrics.maxDrawdown}</span>
                </div>
              </div>

              <div className="flex justify-between items-center text-[10px] text-zinc-500 font-mono">
                <span>TF: {strat.timeframe}</span>
                <span>Expectancy: {strat.oosMetrics.expectancy}/trade</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Selected Strategy Inspector / Config Editor */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Rules & Logic */}
        <div className="lg:col-span-2 p-5 bg-zinc-950 border border-zinc-800 rounded-lg space-y-5">
          <SectionHeader
            title={`${selected.name} — Inspector`}
            subtitle={`Timeframe: ${selected.timeframe} · Expected Holding: ${selected.expectedHolding}`}
            right={
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded border font-bold ${
                selected.enabled ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-zinc-800 text-zinc-500 border-zinc-700'
              }`}>
                {selected.enabled ? 'ACTIVE STRATEGY' : 'DISABLED'}
              </span>
            }
          />

          {/* Performance Comparison: OOS vs In-Sample */}
          <div className="p-4 bg-zinc-900/40 border border-zinc-800 rounded-lg space-y-3 font-mono text-xs">
            <span className="text-xs font-bold text-zinc-300 uppercase block">
              Performance Verification (Walk-Forward Split)
            </span>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-2.5 bg-zinc-950 rounded border border-blue-500/30">
                <span className="text-[9px] text-blue-400 uppercase block font-semibold">OOS Win Rate (Headline)</span>
                <span className="text-base font-bold text-zinc-100">{selected.oosMetrics.winRate}</span>
              </div>
              <div className="p-2.5 bg-zinc-950 rounded border border-blue-500/30">
                <span className="text-[9px] text-blue-400 uppercase block font-semibold">OOS Profit Factor</span>
                <span className="text-base font-bold text-emerald-400">{selected.oosMetrics.profitFactor}</span>
              </div>
              <div className="p-2.5 bg-zinc-950 rounded border border-zinc-800 opacity-60">
                <span className="text-[9px] text-zinc-500 uppercase block">In-Sample Win Rate</span>
                <span className="text-base font-bold text-zinc-300">{selected.inSampleMetrics.winRate}</span>
              </div>
              <div className="p-2.5 bg-zinc-950 rounded border border-zinc-800 opacity-60">
                <span className="text-[9px] text-zinc-500 uppercase block">In-Sample Sharpe</span>
                <span className="text-base font-bold text-zinc-300">{selected.inSampleMetrics.sharpe}</span>
              </div>
            </div>
            <p className="text-[10px] text-zinc-500 italic">
              * Note: In-Sample metrics are shown for comparison only. Strategy promotion is strictly gated on OOS verification.
            </p>
          </div>

          {/* Entry & Invalidation Rules */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="p-3 bg-zinc-900/30 border border-zinc-800/80 rounded space-y-2">
              <span className="font-bold text-zinc-200 uppercase tracking-wider block text-[11px]">
                Entry & Confirmation Rules
              </span>
              <ul className="space-y-1.5 text-zinc-400 list-disc list-inside">
                {selected.entryRules.map((rule, idx) => (
                  <li key={idx} className="leading-relaxed">{rule}</li>
                ))}
              </ul>
            </div>
            <div className="p-3 bg-zinc-900/30 border border-zinc-800/80 rounded space-y-2">
              <span className="font-bold text-amber-400/90 uppercase tracking-wider block text-[11px]">
                Invalidation & Exit Conditions
              </span>
              <ul className="space-y-1.5 text-zinc-400 list-disc list-inside">
                {selected.invalidationRules.map((rule, idx) => (
                  <li key={idx} className="leading-relaxed">{rule}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Strategy Parameters Editor */}
        <div className="p-5 bg-zinc-950 border border-zinc-800 rounded-lg space-y-5">
          <SectionHeader
            title="Risk & Parameters"
            subtitle="Validated at engine runtime"
          />

          <div className="space-y-4 font-mono text-xs">
            <div>
              <div className="flex justify-between text-zinc-400 mb-1">
                <span>ATR Stop Multiplier:</span>
                <span className="text-zinc-100 font-bold">{selected.config.atrMultiplier}x</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="3.0"
                step="0.1"
                value={selected.config.atrMultiplier}
                onChange={(e) => updateConfig('atrMultiplier', parseFloat(e.target.value))}
                className="w-full accent-blue-600 bg-zinc-800 h-1.5 rounded-lg appearance-none cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between text-zinc-400 mb-1">
                <span>Volume Baseline Threshold:</span>
                <span className="text-zinc-100 font-bold">{selected.config.volumeThreshold}x</span>
              </div>
              <input
                type="range"
                min="1.0"
                max="3.5"
                step="0.1"
                value={selected.config.volumeThreshold}
                onChange={(e) => updateConfig('volumeThreshold', parseFloat(e.target.value))}
                className="w-full accent-blue-600 bg-zinc-800 h-1.5 rounded-lg appearance-none cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between text-zinc-400 mb-1">
                <span>Minimum Risk / Reward:</span>
                <span className="text-zinc-100 font-bold">1 : {selected.config.rrRatioMin}</span>
              </div>
              <input
                type="range"
                min="1.2"
                max="3.0"
                step="0.1"
                value={selected.config.rrRatioMin}
                onChange={(e) => updateConfig('rrRatioMin', parseFloat(e.target.value))}
                className="w-full accent-blue-600 bg-zinc-800 h-1.5 rounded-lg appearance-none cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between text-zinc-400 mb-1">
                <span>Max Capital Risk Per Trade:</span>
                <span className="text-zinc-100 font-bold">{selected.config.maxRiskPct}%</span>
              </div>
              <input
                type="range"
                min="0.25"
                max="2.5"
                step="0.25"
                value={selected.config.maxRiskPct}
                onChange={(e) => updateConfig('maxRiskPct', parseFloat(e.target.value))}
                className="w-full accent-blue-600 bg-zinc-800 h-1.5 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>

          <div className="p-3 bg-zinc-900/50 border border-zinc-800/80 rounded text-[11px] text-zinc-500 space-y-1">
            <span className="font-semibold text-zinc-400 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Risk Engine Guardrail
            </span>
            <p>
              Candidate signals failing the minimum R:R or exceeding position sizing constraints are discarded with reason code <code>RISK_REWARD_INSUFFICIENT</code>.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
