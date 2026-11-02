'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, ColorType, LineStyle, CrosshairMode, type IChartApi, type ISeriesApi, type CandlestickData } from 'lightweight-charts';

interface ChartProps {
  candles: any[];
  symbol: string;
  height?: number;
}

export const CandlestickChart: React.FC<ChartProps> = ({ candles, symbol, height = 380 }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const vwapSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const emaSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;

    // Cleanup previous instance
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#09090b' },
        textColor: '#a1a1aa',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#18181b', style: LineStyle.Dashed },
        horzLines: { color: '#18181b', style: LineStyle.Dashed },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#3f3f46', labelBackgroundColor: '#18181b' },
        horzLine: { color: '#3f3f46', labelBackgroundColor: '#18181b' },
      },
      rightPriceScale: {
        borderColor: '#27272a',
        textColor: '#a1a1aa',
      },
      timeScale: {
        borderColor: '#27272a',
        timeVisible: true,
        secondsVisible: false,
      },
      width: containerRef.current.clientWidth,
      height,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    const vwapSeries = chart.addLineSeries({
      color: '#f59e0b',
      lineWidth: 2,
      title: 'VWAP',
      priceLineVisible: false,
    });

    const emaSeries = chart.addLineSeries({
      color: '#6366f1',
      lineWidth: 1,
      title: 'EMA9',
      priceLineVisible: false,
      lineStyle: LineStyle.Dashed,
    });

    // Map fixtures to chart data — timestamps from YYYY-MM-DDTHH:MM:SS.sssZ to unix seconds
    const candleData: CandlestickData[] = candles.map((c) => ({
      time: (new Date(c.timestamp).getTime() / 1000) as any,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    const vwapData = candles
      .filter((c) => c.vwap)
      .map((c) => ({ time: (new Date(c.timestamp).getTime() / 1000) as any, value: c.vwap }));

    const emaData = candles
      .filter((c) => c.ema9)
      .map((c) => ({ time: (new Date(c.timestamp).getTime() / 1000) as any, value: c.ema9 }));

    candleSeries.setData(candleData);
    vwapSeries.setData(vwapData);
    emaSeries.setData(emaData);

    chart.timeScale().fitContent();

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    vwapSeriesRef.current = vwapSeries;
    emaSeriesRef.current = emaSeries;

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [candles, height]);

  return (
    <div className="relative w-full" style={{ height }}>
      <div ref={containerRef} className="w-full h-full" />
      <div className="absolute top-2 right-2 flex items-center gap-3 text-[10px] font-mono pointer-events-none">
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-amber-400 inline-block"></span>VWAP</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-indigo-400 inline-block"></span>EMA9</span>
        <span className="flex items-center gap-1"><span className="w-3 h-1 bg-emerald-500 inline-block"></span>Bull</span>
        <span className="flex items-center gap-1"><span className="w-3 h-1 bg-red-500 inline-block"></span>Bear</span>
      </div>
    </div>
  );
};
