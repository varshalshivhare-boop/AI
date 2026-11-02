'use client';

import React from 'react';
import { usePolling } from '../../hooks/useApi';
import { SectionHeader, StatRow, LoadingState } from '../../components/ui';
import { Activity, Server, Database, Radio, Wifi } from 'lucide-react';

export default function MonitoringPage() {
  const { data: health } = usePolling<any>('/health', 2000);
  const { data: telemetry } = usePolling<any>('/system/monitoring', 2000);

  const statusColor = (s: string) => {
    if (!s) return 'text-zinc-500';
    const up = s === 'HEALTHY' || s === 'OPTIMAL' || s === 'CONNECTED' || s === 'MOCK_READY';
    return up ? 'text-emerald-400' : 'text-rose-400';
  };

  return (
    <div className="space-y-5 max-w-screen-xl mx-auto">
      <div className="border-b border-zinc-800 pb-4">
        <h1 className="text-base font-bold uppercase tracking-wider text-zinc-100 flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" aria-hidden /> System Telemetry
        </h1>
        <p className="text-[11px] text-zinc-500">Feed health, WebSocket clients, Redis consumer group lag, dead-letter queue depth — refreshes every 2s</p>
      </div>

      {!telemetry ? <LoadingState label="Collecting telemetry..." /> : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* API Gateway */}
          <div className="p-5 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase text-zinc-300 flex items-center gap-2">
                <Server className="w-4 h-4 text-blue-400" aria-hidden /> NestJS API
              </span>
              <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${statusColor(telemetry.api_health)} bg-emerald-500/5 border border-emerald-500/20`}>
                {telemetry.api_health}
              </span>
            </div>
            <StatRow label="API Uptime" value={`${telemetry.api_uptime_seconds}s`} />
            <StatRow label="WebSocket Clients" value={telemetry.websocket_clients} />
            <StatRow label="Pipeline Latency" value={`${telemetry.pipeline_latency_ms} ms`} />
            <StatRow label="Dead Letter Queue" value={`${telemetry.dead_letter_count} msgs`} />
            <StatRow label="Failed Calculations" value={telemetry.failed_calculations} />
          </div>

          {/* Redis Streams */}
          <div className="p-5 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase text-zinc-300 flex items-center gap-2">
                <Database className="w-4 h-4 text-purple-400" aria-hidden /> Redis Streams
              </span>
              <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${statusColor(telemetry.redis_status)} bg-emerald-500/5 border border-emerald-500/20`}>
                {telemetry.redis_status}
              </span>
            </div>
            <StatRow label="DB Status" value={telemetry.db_status} />
            <StatRow label="Last Tick Age" value={`${telemetry.last_tick_age_ms} ms`} />
            {telemetry.candleStreams && Object.entries(telemetry.candleStreams).map(([k, v]: [string, any]) => (
              <StatRow key={k} label={k} value={String(v)} />
            ))}
            {telemetry.signalStreams && Object.entries(telemetry.signalStreams).map(([k, v]: [string, any]) => (
              <StatRow key={k} label={k} value={String(v)} />
            ))}
          </div>

          {/* Quant Engine */}
          <div className="p-5 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase text-zinc-300 flex items-center gap-2">
                <Radio className="w-4 h-4 text-amber-400" aria-hidden /> Quant Engine (PC 2)
              </span>
              <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded text-blue-400 bg-blue-500/5 border border-blue-500/20">
                DEMO MODE
              </span>
            </div>
            <StatRow label="Data Mode" value={telemetry.data_mode} />
            <StatRow label="Feed" value="Fixture Replay (No Live Broker)" />
            <div className="p-2 bg-amber-500/5 border border-amber-500/20 rounded text-[10px] text-amber-400/90 mt-2">
              This pane shows mock data. Switch NEXT_PUBLIC_API_URL to real quant-engine endpoint for live telemetry.
            </div>
          </div>

          {/* Provider Health */}
          {health && (
            <div className="p-5 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3 md:col-span-3">
              <SectionHeader title="Provider Health" subtitle="From /health endpoint" />
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px] font-mono">
                <div className="p-3 bg-zinc-900 rounded border border-zinc-800">
                  <span className="text-zinc-600 block text-[9px] uppercase mb-0.5">Provider</span>
                  <span className="text-zinc-200">{health.provider}</span>
                </div>
                <div className="p-3 bg-zinc-900 rounded border border-zinc-800">
                  <span className="text-zinc-600 block text-[9px] uppercase mb-0.5">Status</span>
                  <span className={statusColor(health.status)}>{health.status}</span>
                </div>
                <div className="p-3 bg-zinc-900 rounded border border-zinc-800">
                  <span className="text-zinc-600 block text-[9px] uppercase mb-0.5">Latency</span>
                  <span className="text-zinc-200">{health.latency_ms} ms</span>
                </div>
                <div className="p-3 bg-zinc-900 rounded border border-zinc-800">
                  <span className="text-zinc-600 block text-[9px] uppercase mb-0.5">Last Tick Age</span>
                  <span className="text-zinc-200">{health.last_tick_age_seconds}s</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
