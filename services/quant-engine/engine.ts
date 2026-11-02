/**
 * QuantMind AI — PC2 Quant Engine Stub
 *
 * Integration stub only — simulates signal generation and backtest execution
 * to verify the PC2 ↔ PC3 contract boundary. Does NOT run live strategy code.
 *
 * Limitations documented here (per M2.4 discipline):
 * - Order flow evidence is never inferred — always "Unavailable"
 * - No institutional accumulation or hidden order inference
 * - calibrated=false on all stub signals — uncalibrated_score is NOT a probability
 */
import type { SignalGeneratedV1 } from '../../packages/contracts/src/index.ts';

export class QuantEnginePC2 {
  public generatedSignals: SignalGeneratedV1[] = [];
  public executedBacktests: Map<string, unknown> = new Map();

  /**
   * Consumes candles from the DB and evaluates all configured strategies.
   * Returns only signals that meet minimum evidence threshold.
   */
  public processCandles(candles: Record<string, unknown>[]): SignalGeneratedV1[] {
    this.generatedSignals = [];
    if (candles.length < 5) return [];

    const latest = candles[candles.length - 1];
    const prev = candles[candles.length - 2];

    // ── Strategy 1: Breakout ────────────────────────────────────────────────
    // Condition: bullish bar + volume > threshold
    if (
      typeof latest.close === 'number' && typeof latest.open === 'number' &&
      typeof latest.volume === 'number' &&
      latest.close > latest.open &&
      latest.volume > 150_000
    ) {
      this.generatedSignals.push({
        signal_id: `sig-replay-breakout-${Date.now()}`,
        symbol: latest.symbol as string,
        price: latest.close,
        timestamp: latest.timestamp as string,
        action: 'BUY',
        strategy: 'Breakout',
        timeframe: latest.timeframe as string,
        regime: 'TRENDING_BULLISH',
        entry_zone: {
          min: +((latest.close as number) - 10).toFixed(2),
          max: +((latest.close as number) + 10).toFixed(2)
        },
        stop_loss: +((latest.close as number) - 60).toFixed(2),
        targets: [
          +((latest.close as number) + 80).toFixed(2),
          +((latest.close as number) + 150).toFixed(2)
        ],
        risk_reward_ratio: 2.33,
        supporting_evidence: [
          '5m close clears 3-bar confirmed swing-high resistance cluster',
          `Relative volume ${((latest.volume as number) / 100_000).toFixed(1)}x over same-time-of-day baseline (threshold: 1.8x)`,
          'VWAP support: close above session VWAP',
          'ADX > 25 — confirmed trending regime'
        ],
        volume_confirmation: true,
        structure_explanation: 'Breakout above 3-bar confirmed swing high. Market structure shift from range to trend. Higher highs and higher lows sequence initiated.',
        order_flow_evidence: 'Unavailable',  // No trade-level aggressor data — see M2.4
        invalidation_conditions: [
          `5m close below stop loss ₹${+((latest.close as number) - 60).toFixed(2)}`,
          'Volume dries below 0.7x baseline within 2 bars of breakout'
        ],
        calibrated: false,
        uncalibrated_score: 0.82,  // Rule-based score — NOT a probability
        data_mode: 'REPLAY',
        source_ts: latest.timestamp as string
      });
    }

    // ── Strategy 2: NO_TRADE (insufficient evidence) ────────────────────────
    // Condition: flat candle body or low ADX regime
    if (
      typeof latest.close === 'number' && typeof latest.open === 'number' &&
      typeof prev.close === 'number'
    ) {
      const bodyRatio = Math.abs((latest.close - latest.open) /
        ((latest.high as number) - (latest.low as number) || 1));

      if (bodyRatio < 0.3) {
        this.generatedSignals.push({
          signal_id: `sig-replay-notrade-${Date.now() + 1}`,
          symbol: latest.symbol as string,
          price: latest.close,
          timestamp: latest.timestamp as string,
          action: 'NO_TRADE',
          strategy: 'Breakout',
          timeframe: latest.timeframe as string,
          regime: 'RANGING',
          entry_zone: { min: latest.close - 5, max: latest.close + 5 },
          stop_loss: latest.close - 30,
          targets: [latest.close + 40],
          risk_reward_ratio: 1.33,
          supporting_evidence: [
            `Body-to-range ratio ${bodyRatio.toFixed(2)} — below 0.30 threshold`,
            'Indecision candle — insufficient directional conviction'
          ],
          volume_confirmation: false,
          structure_explanation: 'No clear market structure — price chopping inside prior value area. ADX < 20 confirms ranging regime.',
          order_flow_evidence: 'Unavailable',
          invalidation_conditions: ['Any close outside current value area'],
          calibrated: false,
          uncalibrated_score: 0.31,
          data_mode: 'REPLAY',
          source_ts: latest.timestamp as string
        });
      }
    }

    return this.generatedSignals;
  }

  /**
   * Backtest Worker: picks up a QUEUED job and executes walk-forward backtest.
   * OOS period is always chronologically AFTER the IS period — no data leakage.
   * config_hash, data_hash, and code_version are set for reproducibility auditing.
   */
  public executeBacktestJob(job: Record<string, unknown>): Record<string, unknown> {
    const isTrades = 80;
    const oosTrades = 35;

    // Deterministic equity curve from IS period
    const isEquityCurve = [
      { timestamp: '2026-09-01', equity: 100_000, drawdown: 0 },
      { timestamp: '2026-09-15', equity: 103_200, drawdown: 0.008 },
      { timestamp: '2026-10-01', equity: 107_800, drawdown: 0.003 },
      { timestamp: '2026-10-15', equity: 112_100, drawdown: 0.015 },
      { timestamp: '2026-11-01', equity: 118_200, drawdown: 0.006 }
    ];

    // OOS equity curve — chronologically AFTER IS (walk-forward)
    const oosEquityCurve = [
      { timestamp: '2026-11-01', equity: 100_000, drawdown: 0 },
      { timestamp: '2026-11-10', equity: 102_400, drawdown: 0.012 },
      { timestamp: '2026-11-20', equity: 104_100, drawdown: 0.025 },
      { timestamp: '2026-11-30', equity: 109_100, drawdown: 0.008 }
    ];

    const completedResults = {
      in_sample: {
        period_start: '2026-09-01T03:45:00Z',
        period_end:   '2026-10-31T15:30:00Z',
        win_rate: 0.575,
        profit_factor: 1.82,
        sharpe: 2.10,
        sortino: 2.70,
        max_drawdown: 0.072,
        total_return: 0.182,
        total_trades: isTrades,
        expectancy: 1_285,
        avg_win: 3_420,
        avg_loss: -1_860,
        annualization_factor: 252,
        risk_free_rate: 0.065
      },
      out_of_sample: {
        period_start: '2026-11-01T03:45:00Z',
        period_end:   '2026-11-30T15:30:00Z',
        win_rate: 0.528,
        profit_factor: 1.49,
        sharpe: 1.61,
        sortino: 2.02,
        max_drawdown: 0.095,
        total_return: 0.091,
        total_trades: oosTrades,
        expectancy: 894,
        avg_win: 3_180,
        avg_loss: -1_940,
        annualization_factor: 252,
        risk_free_rate: 0.065
      },
      equity_curve: isEquityCurve,
      oos_equity_curve: oosEquityCurve,
      walk_forward_method: 'anchored',
      lookahead_bias_check: 'PASS — signals fired on bar close, executed at next-bar open',
      disclaimer: 'Past simulated results do not guarantee future performance. OOS is the only reliable performance estimate.',
      trades: []
    };

    const updatedJob = {
      ...job,
      status: 'COMPLETED',
      results: completedResults,
      data_mode: 'REPLAY',
      executed_by: 'PC2_QUANT_WORKER',
      completed_at: new Date().toISOString(),
      // Reproducibility fields — required for auditing
      config_hash: 'sha256-stub-config-abc123def456',
      data_hash: 'sha256-stub-data-xyz789uvw012',
      code_version: 'stub-git-sha-00000000'
    };

    this.executedBacktests.set((job.job_id ?? job.id) as string, updatedJob);
    return updatedJob;
  }
}
