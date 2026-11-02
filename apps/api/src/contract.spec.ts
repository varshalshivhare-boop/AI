import fs from 'fs';
import path from 'path';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { TelegramAlertService } from '../src/telegram-alert.service';
import { SignalGeneratedV1 } from '@quantmind/contracts';

describe('QuantMind Phase 3 Contract & Verification Tests', () => {
  const ajv = new Ajv({ strict: false });
  addFormats(ajv);

  const schemasDir = path.resolve(__dirname, '../../../packages/contracts/schemas');
  const fixturesDir = path.resolve(__dirname, '../../../fixtures');

  const signalSchema = JSON.parse(fs.readFileSync(path.join(schemasDir, 'signal.generated.v1.json'), 'utf-8'));
  const candleSchema = JSON.parse(fs.readFileSync(path.join(schemasDir, 'candle.v1.json'), 'utf-8'));
  const backtestSchema = JSON.parse(fs.readFileSync(path.join(schemasDir, 'backtest_job.v1.json'), 'utf-8'));

  const validateSignal = ajv.compile(signalSchema);
  const validateCandle = ajv.compile(candleSchema);
  const validateBacktest = ajv.compile(backtestSchema);

  it('validates all fixture candles against CandleV1 schema', () => {
    const candles = JSON.parse(fs.readFileSync(path.join(fixturesDir, 'candles_nifty50_demo.json'), 'utf-8'));
    expect(candles.length).toBeGreaterThan(0);
    for (const candle of candles) {
      const valid = validateCandle(candle);
      if (!valid) {
        console.error(validateCandle.errors);
      }
      expect(valid).toBe(true);
    }
  });

  it('validates all fixture signals against SignalGeneratedV1 schema', () => {
    const signals = JSON.parse(fs.readFileSync(path.join(fixturesDir, 'signals_demo.json'), 'utf-8'));
    expect(signals.length).toBeGreaterThan(0);
    for (const signal of signals) {
      const valid = validateSignal(signal);
      if (!valid) {
        console.error(validateSignal.errors);
      }
      expect(valid).toBe(true);
    }
  });

  describe('Telegram Alert Guardrails', () => {
    const mockTelegram = new TelegramAlertService({ botToken: 'mock-bot', chatId: 'mock-chat' });

    it('STRICTLY rejects DEMO signals from Telegram alert triggers', async () => {
      const demoSignal: SignalGeneratedV1 = {
        signal_id: 'test-demo',
        symbol: 'NIFTY50',
        timestamp: new Date().toISOString(),
        action: 'BUY',
        strategy: 'Breakout',
        timeframe: '5m',
        regime: 'TRENDING',
        entry_zone: { min: 24300, max: 24320 },
        stop_loss: 24250,
        targets: [24400],
        risk_reward_ratio: 2.0,
        supporting_evidence: ['Test'],
        volume_confirmation: true,
        structure_explanation: 'Testing',
        invalidation_conditions: ['Break below 24250'],
        calibrated: false,
        data_mode: 'DEMO'
      };

      const result = await mockTelegram.sendAlert(demoSignal);
      expect(result.sent).toBe(false);
      expect(result.reason).toContain("strictly require LIVE mode");
    });

    it('STRICTLY rejects REPLAY signals from Telegram alert triggers', async () => {
      const replaySignal: SignalGeneratedV1 = {
        signal_id: 'test-replay',
        symbol: 'NIFTY50',
        timestamp: new Date().toISOString(),
        action: 'BUY',
        strategy: 'Breakout',
        timeframe: '5m',
        regime: 'TRENDING',
        entry_zone: { min: 24300, max: 24320 },
        stop_loss: 24250,
        targets: [24400],
        risk_reward_ratio: 2.0,
        supporting_evidence: ['Test'],
        volume_confirmation: true,
        structure_explanation: 'Testing',
        invalidation_conditions: ['Break below 24250'],
        calibrated: false,
        data_mode: 'REPLAY'
      };

      const result = await mockTelegram.sendAlert(replaySignal);
      expect(result.sent).toBe(false);
      expect(result.reason).toContain("strictly require LIVE mode");
    });
  });
});
