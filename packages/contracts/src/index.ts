/* eslint-disable */
/**
 * AUTO-GENERATED from /packages/contracts/schemas
 * Run `npm run generate` in packages/contracts to regenerate.
 * DO NOT EDIT MANUALLY.
 */

export type DataMode = 'LIVE' | 'REPLAY' | 'DEMO';

export type SignalAction = 'BUY' | 'SELL' | 'NO_TRADE';

export interface EntryZone {
  min: number;
  max: number;
}

export interface SignalGeneratedV1 {
  signal_id: string;
  symbol: string;
  price?: number;
  timestamp: string;
  action: SignalAction;
  strategy: string;
  timeframe: string;
  regime: string;
  entry_zone: EntryZone;
  stop_loss: number;
  targets: number[];
  risk_reward_ratio: number;
  supporting_evidence: string[];
  volume_confirmation: boolean;
  structure_explanation: string;
  order_flow_evidence?: string;
  invalidation_conditions: string[];
  calibrated: boolean;
  probability?: number;
  uncalibrated_score?: number;
  data_mode: DataMode;
  source_ts?: string;
}

export interface CandleV1 {
  symbol: string;
  timeframe: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap?: number;
  data_mode: DataMode;
}

export type BacktestStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';

export interface BacktestPerformanceMetrics {
  win_rate: number;
  profit_factor: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  total_return: number;
  total_trades: number;
}

export interface EquityCurvePoint {
  timestamp: string;
  equity: number;
  drawdown: number;
}

export interface BacktestJobV1 {
  job_id: string;
  symbol: string;
  strategy: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  parameters: Record<string, unknown>;
  status: BacktestStatus;
  data_mode: DataMode;
  results?: {
    in_sample: BacktestPerformanceMetrics;
    out_of_sample: BacktestPerformanceMetrics;
    equity_curve: EquityCurvePoint[];
    trades: Array<Record<string, unknown>>;
  };
}

export interface ProviderHealthV1 {
  provider: string;
  status: 'HEALTHY' | 'DEGRADED' | 'DOWN';
  timestamp: string;
  latency_ms: number;
  last_tick_age_seconds?: number;
  failed_calculations?: number;
  redis_status?: string;
  db_status?: string;
  data_mode: DataMode;
}

export interface ApiResponseEnvelope<T> {
  data: T;
  data_mode: DataMode;
  source_ts: string;
  ingest_ts: string;
  request_id: string;
}
