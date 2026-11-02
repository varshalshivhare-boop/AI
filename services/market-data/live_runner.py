import asyncio
import os
import json
import logging
from datetime import datetime
import aiohttp
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("live_engine")

load_dotenv("quantmind-ai/.env")

UPSTOX_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ALERTS_ENABLED", "true").lower() == "true"

# Top liquid NSE watchlist mapping (Symbol -> Instrument Key)
WATCHLIST = {
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "Nifty Bank": "NSE_INDEX|Nifty Bank",
    "RELIANCE": "NSE_EQ|INE002A01018",
    "HDFCBANK": "NSE_EQ|INE040A01034",
    "INFY": "NSE_EQ|INE009A01021",
    "TCS": "NSE_EQ|INE467B01029",
    "ICICIBANK": "NSE_EQ|INE090A01021",
    "SBIN": "NSE_EQ|INE062A01020",
    "BHARTIARTL": "NSE_EQ|INE397D01024",
    "ITC": "NSE_EQ|INE154A01025",
    "LT": "NSE_EQ|INE018A01030",
    "AXISBANK": "NSE_EQ|INE238A01034",
    "MARUTI": "NSE_EQ|INE585B01010",
    "TATAMOTORS": "NSE_EQ|INE155A01022",
    "BAJFINANCE": "NSE_EQ|INE296A01024"
}

# Reverse mapping: key in response e.g. "NSE_EQ:RELIANCE" -> friendly symbol "RELIANCE"
def get_friendly_symbol(response_key: str) -> str:
    parts = response_key.split(":")
    if len(parts) == 2:
        return parts[1]
    return response_key

# In-memory history for technical calculation
price_history = {}
last_alert_time = {}

async def send_telegram_alert(symbol: str, action: str, price: float, reason: str):
    if not TELEGRAM_ENABLED or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    # Simple alert dedup (15 min cooldown per symbol)
    now = datetime.now()
    if symbol in last_alert_time:
        if (now - last_alert_time[symbol]).total_seconds() < 900:
            return
    last_alert_time[symbol] = now

    icon = "🟢 🚀" if action == "BUY" else "🔴 ⚠️"
    msg = (
        f"{icon} *QUANTMIND AI LIVE ALERT*\n\n"
        f"🎯 *Action:* `{action}`\n"
        f"📈 *Stock:* `{symbol}`\n"
        f"💰 *Current Price:* ₹{price}\n"
        f"📊 *Strategy:* Multi-Factor Momentum & Mean Reversion\n"
        f"🔍 *Trigger Reason:* {reason}\n"
        f"⏱️ *Time:* {now.strftime('%d-%m-%Y %H:%M:%S IST')}\n\n"
        f"⚠️ _Real-time signal generated from live Upstox feed. Review on Upstox app before executing._"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if data.get("ok"):
                    logger.info(f"Telegram alert dispatched: {symbol} -> {action} @ Rs. {price}")
                else:
                    logger.error(f"Failed to send Telegram alert: {data}")
    except Exception as e:
        logger.error(f"Telegram network error: {e}")

def calculate_rsi(prices: list[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
    gains = [d for d in deltas[-period:] if d > 0]
    losses = [-d for d in deltas[-period:] if d < 0]
    
    avg_gain = sum(gains) / period if gains else 0.0001
    avg_loss = sum(losses) / period if losses else 0.0001
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

async def analyze_tick(symbol: str, price: float, volume: int):
    if symbol not in price_history:
        price_history[symbol] = []
    
    history = price_history[symbol]
    history.append(price)
    if len(history) > 100:
        history.pop(0)

    if len(history) < 15:
        return

    # Calculate indicators
    rsi = calculate_rsi(history)
    sma_short = sum(history[-5:]) / 5
    sma_long = sum(history[-15:]) / 15

    # Strategy: RSI Oversold + Short-term Momentum Crossover -> BUY
    if rsi < 32 and price > sma_short:
        reason = f"RSI Oversold ({rsi:.1f}) + Price Cross above Short SMA"
        logger.info(f"⚡ [BUY SIGNAL] {symbol} @ {price} | {reason}")
        await send_telegram_alert(symbol, "BUY", price, reason)
    # Strategy: RSI Overbought -> SELL/EXIT
    elif rsi > 70 and price < sma_short:
        reason = f"RSI Overbought ({rsi:.1f}) + Exhaustion below Short SMA"
        logger.info(f"⚡ [SELL/EXIT SIGNAL] {symbol} @ {price} | {reason}")
        await send_telegram_alert(symbol, "SELL", price, reason)

async def run_live_loop():
    logger.info("Starting QuantMind Live Market Data Polling & Analysis Service...")
    logger.info(f"Tracking {len(WATCHLIST)} active instruments on NSE...")
    
    keys = ",".join(WATCHLIST.values())
    url = f"https://api.upstox.com/v2/market-quote/quotes?instrument_key={keys}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {UPSTOX_TOKEN}"
    }

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        quotes = data.get("data", {})
                        for key, info in quotes.items():
                            sym = get_friendly_symbol(key)
                            price = info.get("last_price")
                            vol = info.get("volume", 0)
                            if sym and price is not None:
                                await analyze_tick(sym, float(price), int(vol or 0))
                    elif resp.status == 401:
                        logger.error("Upstox Access Token Expired! Please refresh in .env")
                        await asyncio.sleep(60)
                    else:
                        logger.warning(f"Upstox Quote API responded with {resp.status}")
            except Exception as e:
                logger.error(f"Error fetching quotes: {e}")

            # Polling cadence: every 3 seconds for active price movement
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(run_live_loop())
