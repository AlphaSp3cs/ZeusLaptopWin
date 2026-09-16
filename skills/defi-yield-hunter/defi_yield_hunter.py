#!/usr/bin/env python3
"""DeFi Yield Hunter — LIVE TVL + yield from DeFiLlama (keyless).

Replaces the scaffold. DeFiLlama yields endpoint is public, no API key.
Tables written (audit target: tvl_history, yield_opportunities):
  tvl_history          top chains by TVL (snapshot)
  yield_opportunities  pools with APY>threshold, sorted

Real data only; no network => no rows => stays DEAD (never fabricates).
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
DB_PATH = SKILL_DIR / "defi_yields.db"
LOG_PATH = SKILL_DIR / "defi_yield.log"
LLAMA_YIELDS = "https://yields.llama.fi/pools"
LLAMA_TVL = "https://api.llama.fi/v2/chains"
MIN_APY = 20.0  # surfaced as "high yield" (matches skill description)
session = requests.Session()
session.headers.update({"User-Agent": "ourotaurus-defi-hunter/1.0"})


def log(m):
    with open(LOG_PATH, "a") as f:
        f.write(f"[{datetime.now(timezone.utc)}] {m}\n")


def init_database():
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS tvl_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        chain TEXT,
        tvl_usd REAL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS yield_opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        chain TEXT, project TEXT, symbol TEXT, pool TEXT,
        tvl_usd REAL, apy REAL, apy_base REAL, apy_reward REAL,
        stablecoin BOOLEAN, il_risk TEXT
    )""")
    con.commit()
    con.close()


def fetch_json(url, tries=3):
    for _ in range(tries):
        try:
            r = session.get(url, timeout=15)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            log(f"req fail {url}: {e}")
            time.sleep(1.5)
    return None


def scan_tvl_changes():
    data = fetch_json(LLAMA_TVL)
    if not isinstance(data, list):
        return 0
    con = sqlite3.connect(DB_PATH)
    n = 0
    for row in data[:50]:
        chain = row.get("name")
        tvl = row.get("tvl")
        if not chain or tvl is None:
            continue
        con.execute("INSERT INTO tvl_history (chain, tvl_usd) VALUES (?,?)",
                    (chain, float(tvl)))
        n += 1
    con.commit()
    con.close()
    return n


def hunt_yields():
    data = fetch_json(LLAMA_YIELDS)
    pools = data.get("data") if isinstance(data, dict) else None
    if not pools:
        return []
    con = sqlite3.connect(DB_PATH)
    found = []
    for p in pools:
        apy = p.get("apy")
        if apy is None or apy < MIN_APY:
            continue
        tvl = p.get("tvlUsd") or 0
        if tvl < 1_000_000:  # skip sub-$1M rugs
            continue
        con.execute("""INSERT INTO yield_opportunities
            (chain,project,symbol,pool,tvl_usd,apy,apy_base,apy_reward,stablecoin,il_risk)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (p.get("chain"), p.get("project"), p.get("symbol"), p.get("pool"),
             tvl, apy, p.get("apyBase"), p.get("apyReward"),
             bool(p.get("stablecoin")), p.get("ilRisk")))
        found.append((p.get("project"), p.get("symbol"), apy))
    con.commit()
    con.close()
    return found


def run_daily_tvl_scan():
    init_database()
    n_tvl = scan_tvl_changes()
    yields = hunt_yields()
    msg = f"TVL rows={n_tvl}; high-yield(>={MIN_APY}%)={len(yields)}"
    log(msg)
    if yields:
        top = sorted(yields, key=lambda x: x[2], reverse=True)[:8]
        print(msg + "\nTOP:")
        for proj, sym, apy in top:
            print(f"  {proj} {sym}: {apy:.1f}%")
    else:
        print(msg)


if __name__ == "__main__":
    sys.path.insert(0, str(SKILL_DIR))
    try:
        import _ourotaurus_secrets  # noqa: F401
    except Exception:
        pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else "daily"
    if cmd == "daily":
        run_daily_tvl_scan()
    else:
        print("Usage: python defi_yield_hunter.py [daily]")
