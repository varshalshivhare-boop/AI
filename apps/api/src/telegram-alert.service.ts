import type { SignalGeneratedV1 } from '../../../packages/contracts/src/index.ts';

export interface TelegramConfig {
  botToken: string;
  chatId: string;
}

export class TelegramAlertService {
  private config: TelegramConfig | null;
  private lastAlerts = new Map<string, number>();
  private readonly dedupWindowMs: number;

  constructor(
    config: TelegramConfig | null,
    dedupWindowMinutes = 15
  ) {
    this.config = config;
    this.dedupWindowMs = dedupWindowMinutes * 60 * 1000;
  }

  /**
   * Deduplication key per (symbol, strategy, timeframe, action)
   */
  private getDedupKey(signal: SignalGeneratedV1): string {
    return `${signal.symbol}:${signal.strategy}:${signal.timeframe}:${signal.action}`;
  }

  /**
   * Format message per Milestone 3.7 specification
   */
  public formatSignalMessage(signal: SignalGeneratedV1): string {
    const entryRange = `${signal.entry_zone.min.toFixed(2)} - ${signal.entry_zone.max.toFixed(2)}`;
    const targetsStr = signal.targets.map(t => t.toFixed(2)).join(', ');
    const invalidations = signal.invalidation_conditions.join('; ');

    return [
      `🚨 *QuantMind Research Signal* [${signal.data_mode}]`,
      `• *Symbol*: ${signal.symbol}`,
      `• *Action*: ${signal.action}`,
      `• *Price*: ${signal.price ? signal.price.toFixed(2) : 'N/A'}`,
      `• *Entry Zone*: ${entryRange}`,
      `• *Stop Loss*: ${signal.stop_loss.toFixed(2)}`,
      `• *Targets*: ${targetsStr}`,
      `• *Risk/Reward*: 1:${signal.risk_reward_ratio}`,
      `• *Timestamp*: ${signal.timestamp}`,
      `• *Invalidation*: ${invalidations}`,
      ``,
      `⚠️ _Research and paper-trading signal. Not investment advice._`
    ].join('\n');
  }

  /**
   * Send alert strictly enforcing:
   * 1. ONLY LIVE-mode data (NEVER DEMO or REPLAY)
   * 2. Fresh signals (not expired or stale)
   * 3. Deduplication window
   */
  public async sendAlert(signal: SignalGeneratedV1): Promise<{ sent: boolean; reason?: string }> {
    // RULE: Never send alerts for REPLAY or DEMO data
    if (signal.data_mode !== 'LIVE') {
      return {
        sent: false,
        reason: `Suppressed: Signal data_mode is '${signal.data_mode}'. Alerts strictly require LIVE mode.`
      };
    }

    // Check configuration
    if (!this.config || !this.config.botToken || !this.config.chatId) {
      return { sent: false, reason: 'Telegram Bot API token or chat ID not configured.' };
    }

    // Check expiration / staleness (> 5 minutes old)
    const signalTime = new Date(signal.timestamp).getTime();
    if (Date.now() - signalTime > 5 * 60 * 1000) {
      return { sent: false, reason: 'Signal is stale (> 5 minutes old). Alert suppressed.' };
    }

    // Deduplication check
    const dedupKey = this.getDedupKey(signal);
    const lastSent = this.lastAlerts.get(dedupKey);
    const now = Date.now();
    if (lastSent && now - lastSent < this.dedupWindowMs) {
      return { sent: false, reason: `Deduplicated: Identical alert sent within ${this.dedupWindowMs / 60000}m window.` };
    }

    // Update deduplication timestamp
    this.lastAlerts.set(dedupKey, now);

    const message = this.formatSignalMessage(signal);

    try {
      const response = await fetch(`https://api.telegram.org/bot${this.config.botToken}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: this.config.chatId,
          text: message,
          parse_mode: 'Markdown'
        })
      });

      if (!response.ok) {
        throw new Error(`Telegram API returned HTTP ${response.status}`);
      }

      return { sent: true };
    } catch (err: any) {
      return { sent: false, reason: `Telegram dispatch failed: ${err.message}` };
    }
  }
}
