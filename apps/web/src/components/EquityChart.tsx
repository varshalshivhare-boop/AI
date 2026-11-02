'use client';

import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, LineStyle } from 'lightweight-charts';

interface EquityPoint { timestamp: string; equity: number; drawdown: number; }

interface EquityChartProps {
  inSample: EquityPoint[];
  outOfSample: EquityPoint[];
  height?: number;
}

export const EquityChart: React.FC<EquityChartProps> = ({ inSample, outOfSample, height = 260 }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || (inSample.length === 0 && outOfSample.length === 0)) return;

    const chart = createChart(ref.current, {
      layout: { background: { type: ColorType.Solid, color: '#09090b' }, textColor: '#a1a1aa', fontSize: 10, fontFamily: 'ui-monospace, monospace' },
      grid: { vertLines: { color: '#18181b' }, horzLines: { color: '#18181b' } },
      rightPriceScale: { borderColor: '#27272a' },
      timeScale: { borderColor: '#27272a', timeVisible: true },
      width: ref.current.clientWidth,
      height,
    });

    if (inSample.length > 0) {
      const is = chart.addLineSeries({ color: '#52525b', lineWidth: 1, title: 'In-Sample', lineStyle: LineStyle.Dashed });
      is.setData(inSample.map(p => ({ time: p.timestamp as any, value: p.equity })));
    }

    if (outOfSample.length > 0) {
      const oos = chart.addLineSeries({ color: '#3b82f6', lineWidth: 2, title: 'OOS (Headline)' });
      oos.setData(outOfSample.map(p => ({ time: p.timestamp as any, value: p.equity })));
    }

    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    });
    ro.observe(ref.current);

    return () => { ro.disconnect(); chart.remove(); };
  }, [inSample, outOfSample, height]);

  return <div ref={ref} className="w-full" style={{ height }} />;
};
