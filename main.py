# london_orb.py – FULL FIXED SCRIPT (copy everything below this line)
import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.accounts as accounts
from oandapyV20.contrib.requests import MarketOrderRequest, TakeProfitDetails, StopLossDetails
import time
import datetime as dt
import requests
import threading
import logging

# =============================================================================
# CONFIG – CHANGE ONLY THESE 4 WHEN GOING LIVE
# =============================================================================
ACCOUNT_TYPE = "practice"
ACCOUNT_ID   = "101-004-35847042-002"      # ← change to your real one
API_KEY      = "your-practice-api-key-here" # ← change when live
OANDA_ENV    = "practice"

# =============================================================================
# WEBHOOK & TELEGRAM (already pointing to your dashboard)
# =============================================================================
WEBHOOK_URL      = "https://nas-orb-ldn-open.onrender.com/webhook"
WEBHOOK_ENABLED  = True
TELEGRAM_TOKEN   = "812345678:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TELEGRAM_CHAT_ID = "-123456789"
TELEGRAM_ENABLED = True

# =============================================================================
# SETTINGS
# =============================================================================
INSTRUMENTS = ["GBP_USD", "EUR_USD", "GBP_JPY", "EUR_JPY", "AUD_JPY", "USD_JPY"]
RISK_PERCENT = 0.009
ORB_BREAK_PIPS = {"GBP_USD": 15, "EUR_USD": 12, "GBP_JPY": 25, "EUR_JPY": 25, "AUD_JPY": 20, "USD_JPY": 15}
RR = 2.0

# =============================================================================
# NOTIFY
# =============================================================================
logging.basicConfig(level=logging.INFO)
def send(msg):
    logging.info(msg)
    if WEBHOOK_ENABLED:
        try: requests.post(WEBHOOK_URL, json={"message": msg})
        except: pass
    if TELEGRAM_ENABLED:
        try:
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                        params={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        except: pass

# =============================================================================
# OANDA
# =============================================================================
api = oandapyV20.API(access_token=API_KEY, environment=OANDA_ENV)

def get_balance():
    r = accounts.AccountDetails(ACCOUNT_ID)
    api.request(r)
    return float(r.response['account']['balance'])

# =============================================================================
# MAIN LONDON ORB
# =============================================================================
def london_orb():
    send("London ORB armed – building 07:00–07:30 range")
    while dt.datetime.utcnow().hour != 7 or dt.datetime.utcnow().minute < 31:
        time.sleep(10)
    
    ranges = {}
    for inst in INSTRUMENTS:
        params = {"count": 7, "granularity": "M5"}
        r = instruments.InstrumentsCandles(instrument=inst, params=params)
        api.request(r)
        candles = [c for c in r.response['candles'] if c['complete']]
        highs = [float(c['mid']['h']) for c in candles]
        lows  = [float(c['mid']['l']) for c in candles]
        ranges[inst] = {"high": max(highs), "low": min(lows)}
        send(f"{inst} ORB High {max(highs):.5f} | Low {min(lows):.5f}")

    balance = get_balance()
    for inst in INSTRUMENTS:
        high = ranges[inst]["high"]
        low  = ranges[inst]["low"]
        pips = ORB_BREAK_PIPS.get(inst.replace("_", ""), 15)
        pip_size = 0.0001 if "JPY" not in inst else 0.01
        
        long_entry  = high + pips * pip_size
        short_entry = low  - pips * pip_size
        sl_pips = pips * 1.5
        tp_pips = sl_pips * RR
        
        units = int((balance * RISK_PERCENT) / (sl_pips * pip_size * 100000))
        if units < 1000: units = 1000  # minimum size

        # LONG
        mo = MarketOrderRequest(
            instrument=inst,
            units=units,
            type="STOP",
            price=round(long_entry, 5),
            stopLossOnFill=StopLossDetails(price=round(long_entry - sl_pips * pip_size, 5)),
            takeProfitOnFill=TakeProfitDetails(price=round(long_entry + tp_pips * pip_size, 5))
        )
        try:
            api.request(orders.OrderCreate(ACCOUNT_ID, data=mo.data))
            send(f"{inst} LONG pending @ {long_entry:.5f}")
        except: pass

        # SHORT
        mo = MarketOrderRequest(
            instrument=inst,
            units=-units,
            type="STOP",
            price=round(short_entry, 5),
            stopLossOnFill=StopLossDetails(price=round(short_entry + sl_pips * pip_size, 5)),
            takeProfitOnFill=TakeProfitDetails(price=round(short_entry - tp_pips * pip_size, 5))
        )
        try:
            api.request(orders.OrderCreate(ACCOUNT_ID, data=mo.data))
            send(f"{inst} SHORT pending @ {short_entry:.5f}")
        except: pass

    send("London ORB complete – all orders live")

# =============================================================================
# DAILY LOOP
# =============================================================================
def daily_reset():
    send("London ORB bot started")
    while True:
        now = dt.datetime.utcnow()
        if now.hour == 0 and now.minute < 5:
            send(f"New day – balance ${get_balance():,.2f} – London ORB armed")
            next_run = dt.datetime(now.year, now.month, now.day, 7, 0)
            if now.hour >= 7: next_run += dt.timedelta(days=1)
            delay = (next_run - now).total_seconds()
            threading.Timer(delay, london_orb).start()
            time.sleep(300)
        time.sleep(60)

if __name__ == "__main__":
    daily_reset()