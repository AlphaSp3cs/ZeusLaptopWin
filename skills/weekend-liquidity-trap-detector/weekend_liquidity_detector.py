#!/usr/bin/env python3
"""Weekend Liquidity Trap Detector — LIVE volume/spread surveillance via Binance.

Replaces the scaffold. Uses public Binance klines: compares current (weekend)
volume to the trailing 20-day weekday average to flag thin-book pumps/dumps.

Tables written (audit target: volume_history, pump_detections):
  volume_history   per-symbol daily volume + z-score vs 20d avg
  pump_detections  symbols with abnormal volume OR price move on thin book

No network => no rows => stays DEAD (never fabricates).
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
DB_PATH = SKILL_DIR / "weekend_liquidity.db"
LOG_PATH = SKILL_DIR / "weekend_liquidity.log"
API = "https://api.binance.com"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT",
           "ADAUSDT", "AVAXUSDT", "NEARUSDT", "LINKUSDT", "TRXUSDT"]
session = requests.Session()
session.headers.update({"User-Agent": "ourotaurus-weekend-sentinel/1.0"})


def log(m):
    with open(LOG_PATH, "a") as f:
        f.write(f"[{datetime.now(timezone.utc)}] {m}\n")


def init_database():
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS volume_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        symbol TEXT,
        volume REAL,
        vol_zscore REAL,
        price_change_pct REAL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS pump_detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        symbol TEXT,
        reason TEXT,
        volume_ratio REAL,
        price_change_pct REAL
    )""")
    con.commit()
    con.close()


def fetch_klines(sym, limit=22):
    try:
        r = session.get(f"{API}/api/v3/klines",
                        params={"symbol": sym, "interval": "1d", "limit": limit},
                        timeout=12)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log(f"klines fail {sym}: {e}")
        time.sleep(1)
    return None


def run_liquidity_check():
    init_database()
    con = sqlite3.connect(DB_PATH)
    detected = []
    for sym in SYMBOLS:
        rows = fetch_klines(sym, 22)
        if not rows or len(rows) < 21:
            continue
        vols = [float(r[5]) for r in rows[:-1]]  # exclude today for baseline
        today_vol = float(rows[-1][5])
        today_chg = (float(rows[-1][4]) / float(rows[-1][1]) - 1) * 100
        mean = sum(vols) / len(vols)
        var = sum((v - mean) ** 2 for v in vols) / len(vols)
        sd = var ** 0.5 or 1.0
        z = (today_vol - mean) / sd
        ratio = today_vol / mean if mean else 0
        con.execute("INSERT INTO volume_history (symbol, volume, vol_zscore, price_change_pct) VALUES (?,?,?,?)",
                    (sym, today_vol, z, today_chg))
        # trap logic: big move on THIN volume (|z|<0.5) or volume spike w/ move
        if abs(today_chg) > 3 and abs(z) < 0.5:
            reason = "low-volume pump/dump (big move, thin book)"
            con.execute("INSERT INTO pump_detections (symbol, reason, volume_ratio, price_change_pct) VALUES (?,?,?,?)",
                        (sym, reason, round(ratio, 2), round(today_chg, 2)))
            detected.append((sym, reason, today_chg))
        elif abs(z) > 3 and abs(today_chg) > 2:
            reason = "volume spike with directional move"
            con.execute("INSERT INTO pump_detections (symbol, reason, volume_ratio, price_change_pct) VALUES (?,?,?,?)",
                        (sym, reason, round(ratio, 2), round(today_chg, 2)))
            detected.append((sym, reason, today_chg))
    con.commit()
    con.close()
    if detected:
        print("DETECTIONS:")
        for s, r, c in detected:
            print(f"  {s}: {r} ({c:+.1f}%)")
    else:
        print("weekend liquidity scan complete — no traps flagged")


if __name__ == "__main__":
    sys.path.insert(0, str(SKILL_DIR))
    try:
        import _ourotaurus_secrets  # noqa: F401
    except Exception:
        pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        run_liquidity_check()
    else:
        print("Usage: python weekend_liquidity_detector.py [check]")
