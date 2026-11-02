'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  LineChart,
  Radio,
  FlaskConical,
  History,
  Wallet,
  Activity
} from 'lucide-react';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/analysis', label: 'Instrument Analysis', icon: LineChart },
  { href: '/signals', label: 'Signal Intelligence', icon: Radio },
  { href: '/strategies', label: 'Strategy Lab', icon: FlaskConical },
  { href: '/backtesting', label: 'Backtest Engine', icon: History },
  { href: '/paper-trading', label: 'Paper Trading', icon: Wallet },
  { href: '/monitoring', label: 'System Telemetry', icon: Activity },
];

export const Navigation: React.FC = () => {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r border-zinc-800 bg-zinc-950 flex flex-col justify-between p-4">
      <div className="space-y-6">
        <div className="flex items-center gap-2 px-2">
          <div className="w-7 h-7 rounded bg-blue-600 flex items-center justify-center font-bold text-white text-sm">
            QM
          </div>
          <div>
            <h1 className="font-bold text-sm tracking-wider text-zinc-100 uppercase">QuantMind AI</h1>
            <p className="text-[10px] text-zinc-500 font-mono">NSE INTRADAY TERMINAL</p>
          </div>
        </div>

        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-zinc-800 text-blue-400 font-semibold'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-blue-400' : 'text-zinc-400'}`} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="p-3 bg-zinc-900/60 rounded-lg border border-zinc-800/80 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-zinc-400 uppercase font-mono">Gateway Status</span>
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
        </div>
        <p className="text-[11px] font-mono text-zinc-300">ws://localhost:4000</p>
        <div className="text-[10px] text-zinc-500 font-mono">Session: Paper/Demo</div>
      </div>
    </aside>
  );
};
