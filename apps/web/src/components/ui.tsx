'use client';

import React from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  sub?: string;
  color?: 'default' | 'green' | 'red' | 'blue' | 'amber';
}

const COLOR_MAP: Record<string, string> = {
  default: 'text-zinc-100',
  green: 'text-emerald-400',
  red: 'text-rose-400',
  blue: 'text-blue-400',
  amber: 'text-amber-400',
};

export const MetricCard: React.FC<MetricCardProps> = ({ label, value, sub, color = 'default' }) => (
  <div className="p-3 bg-zinc-900/60 rounded border border-zinc-800/80 space-y-1">
    <span className="text-[10px] text-zinc-500 block uppercase tracking-wider font-mono">{label}</span>
    <span className={`text-lg font-bold font-mono ${COLOR_MAP[color]}`}>{value}</span>
    {sub && <p className="text-[10px] text-zinc-600 font-mono">{sub}</p>}
  </div>
);

interface SignalBadgeProps {
  action: 'BUY' | 'SELL' | 'NO_TRADE';
  size?: 'sm' | 'md';
}

const ACTION_STYLES: Record<string, string> = {
  BUY: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40',
  SELL: 'bg-rose-500/15 text-rose-400 border-rose-500/40',
  NO_TRADE: 'bg-zinc-800 text-zinc-500 border-zinc-700',
};

export const SignalBadge: React.FC<SignalBadgeProps> = ({ action, size = 'sm' }) => (
  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border font-bold uppercase ${
    size === 'md' ? 'text-xs' : 'text-[10px]'
  } ${ACTION_STYLES[action]}`}>
    {action === 'BUY' && <span aria-label="BUY direction">▲</span>}
    {action === 'SELL' && <span aria-label="SELL direction">▼</span>}
    {action === 'NO_TRADE' && <span aria-label="NO_TRADE hold">—</span>}
    <span>{action}</span>
  </span>
);

interface RegimeBadgeProps { regime: string; }

export const RegimeBadge: React.FC<RegimeBadgeProps> = ({ regime }) => {
  const color = regime.includes('TRENDING')
    ? 'text-blue-400 bg-blue-500/10 border-blue-500/30'
    : regime === 'UNCERTAIN'
    ? 'text-amber-400 bg-amber-500/10 border-amber-500/30'
    : 'text-zinc-400 bg-zinc-800 border-zinc-700';
  return (
    <span className={`text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded border ${color}`}>
      {regime}
    </span>
  );
};

interface StatRowProps { label: string; value: string | number; className?: string; }

export const StatRow: React.FC<StatRowProps> = ({ label, value, className = '' }) => (
  <div className={`flex justify-between items-center py-1.5 border-b border-zinc-900 last:border-0 ${className}`}>
    <span className="text-[11px] text-zinc-500 font-mono">{label}</span>
    <span className="text-[11px] text-zinc-200 font-mono font-medium">{value}</span>
  </div>
);

export const SectionHeader: React.FC<{ title: string; subtitle?: string; right?: React.ReactNode }> = ({
  title, subtitle, right
}) => (
  <div className="flex items-center justify-between border-b border-zinc-800 pb-3 mb-4">
    <div>
      <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-200">{title}</h2>
      {subtitle && <p className="text-[11px] text-zinc-500 mt-0.5">{subtitle}</p>}
    </div>
    {right && <div>{right}</div>}
  </div>
);

export const LoadingState: React.FC<{ label?: string }> = ({ label = 'Loading...' }) => (
  <div className="flex flex-col items-center justify-center py-12 text-zinc-600 space-y-2">
    <div className="w-6 h-6 border-2 border-zinc-700 border-t-blue-500 rounded-full animate-spin"></div>
    <span className="text-xs font-mono">{label}</span>
  </div>
);

export const EmptyState: React.FC<{ label?: string }> = ({ label = 'No data available' }) => (
  <div className="flex items-center justify-center py-10 text-zinc-600 text-xs font-mono">
    {label}
  </div>
);

export const ErrorState: React.FC<{ message?: string }> = ({ message }) => (
  <div className="flex items-center justify-center py-10 text-rose-500 text-xs font-mono">
    Error: {message || 'Failed to load data from mock server'}
  </div>
);
