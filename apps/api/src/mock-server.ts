import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = Number(process.env.PORT) || 4000;
const DATA_MODE = 'DEMO';

// ── Fixtures ──────────────────────────────────────────────────────────────────
const fixturesDir = path.resolve(__dirname, '../../../fixtures');

const candlesFixture: any[] = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, 'candles_nifty50_demo.json'), 'utf-8')
);
const signalsFixture: any[] = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, 'signals_demo.json'), 'utf-8')
);

// Banknifty candles — generated from nifty with ~2.15x multiplier for realism
const bankNiftyCandles: any[] = candlesFixture.map((c) => ({
  ...c,
  symbol: 'BANKNIFTY',
  open: +(c.open * 2.168).toFixed(2),
  high: +(c.high * 2.168).toFixed(2),
  low: +(c.low * 2.168).toFixed(2),
  close: +(c.close * 2.168).toFixed(2),
  vwap: +(c.vwap * 2.168).toFixed(2),
  volume: Math.round(c.volume * 0.62),
  sma20: +(c.sma20 * 2.168).toFixed(2),
  ema9: +(c.ema9 * 2.168).toFixed(2),
  rsi14: +(c.rsi14 - 2 + Math.random() * 3).toFixed(1),
  atr14: +(c.atr14 * 4.8).toFixed(2),
  adx: +(c.adx - 1 + Math.random() * 2).toFixed(1),
  macd: +(c.macd * 5.2).toFixed(2),
  bb_upper: +(c.bb_upper * 2.168).toFixed(2),
  bb_lower: +(c.bb_lower * 2.168).toFixed(2),
}));

// ── Request ID Generator ──────────────────────────────────────────────────────
function newRequestId(): string {
  return 'rq-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 7);
}

// ── Alert History (in-memory dedup + persistence stub) ────────────────────────
interface AlertRecord {
  alert_id: string;
  signal_id: string;
  symbol: string;
  action: string;
  data_mode: string;
  sent: boolean;
  reason?: string;
  created_at: string;
  status: 'GENERATED' | 'DELIVERED' | 'SUPPRESSED' | 'EXPIRED';
}
const alertHistory: AlertRecord[] = [];

// ── In-memory State ───────────────────────────────────────────────────────────
const mockPaperTrades: any[] = [
  {
    id: 'pt-001',
    user_id: 'usr-demo-1',
    symbol: 'NIFTY50',
    strategy: 'Breakout',
    timeframe: '5m',
    action: 'BUY',
    quantity: 50,
    entry_price: 24360.50,
    exit_price: null,
    stop_loss: 24295.00,
    target: 24440.00,
    pnl: 2611.50,
    unrealized_pnl: 2611.50,
    slippage: 1.5,
    brokerage_fees: 47.82,
    status: 'OPEN',
    paper_flag: true,
    entry_time: new Date(Date.now() - 65 * 60 * 1000).toISOString()
  },
  {
    id: 'pt-002',
    user_id: 'usr-demo-1',
    symbol: 'RELIANCE',
    strategy: 'TrendContinuation',
    timeframe: '5m',
    action: 'BUY',
    quantity: 250,
    entry_price: 2948.75,
    exit_price: 2984.50,
    stop_loss: 2918.00,
    target: 2985.00,
    pnl: 8937.50,
    unrealized_pnl: 0,
    slippage: 0.5,
    brokerage_fees: 31.67,
    status: 'CLOSED',
    paper_flag: true,
    entry_time: new Date(Date.now() - 90 * 60 * 1000).toISOString(),
    exit_time: new Date(Date.now() - 20 * 60 * 1000).toISOString()
  }
];

const mockBacktestJobs = new Map<string, any>();

// Walk-forward equity curve with realistic daily P&L series
function generateEquityCurve(capital: number, trades: number, winRate: number): any[] {
  const points = [];
  let equity = capital;
  let peak = capital;
  const startDate = new Date('2026-10-01');

  for (let i = 0; i < trades; i++) {
    const date = new Date(startDate);
    date.setDate(startDate.getDate() + Math.floor(i * 22 / trades));
    const won = Math.random() < winRate;
    const pct = won ? (Math.random() * 0.012 + 0.003) : -(Math.random() * 0.007 + 0.002);
    equity = equity * (1 + pct);
    if (equity > peak) peak = equity;
    const drawdown = peak > 0 ? (peak - equity) / peak : 0;
    points.push({
      timestamp: date.toISOString().split('T')[0],
      equity: +equity.toFixed(2),
      drawdown: +drawdown.toFixed(4)
    });
  }
  return points;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function wrapEnvelope<T>(data: T, requestId?: string) {
  const now = new Date().toISOString();
  return {
    data,
    data_mode: DATA_MODE,
    source_ts: now,
    ingest_ts: now,
    request_id: requestId ?? newRequestId()
  };
}

function errorResponse(code: string, message: string, status: number, requestId: string) {
  return { error: { code, message }, data_mode: DATA_MODE, request_id: requestId, status };
}

function readBody(req: http.IncomingMessage): Promise<any> {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => { resolve(body ? JSON.parse(body) : {}); });
  });
}

// Live price ticker — simulates price drift for NIFTY50
let lastPrice = 24512.50;
function getTickPrice(): number {
  const drift = (Math.random() - 0.48) * 4.5;
  lastPrice = +(lastPrice + drift).toFixed(2);
  return lastPrice;
}

// ── HTTP Server ───────────────────────────────────────────────────────────────
const server = http.createServer(async (req, res) => {
  const requestId = newRequestId();
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-request-id');
  res.setHeader('X-Request-ID', requestId);
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  const url = new URL(req.url || '/', `http://localhost:${PORT}`);
  const { pathname } = url;
  res.setHeader('Content-Type', 'application/json');

  try {
    // ── GET /health ────────────────────────────────────────────────────────
    if (pathname === '/health' && req.method === 'GET') {
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope({
        provider: 'QuantMindMockEngine v2',
        status: 'HEALTHY',
        timestamp: new Date().toISOString(),
        latency_ms: +(Math.random() * 0.8 + 0.6).toFixed(2),
        last_tick_age_seconds: +(Math.random() * 0.8 + 0.1).toFixed(2),
        failed_calculations: 0,
        redis_status: 'MOCK_READY',
        db_status: 'MOCK_READY',
        data_mode: DATA_MODE
      })));
      return;
    }

    // ── POST /auth/login ────────────────────────────────────────────────────
    if (pathname === '/auth/login' && req.method === 'POST') {
      const body = await readBody(req);
      // Basic mock auth: any credentials accepted in demo mode
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope({
        access_token: 'mock-jwt-access-demo',
        refresh_token: 'mock-jwt-refresh-demo',
        user: { id: 'usr-demo-1', email: body.email || 'trader@quantmind.ai', role: 'ADMIN' }
      })));
      return;
    }

    // ── POST /auth/refresh ──────────────────────────────────────────────────
    if (pathname === '/auth/refresh' && req.method === 'POST') {
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope({
        access_token: 'mock-jwt-access-refreshed-demo',
        refresh_token: 'mock-jwt-refresh-demo'
      })));
      return;
    }

    // ── GET /instruments ────────────────────────────────────────────────────
    if (pathname === '/instruments' && req.method === 'GET') {
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope([
        { symbol: 'NIFTY50',   name: 'Nifty 50 Index',        exchange: 'NSE', tick_size: 0.05, lot_size: 25,  segment: 'INDEX', is_active: true },
        { symbol: 'BANKNIFTY', name: 'Bank Nifty Index',       exchange: 'NSE', tick_size: 0.05, lot_size: 15,  segment: 'INDEX', is_active: true },
        { symbol: 'RELIANCE',  name: 'Reliance Industries Ltd', exchange: 'NSE', tick_size: 0.05, lot_size: 250, segment: 'EQ',    is_active: true },
        { symbol: 'INFY',      name: 'Infosys Ltd',             exchange: 'NSE', tick_size: 0.05, lot_size: 300, segment: 'EQ',    is_active: true },
        { symbol: 'HDFCBANK',  name: 'HDFC Bank Ltd',           exchange: 'NSE', tick_size: 0.05, lot_size: 550, segment: 'EQ',    is_active: true }
      ])));
      return;
    }

    // ── GET /candles ────────────────────────────────────────────────────────
    if (pathname === '/candles' && req.method === 'GET') {
      const symbol = url.searchParams.get('symbol') || 'NIFTY50';
      const limitParam = url.searchParams.get('limit');
      const limit = limitParam ? parseInt(limitParam) : 50;

      let candles = symbol === 'BANKNIFTY' ? bankNiftyCandles : candlesFixture;
      candles = candles.slice(-limit);
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope(candles)));
      return;
    }

    // ── GET /ticker/:symbol ─────────────────────────────────────────────────
    if (pathname.startsWith('/ticker/') && req.method === 'GET') {
      const symbol = pathname.replace('/ticker/', '');
      const tick = getTickPrice();
      const mult = symbol === 'BANKNIFTY' ? 2.168 : symbol === 'RELIANCE' ? 0.121 : 1;
      const price = +(tick * mult).toFixed(2);
      const prevClose = +(price * (1 - (Math.random() - 0.5) * 0.004)).toFixed(2);
      const change = +(price - prevClose).toFixed(2);
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope({
        symbol,
        ltp: price,
        prev_close: prevClose,
        change,
        change_pct: +((change / prevClose) * 100).toFixed(3),
        volume: Math.round(50000 + Math.random() * 200000),
        timestamp: new Date().toISOString(),
        data_mode: DATA_MODE
      })));
      return;
    }

    // ── GET /market/watchlist ───────────────────────────────────────────────
    if (pathname === '/market/watchlist' && req.method === 'GET') {
      const baseNifty = getTickPrice();
      const items = [
        { symbol: 'NIFTY50',   ltp: baseNifty,                  change_pct: +((Math.random()-0.3)*0.8).toFixed(3), rsi14: 80.1, rvol: 2.4, vwap: 24459.40, adx: 35.9, signal: 'BUY',      strategy: 'VolumeExpansion', regime: 'TRENDING' },
        { symbol: 'BANKNIFTY', ltp: +(baseNifty*2.168).toFixed(2), change_pct: +((Math.random()-0.4)*1.1).toFixed(3), rsi14: 68.4, rvol: 0.88, vwap: 52460.00, adx: 28.2, signal: 'NO_TRADE',  strategy: 'Pullback',       regime: 'UNCERTAIN' },
        { symbol: 'RELIANCE',  ltp: +(baseNifty*0.121).toFixed(2), change_pct: +((Math.random()-0.35)*0.6).toFixed(3), rsi14: 73.1, rvol: 1.55, vwap: 2944.80,  adx: 28.4, signal: 'BUY',      strategy: 'TrendCont',      regime: 'TRENDING' },
        { symbol: 'INFY',      ltp: +(1885+Math.random()*8).toFixed(2), change_pct: +((Math.random()-0.45)*0.5).toFixed(3), rsi14: 58.2, rvol: 0.72, vwap: 1880.20,  adx: 19.5, signal: 'NO_TRADE',  strategy: 'None',           regime: 'RANGING'  },
        { symbol: 'HDFCBANK',  ltp: +(1612+Math.random()*6).toFixed(2), change_pct: +((Math.random()-0.48)*0.7).toFixed(3), rsi14: 61.5, rvol: 1.12, vwap: 1608.50,  adx: 22.1, signal: 'NO_TRADE',  strategy: 'None',           regime: 'RANGING'  },
      ];
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope(items)));
      return;
    }

    // ── GET /signals ────────────────────────────────────────────────────────
    if (pathname === '/signals' && req.method === 'GET') {
      const symbol = url.searchParams.get('symbol');
      const action = url.searchParams.get('action');
      let sigs = signalsFixture;
      if (symbol) sigs = sigs.filter((s: any) => s.symbol === symbol);
      if (action) sigs = sigs.filter((s: any) => s.action === action);
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope(sigs)));
      return;
    }

    // ── GET /regime ─────────────────────────────────────────────────────────
    if (pathname === '/regime' && req.method === 'GET') {
      const symbol = url.searchParams.get('symbol') || 'NIFTY50';
      const regimes: Record<string, any> = {
        NIFTY50:   { symbol: 'NIFTY50',   regime: 'TRENDING_BULLISH', adx: 35.9, adx_threshold: 25, directional_efficiency: 0.81, volatility_pct: 82, vol_regime: 'HIGH', pressure: 'BUYING', confident: true },
        BANKNIFTY: { symbol: 'BANKNIFTY', regime: 'UNCERTAIN',        adx: 28.2, adx_threshold: 25, directional_efficiency: 0.51, volatility_pct: 55, vol_regime: 'NORMAL', pressure: 'NEUTRAL', confident: false },
        RELIANCE:  { symbol: 'RELIANCE',  regime: 'TRENDING_BULLISH', adx: 28.4, adx_threshold: 25, directional_efficiency: 0.72, volatility_pct: 68, vol_regime: 'NORMAL', pressure: 'BUYING', confident: true },
      };
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope(regimes[symbol] || regimes['NIFTY50'])));
      return;
    }

    // ── POST /backtests ─────────────────────────────────────────────────────
    if (pathname === '/backtests' && req.method === 'POST') {
      const body = await readBody(req);
      const jobId = 'bt-' + Date.now().toString(36);
      const isTradeCount = 120;
      const job = {
        job_id: jobId,
        symbol: body.symbol || 'NIFTY50',
        strategy: body.strategy || 'Breakout',
        timeframe: body.timeframe || '5m',
        start_date: body.start_date || '2026-09-01T03:45:00.000Z',
        end_date: body.end_date || '2026-11-02T10:00:00.000Z',
        parameters: body.parameters || { atr_multiplier: 1.5, rr_min: 1.5, volume_threshold: 1.8 },
        status: 'COMPLETED',
        data_mode: DATA_MODE,
        results: {
          in_sample: {
            win_rate: 0.582, profit_factor: 1.88, sharpe: 2.18,
            sortino: 2.82, max_drawdown: 0.071, total_return: 0.196, total_trades: isTradeCount,
            expectancy: 1285, avg_win: 3420, avg_loss: -1860,
            annualization_factor: 252, risk_free_rate: 0.065
          },
          out_of_sample: {
            win_rate: 0.533, profit_factor: 1.51, sharpe: 1.64,
            sortino: 2.08, max_drawdown: 0.096, total_return: 0.094, total_trades: 45,
            expectancy: 894, avg_win: 3180, avg_loss: -1940,
            annualization_factor: 252, risk_free_rate: 0.065
          },
          equity_curve: generateEquityCurve(100000, isTradeCount, 0.56),
          oos_equity_curve: generateEquityCurve(100000, 45, 0.52),
          trades: mockPaperTrades.map((t, i) => ({
            trade_id: `sim-${i+1}`,
            symbol: t.symbol,
            action: t.action,
            entry_price: t.entry_price,
            exit_price: t.exit_price || t.entry_price * 1.003,
            quantity: t.quantity,
            pnl: t.pnl,
            duration_bars: Math.round(Math.random() * 8 + 2)
          }))
        },
        config_hash: 'sha256-demo-config-abc123',
        data_hash: 'sha256-demo-data-xyz789',
        code_version: 'demo-git-sha-00000000'
      };
      mockBacktestJobs.set(jobId, job);
      res.writeHead(201);
      res.end(JSON.stringify(wrapEnvelope({ job_id: jobId, status: 'QUEUED' })));
      return;
    }

    // ── GET /backtests ──────────────────────────────────────────────────────
    if (pathname === '/backtests' && req.method === 'GET') {
      const jobs = Array.from(mockBacktestJobs.values());
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope(jobs)));
      return;
    }

    // ── GET /backtests/:id ──────────────────────────────────────────────────
    if (pathname.startsWith('/backtests/') && req.method === 'GET') {
      const jobId = pathname.replace('/backtests/', '');
      const job = mockBacktestJobs.get(jobId) || {
        job_id: jobId, symbol: 'NIFTY50', strategy: 'Breakout', timeframe: '5m',
        status: 'COMPLETED', data_mode: DATA_MODE,
        results: {
          in_sample: { win_rate: 0.582, profit_factor: 1.88, sharpe: 2.18, sortino: 2.82, max_drawdown: 0.071, total_return: 0.196, total_trades: 120, expectancy: 1285 },
          out_of_sample: { win_rate: 0.533, profit_factor: 1.51, sharpe: 1.64, sortino: 2.08, max_drawdown: 0.096, total_return: 0.094, total_trades: 45, expectancy: 894 },
          equity_curve: generateEquityCurve(100000, 120, 0.56),
          oos_equity_curve: generateEquityCurve(100000, 45, 0.52),
          trades: []
        }
      };
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope(job)));
      return;
    }

    // ── GET /paper-trading/positions ────────────────────────────────────────
    if (pathname === '/paper-trading/positions' && req.method === 'GET') {
      const openPositions = mockPaperTrades.filter(t => t.status === 'OPEN');
      const realizedPnL = mockPaperTrades.filter(t => t.status === 'CLOSED').reduce((acc, t) => acc + t.pnl, 0);
      const unrealizedPnL = openPositions.reduce((acc, t) => acc + (t.unrealized_pnl || 0), 0);
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope({
        virtual_capital: 1000000.0,
        used_margin: openPositions.reduce((acc, t) => acc + t.entry_price * t.quantity, 0),
        available_margin: 1000000.0 - openPositions.reduce((acc, t) => acc + t.entry_price * t.quantity, 0),
        realized_pnl: +realizedPnL.toFixed(2),
        unrealized_pnl: +unrealizedPnL.toFixed(2),
        total_pnl: +(realizedPnL + unrealizedPnL).toFixed(2),
        positions: openPositions,
        is_paper: true,
        session_trades_count: mockPaperTrades.length
      })));
      return;
    }

    // ── GET /paper-trading/trades ────────────────────────────────────────────
    if (pathname === '/paper-trading/trades' && req.method === 'GET') {
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope(mockPaperTrades, requestId)));
      return;
    }

    // ── POST /paper-trading/orders ──────────────────────────────────────────
    if (pathname === '/paper-trading/orders' && req.method === 'POST') {
      const body = await readBody(req);
      const requiredFields = ['symbol', 'action', 'quantity', 'order_type'];
      const missing = requiredFields.filter(f => !body[f]);
      if (missing.length > 0) {
        res.writeHead(400);
        res.end(JSON.stringify({ ...errorResponse('VALIDATION_ERROR', `Missing required fields: ${missing.join(', ')}`, 400, requestId) }));
        return;
      }
      if (!['BUY', 'SELL'].includes(body.action)) {
        res.writeHead(400);
        res.end(JSON.stringify({ ...errorResponse('VALIDATION_ERROR', 'action must be BUY or SELL', 400, requestId) }));
        return;
      }

      const entryPrice = getTickPrice();
      const newTrade = {
        id: 'pt-' + Date.now().toString(36),
        user_id: 'usr-demo-1',
        symbol: body.symbol,
        strategy: body.strategy || 'Manual',
        timeframe: body.timeframe || '5m',
        action: body.action,
        quantity: Number(body.quantity),
        entry_price: entryPrice,
        exit_price: null,
        stop_loss: body.stop_loss || +(entryPrice * 0.997).toFixed(2),
        target: body.target || +(entryPrice * 1.006).toFixed(2),
        pnl: 0,
        unrealized_pnl: 0,
        slippage: 0.5,
        brokerage_fees: +(Number(body.quantity) * entryPrice * 0.0003).toFixed(2),
        status: 'OPEN',
        paper_flag: true, // ALWAYS paper — no real execution
        entry_time: new Date().toISOString()
      };
      mockPaperTrades.push(newTrade);
      res.writeHead(201);
      res.end(JSON.stringify(wrapEnvelope({ order_id: newTrade.id, status: 'ACCEPTED', paper: true, trade: newTrade }, requestId)));
      return;
    }

    // ── GET /strategies ─────────────────────────────────────────────────────
    if (pathname === '/strategies' && req.method === 'GET') {
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope([
        {
          id: 'breakout', name: 'Breakout', version: '2.1.0', enabled: true,
          description: 'Breakout above confirmed swing high structure with volume expansion (≥1.8× relative volume baseline).',
          parameters: { atr_multiplier: 1.5, rr_min: 1.5, volume_threshold: 1.8, lookback_bars: 5 },
          oos_metrics: { sharpe: 1.64, win_rate: 0.533, profit_factor: 1.51, max_drawdown: 0.096, total_trades: 45 },
          is_metrics: { sharpe: 2.18, win_rate: 0.582, profit_factor: 1.88, max_drawdown: 0.071, total_trades: 120 },
          disclaimer: 'OOS metrics are headline. IS shown for reference only. Not a guarantee of future performance.'
        },
        {
          id: 'false-breakout', name: 'FalseBreakout', version: '2.1.0', enabled: true,
          description: 'Price exits zone and closes back inside within K bars — fade the move.',
          parameters: { reversal_bars: 3, atr_multiplier: 1.2, rr_min: 1.3, volume_threshold: 1.5 },
          oos_metrics: { sharpe: 1.41, win_rate: 0.512, profit_factor: 1.39, max_drawdown: 0.112, total_trades: 38 },
          is_metrics: { sharpe: 1.95, win_rate: 0.56, profit_factor: 1.72, max_drawdown: 0.088, total_trades: 98 },
          disclaimer: 'OOS metrics are headline. IS shown for reference only.'
        },
        {
          id: 'trend-continuation', name: 'TrendContinuation', version: '2.1.0', enabled: true,
          description: 'Pullback to VWAP in trending regime (ADX > 25), continuation entry on resumption.',
          parameters: { adx_threshold: 25, vwap_distance_pct: 0.2, rr_min: 2.0 },
          oos_metrics: { sharpe: 1.55, win_rate: 0.548, profit_factor: 1.60, max_drawdown: 0.083, total_trades: 52 },
          is_metrics: { sharpe: 2.08, win_rate: 0.601, profit_factor: 1.94, max_drawdown: 0.062, total_trades: 135 },
          disclaimer: 'OOS metrics are headline. IS shown for reference only.'
        },
        {
          id: 'pullback', name: 'Pullback', version: '2.1.0', enabled: false,
          description: 'Higher-timeframe trend pullback to ATR-defined support zone.',
          parameters: { htf_timeframe: '15m', atr_multiplier: 1.8, rr_min: 1.5 },
          oos_metrics: { sharpe: 1.22, win_rate: 0.494, profit_factor: 1.28, max_drawdown: 0.134, total_trades: 29 },
          is_metrics: { sharpe: 1.74, win_rate: 0.541, profit_factor: 1.65, max_drawdown: 0.095, total_trades: 78 },
          disclaimer: 'OOS metrics are headline. IS shown for reference only.'
        },
        {
          id: 'reversal', name: 'Reversal', version: '2.1.0', enabled: false,
          description: 'RSI divergence + structure shift at key S/R zone.',
          parameters: { rsi_divergence_bars: 10, rr_min: 1.8, zone_atr_width: 0.5 },
          oos_metrics: { sharpe: 1.08, win_rate: 0.482, profit_factor: 1.19, max_drawdown: 0.152, total_trades: 22 },
          is_metrics: { sharpe: 1.58, win_rate: 0.528, profit_factor: 1.58, max_drawdown: 0.108, total_trades: 61 },
          disclaimer: 'OOS metrics are headline. IS shown for reference only.'
        },
        {
          id: 'volume-expansion', name: 'VolumeExpansion', version: '2.1.0', enabled: true,
          description: 'Volume spike (z-score > 2.5) coinciding with price breakout from value area.',
          parameters: { volume_zscore: 2.5, rr_min: 1.5, poc_distance_pct: 0.3 },
          oos_metrics: { sharpe: 1.71, win_rate: 0.557, profit_factor: 1.68, max_drawdown: 0.078, total_trades: 41 },
          is_metrics: { sharpe: 2.24, win_rate: 0.608, profit_factor: 2.01, max_drawdown: 0.059, total_trades: 109 },
          disclaimer: 'OOS metrics are headline. IS shown for reference only.'
        }
      ], requestId)));
      return;
    }

    // ── GET /alerts ─────────────────────────────────────────────────────────
    if (pathname === '/alerts' && req.method === 'GET') {
      const limitParam = url.searchParams.get('limit');
      const limit = limitParam ? parseInt(limitParam) : 20;
      const page = parseInt(url.searchParams.get('page') ?? '1');
      const offset = (page - 1) * limit;
      const sliced = alertHistory.slice(offset, offset + limit);
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope({
        items: sliced,
        total: alertHistory.length,
        page,
        limit,
        has_more: offset + limit < alertHistory.length
      }, requestId)));
      return;
    }

    // ── GET /system/monitoring ──────────────────────────────────────────────
    if (pathname === '/system/monitoring' && req.method === 'GET') {
      res.writeHead(200);
      res.end(JSON.stringify(wrapEnvelope({
        api_uptime_seconds: Math.round(process.uptime()),
        websocket_clients: Math.floor(Math.random() * 3) + 1,
        last_tick_age_ms: Math.round(Math.random() * 150 + 50),
        pipeline_latency_ms: +(Math.random() * 8 + 10).toFixed(2),
        failed_calculations: 0,
        dead_letter_count: 0,
        redis_status: 'MOCK_READY',
        db_status: 'MOCK_READY',
        api_health: 'OPTIMAL',
        data_mode: DATA_MODE,
        candleStreams: { 'candles.closed.NIFTY50.5m': 'ACTIVE', 'candles.closed.BANKNIFTY.5m': 'ACTIVE' },
        signalStreams: { 'signals.generated': 'ACTIVE' }
      })));
      return;
    }

    // ── 404 Fallback ─────────────────────────────────────────────────────────
    res.writeHead(404);
    res.end(JSON.stringify({
      error: { code: 'NOT_FOUND', message: `Endpoint not found: ${req.method} ${pathname}` },
      data_mode: DATA_MODE,
      request_id: requestId
    }));

  } catch (err: any) {
    console.error(`[QuantMind Mock] Error on ${req.method} ${pathname}:`, err.message);
    res.writeHead(500);
    res.end(JSON.stringify({
      error: { code: 'INTERNAL_ERROR', message: 'Internal mock server error' },
      details: err.message,
      data_mode: DATA_MODE,
      request_id: requestId
    }));
  }
});

server.listen(PORT, () => {
  console.log(`\n[QuantMind Mock Engine v2]`);
  console.log(`  HTTP : http://localhost:${PORT}`);
  console.log(`  Mode : STRICT DEMO — fixture-served, no broker connections\n`);
});

export { server, wrapEnvelope };
