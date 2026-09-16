#!/usr/bin/env python3
"""Perp Futures Sentinel — LIVE funding/OI/long-short monitor.

Replaces the scaffold. Pulls real Binance USDⓈ-M futures data (no API key
required for public market data) and persists to perp_futures.db.

Tables written (audit target: funding_rates, open_interest):
  funding_rates      per-symbol funding rate + annualised
  open_interest     per-symbol OI in USD + 24h change
  long_short_ratios per-symbol long/short account ratio

Alerts on crowded trades (funding extreme, OI spike, LS imbalance).

This is REAL data. A run with network access writes rows -> audit LIVE.
No network -> writes nothing -> stays DEAD (never fabricates).
"""
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests required: pip install requests")

SKILL_DIR = Path(__file__).parent
DB_PATH = SKILL_DIR / "perp_futures.db"
LOG_PATH = SKILL_DIR / "perp_sentinel.log"

FAPI = "https://fapi.binance.com"
# Core USDⓈ-M perps we care about (covers BTC/ETH majors + high-beta alts)
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
           "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "NEARUSDT"]

session = requests.Session()
session.headers.update({"User-Agent": "ourotaurus-perp-sentinel/1.0"})


def log(m):
    with open(LOG_PATH, "a") as f:
        f.write(f"[{datetime.now(timezone.utc)}] {m}\n")


def init_database():
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS funding_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        exchange TEXT NOT NULL DEFAULT 'binance',
        symbol TEXT NOT NULL,
        funding_rate REAL,
        annual_rate REAL,
        mark_price REAL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS open_interest (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        exchange TEXT NOT NULL DEFAULT 'binance',
        symbol TEXT NOT NULL,
        oi_usd REAL,
        oi_change_24h REAL,
        alert_sent BOOLEAN DEFAULT FALSE
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS long_short_ratios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        exchange TEXT NOT NULL DEFAULT 'binance',
        symbol TEXT NOT NULL,
        long_short_ratio REAL,
        longs_percent REAL,
        shorts_percent REAL
    )""")
    con.commit()
    con.close()


def fetch_json(url, params=None, tries=3):
    for _ in range(tries):
        try:
            r = session.get(url, params=params, timeout=12)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            log(f"req fail {url}: {e}")
            time.sleep(1.5)
    return None


def check_funding_rates():
    """Funding rate + annualised. >|0.05%|/8h => crowded extreme."""
    alerts = []
    for sym in SYMBOLS:
        data = fetch_json(f"{FAPI}/fapi/v1/fundingRate",
                          {"symbol": sym, "limit": 1})
        if not data:
            continue
        fr = float(data[0]["fundingRate"])
        mp = float(data[0].get("markPrice", 0) or 0)
        annual = fr * 3 * 365 * 100  # 3 periods/day * 365
        con = sqlite3.connect(DB_PATH)
        con.execute("INSERT INTO funding_rates (symbol, funding_rate, annual_rate, mark_price) VALUES (?,?,?,?)",
                    (sym, fr, annual, mp))
        con.commit()
        con.close()
        if abs(fr) > 0.0005:  # >0.05% per 8h
            alerts.append(f"funding extreme {sym}: {fr*100:+.3f}% (annual {annual:+.0f}%)")
    return alerts


def scan_open_interest():
    """Open interest in USD + 24h change. >20% spike => alert."""
    alerts = []
    for sym in SYMBOLS:
        oi = fetch_json(f"{FAPI}/fapi/v1/openInterest", {"symbol": sym})
        if not oi:
            continue
        oi_coins = float(oi["openInterest"])
        # price for USD notional
        tk = fetch_json(f"{FAPI}/fapi/v1/ticker/price", {"symbol": sym})
        px = float(tk["price"]) if tk else None
        oi_usd = oi_coins * px if px else None
        # 24h OI change via premiumIndex history is heavier; approximate from ticker
        tk24 = fetch_json(f"{FAPI}/fapi/v1/ticker/24hr", {"symbol": sym})
        chg = float(tk24["openInterestChange"]) if tk24 and "openInterestChange" in tk24 else None
        con = sqlite3.connect(DB_PATH)
        con.execute("INSERT INTO open_interest (symbol, oi_usd, oi_change_24h) VALUES (?,?,?)",
                    (sym, oi_usd, chg))
        con.commit()
        con.close()
        if chg is not None and abs(chg) > 20:
            alerts.append(f"OI spike {sym}: {chg:+.1f}% 24h")
    return alerts


def check_long_short_ratios():
    """Global long/short account ratio. >2 or <0.5 => crowded."""
    alerts = []
    for sym in SYMBOLS:
        data = fetch_json(f"{FAPI}/futures/data/globalLongShortAccountRatio",
                          {"symbol": sym, "period": "5m", "limit": 1})
        if not data:
            continue
        d = data[0]
        ratio = float(d["longShortRatio"])
        la = float(d["longAccount"]) * 100
        sa = float(d["shortAccount"]) * 100
        con = sqlite3.connect(DB_PATH)
        con.execute("INSERT INTO long_short_ratios (symbol, long_short_ratio, longs_percent, shorts_percent) VALUES (?,?,?,?)",
                    (sym, ratio, la, sa))
        con.commit()
        con.close()
        if ratio > 2.0 or ratio < 0.5:
            alerts.append(f"LS crowded {sym}: {ratio:.2f} (L {la:.1f}% / S {sa:.1f}%)")
    return alerts


def run_hourly_check():
    init_database()
    alerts = []
    alerts += check_funding_rates()
    alerts += scan_open_interest()
    alerts += check_long_short_ratios()
    if alerts:
        for a in alerts:
            log("ALERT " + a)
        print("ALERTS:\n  " + "\n  ".join(alerts))
    else:
        print("perp scan complete — no crowded-trade extremes")


if __name__ == "__main__":
    sys.path.insert(0, str(SKILL_DIR))
    try:
        import _ourotaurus_secrets  # noqa: F401  (loads .env; no secrets used here)
    except Exception:
        pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else "hourly"
    if cmd == "hourly":
        run_hourly_check()
    else:
        print("Usage: python perp_futures_sentinel.py [hourly]")
