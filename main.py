# london_orb.py – FULL SCRIPT (copy-paste & run)
import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.trades as trades
from oandapyV20.contrib.requests import MarketOrderRequest, TakeProfitDetails, StopLossDetails
import time
import datetime as dt
import requests
import threading
import logging

# =============================================================================
# CONFIG – CHANGE ONLY THESE 4 LINES WHEN YOU GO LIVE
# =============================================================================
ACCOUNT_TYPE = "practice"           # ← change to "live" when ready
ACCOUNT_ID   = "101-004-35847042-002"  # ← your account number
API_KEY      = "your-practice-key-here"   # ← change when live
OANDA_ENV    = "practice"           # ← "live" when ready

# =============================================================================
# WEBHOOK & TELEGRAM – ALREADY POINTING TO YOUR DASHBOARD
# =============================================================================
WEBHOOK_URL      = "https://nas-orb-ldn-open.onrender.com/webhook"
WEBHOOK_ENABLED  = True
TELEGRAM_TOKEN   = "812345678:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"   # change if you want private channel
TELEGRAM_CHAT_ID = "-123456789"
TELEGRAM_ENABLED = True

# =============================================================================
# TRADING SETTINGS
# =============================================================================
INSTRUMENTS = ["GBP_USD", "EUR_USD", "GBP_JPY", "EUR_JPY", "AUD_JPY", "USD_JPY"]
RISK_PERCENT = 0.009                      # 0.9% risk per trade
ORB_MINUTES = 30
ORB_BREAK_PIPS = {"GBP_USD": 15, "EUR_USD": 12, "GBP_JPY": 25, "EUR_JPY": 25, "AUD_JPY": 20, "USD_JPY": 15}
RR_RATIO = 2.0

# =============================================================================
# LOGGING & NOTIFICATIONS
# =============================================================================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

def send(msg):
    log.info(msg)
    if WEBHOOK_ENABLED:
        try:
            requests.post(WEBHOOK_URL, json={"message": msg})
        except:
            pass
    if TELEGRAM_ENABLED:
        try:
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                         params={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        except:
            pass

# =============================================================================
# OANDA CONNECTION
# =============================================================================
api = oandapyV20.API(access_token=API_KEY, environment=OANDA_ENV)

def get_balance():
    r = accounts.AccountDetails(ACCOUNT_ID)
    api.request(r)
    return float(r.response['account']['balance'])

def get_price(inst):
    params = {"count": 2, "granularity": "M1"}
    r = instruments.InstrumentsCandles(instrument=inst, params=params)
    api.request(r)
    return float(r.response['candles'][-1]['mid']['c'])

# =============================================================================
# MAIN ORB LOGIC
# =============================================================================
def london_orb():
    send(f"London ORB – {dt.datetime.utcnow().strftime('%H:%M')} UTC – building 07:00–07:30 range")
    time.sleep(60)  # wait till 07:01 to make sure range candle closed

    ranges = {}
    for inst in INSTRUMENTS:
        params = {"from": (dt.datetime.utcnow() - dt.timedelta(minutes=35)).isoformat() + "Z",
                  "to": (dt.datetime.utcnow() - dt.timedelta(minutes=5)).isoformat() + "Z",
                  "granularity": "M5"}
        r = instruments.InstrumentsCandles(instrument=inst, params=params)
        api.request(r)
        candles = r.response['candles']
        highs = [float(c['mid']['h']) for c in candles]
        lows = [float(c['mid']['l']) for c in candles]
        ranges[inst] = {"high": max(highs), "low": min(lows)}
        send(f"{inst} ORB → High {max(highs):.5f} | Low {min(lows):.5f}")

    # Place pending orders
    balance = get_balance()
    for inst in INSTRUMENTS:
        high = ranges[inst]["high"]
        low = ranges[inst]["low"]
        break_pips = ORB_BREAK_PIPS.get(inst.replace("_", ""), 15)
        pip_size = 0.0001 if "JPY" not in inst else 0.01

        long_entry = high + break_pips * pip_size
        short_entry = low - break_pips * pip_size
        sl_pips = break_pips * 1.5
        tp_pips = sl_pips * RR_RATIO

        units_long = int((balance * RISK_PERCENT) / (sl_pips * pip_size * 100000))
        units_short = -units_long

        # LONG ORDER
        mo = MarketOrderRequest(instrument=inst, units=units_long,
                                 stopLossOnFill=StopLossDetails(price=round(long_entry - sl_pips * pip_size, 5)),
                                 takeProfitOnFill=TakeProfitDetails(price=round(long