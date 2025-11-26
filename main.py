# london_orb_full_dashboard.py
from flask import Flask
import threading
import time
from datetime import datetime
import pytz
import v20
import requests
import os

app = Flask(__name__)

# ================= YOUR REAL CREDENTIALS =================
OANDA_ACCOUNT_ID = "101-004-35847042-002"
OANDA_TOKEN = "f0f53a8e9edc5876590a61755f470acd-7b2ca161a8ee8569edcd7fec1487c70b"
OANDA_ENV = "practice"  # flip to "live" when ready

ctx = v20.Context(
    'api-fxpractice.oanda.com' if OANDA_ENV == "practice" else 'api-fxtrade.oanda.com',
    443,
    token=OANDA_TOKEN
)

# Telegram
TELEGRAM_TOKEN = "8172914158:AAGHyW_q_PrJZpTiNv_X5g0DyfEcgtGykBE"  # ← your token
CHAT_ID = "5372494623"  # ← your chat ID
bot = requests.Session()

def send_log(msg):
    try:
        bot.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                 data={"chat_id": CHAT_ID, "text": msg}, timeout=5)
        timestamp = datetime.now(pytz.timezone("US/Eastern")).strftime("%H:%M:%S")
        with open("london_orb.log", "a") as f:
            f.write(f"[{timestamp}] {msg}\n")
        print(f"[{timestamp}] {msg}")
    except Exception as e:
        print(f"Log failed: {e}")

def get_current_price():
    try:
        r = ctx.pricing.get(OANDA_ACCOUNT_ID, instruments=SYMBOL)
        return float(r.body['prices'][0].closeoutBid)
    except:
        return None

def place_trade(direction):
    units = 1000  # 1 mini lot – change as needed
    entry = get_current_price()
    if not entry: return
    sl_pips = 80
    tp_pips = 150
    
    sl = round(entry - sl_pips if direction == "LONG" else entry + sl_pips, 1)
    tp = round(entry + tp_pips if direction == "LONG" else entry - tp_pips, 1)
    
    order = {
        "order": {
            "instrument": SYMBOL,
            "units": str(units) if direction == "LONG" else str(-units),
            "type": "MARKET",
            "stopLossOnFill": {"price": f"{sl:.1f}"},
            "takeProfitOnFill": {"price": f"{tp:.1f}"}
        }
    }
    
    try:
        response = ctx.order.create(OANDA_ACCOUNT_ID, **order)
        send_log(f"🚀 LONDON ORB {direction} EXECUTED @ {entry}\n"
                 f"SL {sl} | TP {tp}\n"
                 f"Account: {OANDA_ACCOUNT_ID} ({OANDA_ENV.upper()})\n"
                 f"Factory printed +{tp_pips} pips potential")
    except Exception as e:
        send_log(f"ORDER FAILED: {e}")

def reset_daily():
    global orb_high, orb_low, orb_set, trade_fired
    orb_high = orb_low = None
    orb_set = trade_fired = False

def london_orb_hunter():
    global orb_high, orb_low, orb_set, trade_fired
    
    while True:
        now = datetime.now(pytz.timezone("US/Eastern"))
        
        # Midnight reset
        if now.hour == 0 and now.minute == 0:
            reset_daily()
            send_log("🏭 LONDON ORB SNIPER – DAILY RESET")

        # 3:00 AM ET – set ORB from first 15-min candle
        if now.hour == 3 and now.minute == 0 and now.second < 30 and not orb_set:
            try:
                r = ctx.candles.get(instrument=SYMBOL, granularity="M15", count=2)
                latest = r.body['candles'][-1]
                orb_high = float(latest.high.ask)
                orb_low = float(latest.low.bid)
                orb_set = True
                send_log(f"🟥 LONDON ORB SET (3:00–3:15 AM ET)\n"
                         f"High: {orb_high}\nLow: {orb_low}\n"
                         f"Hunting breakout...")
            except Exception as e:
                send_log(f"Candle fetch failed: {e}")

        # 3:00–3:15 AM ET breakout detection
        if orb_set and not trade_fired and now.hour == 3 and now.minute < 15:
            price = get_current_price()
            if price and price > orb_high + 5:
                place_trade("LONG")
                trade_fired = True
            elif price and price < orb_low - 5:
                place_trade("SHORT")
                trade_fired = True

        time.sleep(7)

@app.route('/')
def home():
    return "LONDON ORB SNIPER IS ARMED & HUNTING 🏭🔥 (Practice Account Live)"

@app.route('/orb')
def orb_log():
    try:
        with open("london_orb.log", "r") as f:
            return f"<pre>{f.read()[-4000:]}</pre><meta http-equiv='refresh' content='10'>"
    except:
        return "<pre>LONDON ORB LOG STARTING...</pre>"

if __name__ == '__main__':
    SYMBOL = "NAS100_USD"
    send_log("🏭 LONDON ORB SNIPER FULLY ARMED\n"
             "Account: 101-004-35847042-002 (practice)\n"
             "Next hunt: 3:00–3:15 AM ET\n"
             "Live log: /orb")
    threading.Thread(target=london_orb_hunter, daemon=True).start()
    app.run(host='0.0.0.0', port=8080)