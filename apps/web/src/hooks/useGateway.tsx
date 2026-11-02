'use client';

import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:4000/gateway';

interface GatewayMessage {
  type: string;
  data?: any;
  timestamp?: string;
  data_mode?: string;
  banner?: string;
}

interface GatewayContextValue {
  connected: boolean;
  lastMessage: GatewayMessage | null;
  lastTick: any | null;
  dataMode: string;
  subscribe: (symbol: string, timeframe?: string) => void;
}

const GatewayContext = createContext<GatewayContextValue>({
  connected: false,
  lastMessage: null,
  lastTick: null,
  dataMode: 'DEMO',
  subscribe: () => {},
});

export const GatewayProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<GatewayMessage | null>(null);
  const [lastTick, setLastTick] = useState<any | null>(null);
  const [dataMode, setDataMode] = useState('DEMO');
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => { setConnected(true); };
      ws.onmessage = (event) => {
        try {
          const msg: GatewayMessage = JSON.parse(event.data);
          setLastMessage(msg);
          if (msg.data_mode) setDataMode(msg.data_mode);
          if (msg.type === 'CANDLE_UPDATE') setLastTick(msg.data);
        } catch { /* malformed WS message — discard */ }
      };
      ws.onclose = () => {
        setConnected(false);
        reconnectTimer.current = setTimeout(connect, 3000);
      };
      ws.onerror = () => { ws.close(); };
    } catch {
      reconnectTimer.current = setTimeout(connect, 3000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const subscribe = useCallback((symbol: string, timeframe = '5m') => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'SUBSCRIBE', symbol, timeframe }));
    }
  }, []);

  return (
    <GatewayContext.Provider value={{ connected, lastMessage, lastTick, dataMode, subscribe }}>
      {children}
    </GatewayContext.Provider>
  );
};

export const useGateway = () => useContext(GatewayContext);
