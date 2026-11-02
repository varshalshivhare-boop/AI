import { test, expect } from '@playwright/test';

test.describe('QuantMind Research Terminal Smoke Tests', () => {
  const pages = [
    { path: '/', title: 'Dashboard' },
    { path: '/analysis', title: 'Instrument Analysis' },
    { path: '/signals', title: 'Signal Intelligence' },
    { path: '/strategies', title: 'Strategy Lab' },
    { path: '/backtesting', title: 'Backtest Engine' },
    { path: '/paper-trading', title: 'Paper Trading' },
    { path: '/monitoring', title: 'System Telemetry' }
  ];

  for (const p of pages) {
    test(`renders ${p.title} page with DEMO data mode banner`, async ({ page }) => {
      await page.goto(`http://localhost:3000${p.path}`);
      // Banner check
      const banner = page.locator('text=DEMO DATA MODE');
      await expect(banner).toBeVisible();
    });
  }
});
