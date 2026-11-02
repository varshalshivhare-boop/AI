'use client';

import React from 'react';
import { AlertTriangle } from 'lucide-react';

interface BannerProps {
  dataMode?: 'LIVE' | 'REPLAY' | 'DEMO';
}

export const DataModeBanner: React.FC<BannerProps> = ({ dataMode = 'DEMO' }) => {
  if (dataMode === 'LIVE') return null;

  return (
    <div className="w-full bg-amber-500/10 border-b border-amber-500/30 px-4 py-1.5 flex items-center justify-between text-xs text-amber-400">
      <div className="flex items-center gap-2 font-mono">
        <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
        <span className="font-semibold uppercase tracking-wider">
          [{dataMode} DATA MODE]
        </span>
        <span className="text-zinc-400">
          Terminal is running against mock fixtures / replay. NO real-money broker execution.
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
          DEMO ENGINE
        </span>
        <span className="text-zinc-500 text-[11px]">Latency: ~1.2ms</span>
      </div>
    </div>
  );
};
