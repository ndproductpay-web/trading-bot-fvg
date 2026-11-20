import ccxt
import pandas as pd
import numpy as np
import mplfinance as mpf
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
from flask import Flask
from threading import Thread

# Render eka awaken karala thiyanna server eka
app_flask = Flask('')
@app_flask.route('/')
def home():
    return "Bot is Alive!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

Thread(target=run_flask).start()

TOKEN = os.environ.get("TOKEN")

exchange = ccxt.bybit()

def fmt(p):
    if p == 0:
        return "$0"
    if p < 0.0001:
        return f"${p:,.8f}"
    elif p < 0.01:
        return f"${p:,.6f}"
    elif p < 1:
        return f"${p:,.4f}"
    elif p < 100:
        return f"${p:,.3f}"
    else:
        return f"${p:,.2f}"

def get_data(symbol, timeframe):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=100)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df.set_index('time', inplace=True)
    return df

def find_fvg(df):
    fvgs = []
    for i in range(1, len(df)-1):
        if df['low'].iloc[i+1] > df['high'].iloc[i-1]:
            fvgs.append({'top': float(df['low'].iloc[i+1]), 'bottom': float(df['high'].iloc[i-1]), 'type': 'bullish', 'time': df.index[i]})
        if df['high'].iloc[i+1] < df['low'].iloc[i-1]:
            fvgs.append({'top': float(df['low'].iloc[i-1]), 'bottom': float(df['high'].iloc[i+1]), 'type': 'bearish', 'time': df.index[i]})
    return fvgs

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        symbol = args[0].upper() if len(args) > 0 else "BTCUSDT"
        timeframe = args[1] if len(args) > 1 else "15m"
        if "USDT" not in symbol:
            symbol = symbol + "USDT"
        await update.message.reply_text(f"📊 {symbol} - {timeframe} Analyze කරනවා... FVG එක හොයනවා...")
        df = get_data(symbol, timeframe)
        fvgs = find_fvg(df)
        last_price = float(df['close'].iloc[-1])
        support = float(df['low'].min())
        resistance = float(df['high'].max())
        nearest_fvg = None
        min_dist = 999999
        for f in fvgs:
            mid = (f['top'] + f['bottom']) / 2
            dist = abs(last_price - mid) / last_price * 100
            if dist < min_dist:
                min_dist = dist
                nearest_fvg = f
        if nearest_fvg:
            hlines = dict(hlines=[support, resistance, nearest_fvg['top'], nearest_fvg['bottom']], colors=['g','b','y','y'], linestyle=['--','--','-','-'])
        else:
            hlines = dict(hlines=[support, resistance], colors=['g','b'], linestyle='--')
        mpf.plot(df.tail(60), type='candle', style='charles',
                 title=f"{symbol} - {timeframe} - FVG Entry System",
                 hlines=hlines, savefig='chart.png', ylabel='Price')
        if nearest_fvg is None:
            signal = "⚪ NO TRADE - FVG එකක් නෑ"
            entry_msg = "FVG එකක් හැදුනේ නැති නිසා Wait කරන්න"
            sl = last_price; tp1 = last_price; tp2 = last_price; strength = "0/10"; fvg_size = 0
        else:
            fvg_top = nearest_fvg['top']; fvg_bottom = nearest_fvg['bottom']
            fvg_mid = (fvg_top + fvg_bottom) / 2
            fvg_size = abs(fvg_top - fvg_bottom) / last_price * 100
            in_fvg = fvg_bottom <= last_price <= fvg_top
            near_fvg = min_dist < 0.5
            if nearest_fvg['type'] == 'bullish':
                entry = fvg_mid; sl = fvg_bottom * 0.995
                tp1 = entry + (entry - sl) * 2; tp2 = entry + (entry - sl) * 3
                if in_fvg:
                    signal = "🟢 STRONG BUY - FVG එක ඇතුලේ ඉන්නේ!"; strength = "9/10 🔥"
                elif near_fvg:
                    signal = "🟡 BUY WAIT - FVG එකට ලඟයි, ඇතුලට එනකන් ඉන්න"; strength = "6/10"
                else:
                    signal = "⚪ NO TRADE - Price එක FVG එකෙන් දුරයි"; strength = "2/10"
                entry_msg = f"🟩 Buy Entry Zone: {fmt(fvg_bottom)} - {fmt(fvg_top)}\n🎯 Best Entry: {fmt(entry)}"
            else:
                entry = fvg_mid; sl = fvg_top * 1.005
                tp1 = entry - (sl - entry) * 2; tp2 = entry - (sl - entry) * 3
                if in_fvg:
                    signal = "🔴 STRONG SELL - FVG එක ඇතුලේ ඉන්නේ!"; strength = "9/10 🔥"
                elif near_fvg:
                    signal = "🟡 SELL WAIT - FVG එකට ලඟයි, ඇතුලට එනකන් ඉන්න"; strength = "6/10"
                else:
                    signal = "⚪ NO TRADE - Price එක FVG එකෙන් දුරයි"; strength = "2/10"
                entry_msg = f"🟥 Sell Entry Zone: {fmt(fvg_bottom)} - {fmt(fvg_top)}\n🎯 Best Entry: {fmt(entry)}"
        msg = f"""📊 {symbol} - {timeframe} FVG Analysis\n\n{signal}\n💪 Signal Strength: {strength}\n\n💰 Live Price: {fmt(last_price)}\n\n{entry_msg}\n\n🛑 Stop Loss: {fmt(sl)}\n🎯 Target 1 (1:2): {fmt(tp1)}\n🎯 Target 2 (1:3): {fmt(tp2)}\n\n🟦 Resistance: {fmt(resistance)}\n🟩 Support: {fmt(support)}\n🟨 FVG Size: {fvg_size:.2f}%\n📏 FVG එකට දුර: {min_dist:.2f}%\n\n⚠️ Rule: Price එක FVG ඇතුලට ආවම විතරක් Trade ගන්න.\n\n*මේක Analysis එකක් විතරයි.*"""
        await update.message.reply_photo(photo=open('chart.png','rb'), caption=msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"Error: {e}\n\nහරි විදිහ: /analyze BTCUSDT 15m")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hi! මම FVG Pro Bot!\n\nභාවිතය:\n/analyze BTCUSDT 15m\n/analyze ETHUSDT 1h\n/analyze SOLUSDT 4h")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("analyze", analyze))
print("Bot Running...")
app.run_polling()
