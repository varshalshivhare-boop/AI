import React from 'react';
import './globals.css';
import { DataModeBanner } from '../components/DataModeBanner';
import { Navigation } from '../components/Navigation';

export const metadata = {
  title: 'QuantMind AI — NSE Intraday Research Terminal',
  description: 'Explainable Quant Strategy Intelligence. Paper-trading only. No real-money execution.'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark h-full bg-zinc-950 text-zinc-100">
      <body className="h-full flex flex-col font-mono antialiased overflow-hidden">
        <DataModeBanner dataMode="DEMO" />
        <div className="flex-1 flex overflow-hidden">
          <Navigation />
          <main className="flex-1 overflow-y-auto bg-zinc-900/20">
            <div className="p-5 h-full">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
