#!/usr/bin/env python3
"""
CRYPTOWEEKEND — CEREBRO liquid-mover scan.

1. Pull top crypto assets by market cap from CoinGecko.
2. Keep only HIGH-LIQUIDITY + MOVING names:
     - 24h $ volume >= MIN_VOL  (liquidity floor)
     - |24h %|        >= MIN_MOVE (must actually move)
3. Map each to a live, active Binance <BASE>/USDT pair (no mock fallback).
4. Run CEREBRO conviction scoring on REAL 1h OHLCV (mock path bypassed).
5. Rank by liquidity-weighted mover score, emit cerebro_crypto_weekend_<date>.json.

NOTE: CEREBRO's fetch_crypto_data() silently returns seeded mock data on any
error. We do NOT call sc.scan(); we fetch real OHLCV via ccxt and inject sc.df,
then call the indicator methods directly. See cerebro-crypto-scan SKILL.md.
"""
from __future__ import annotations
import json, sys, datetime, time
from pathlib import Path
import pandas as pd
import numpy as np
import ccxt
import urllib.request

HOME = Path.home()
sys.path.insert(0, str(HOME / "workspace" / "think-tank" / "scanners"))
import cerebro_scan as cb

MIN_VOL = 50_000_000      # $50M/day 24h volume floor -> liquid enough to size into
MIN_MOVE = 2.0           # |24h %| must be >= 2% to count as "moving"
TOP_N = 25               # how many to feed CEREBRO
LOOKBACK = 100
TF = "1h"

DATE = datetime.datetime.utcnow().strftime("%Y%m%d")


def coingecko_top(per_page=250):
    url = ("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&"
           f"order=market_cap_desc&per_page={per_page}&page=1&sparkline=false&"
           "price_change_percentage=24h,7d,14d,30d")
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def build_universe():
    coins = coingecko_top()
    rows = []
    for c in coins:
        sym = (c.get("symbol") or "").upper()
        vol = c.get("total_volume") or 0
        ch24 = c.get("price_change_percentage_24h_in_currency")
        ch7 = c.get("price_change_percentage_7d_in_currency")
        ch24 = ch24 if ch24 is not None else (c.get("price_change_percentage_24h") or 0)
        if vol < MIN_VOL:
            continue
        if ch24 is None or abs(ch24) < MIN_MOVE:
            continue
        rows.append({
            "id": c.get("id"), "symbol": sym, "name": c.get("name"),
            "price": c.get("current_price"),
            "market_cap": c.get("market_cap"),
            "volume_24h": vol,
            "chg_24h": round(ch24, 2),
            "chg_7d": round(ch7, 2) if ch7 is not None else None,
        })
    v = np.array([r["volume_24h"] for r in rows], float)
    m = np.array([abs(r["chg_24h"]) for r in rows], float)
    zv = (v - v.mean()) / (v.std() + 1e-9)
    zm = (m - m.mean()) / (m.std() + 1e-9)
    for i, r in enumerate(rows):
        r["liq_z"] = round(float(zv[i]), 3)
        r["move_z"] = round(float(zm[i]), 3)
        r["mover_score"] = round(float(0.5 * zv[i] + 0.5 * zm[i]), 3)
    rows.sort(key=lambda r: r["mover_score"], reverse=True)
    return rows[:TOP_N]


def main():
    print(f"[1/4] Fetching CoinGecko top assets @ {datetime.datetime.utcnow().isoformat()}Z")
    universe = build_universe()
    print(f"      -> {len(universe)} liquid+movers passed filters "
          f"(vol>={MIN_VOL/1e6:.0f}M, |24h%|>={MIN_MOVE:.0f}%)")
    if not universe:
        print("NO UNIVERSE — relax MIN_VOL/MIN_MOVE"); sys.exit(1)

    (HOME / f"cerebro_crypto_universe_{DATE}.json").write_text(json.dumps(universe, indent=2))

    print("[2/4] Loading Binance markets + validating USDT pairs")
    ex = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    ex.load_markets()
    valid = {s for s, m in ex.markets.items() if m.get("active") and s.endswith("/USDT")}

    print("[3/4] Running CEREBRO conviction on REAL 1h OHLCV (mock fallback bypassed)")
    results = []
    for r in universe:
        pair = f"{r['symbol']}/USDT"
        if pair not in valid:
            print(f"      skip {pair}: no live Binance USDT pair"); continue
        try:
            ohlcv = ex.fetch_ohlcv(pair, TF, limit=LOOKBACK)
        except Exception as e:
            print(f"      skip {pair}: fetch error {e}"); continue
        if not ohlcv or len(ohlcv) < LOOKBACK:
            print(f"      skip {pair}: insufficient bars ({len(ohlcv) if ohlcv else 0})"); continue
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
        sc = cb.CerebroScanner(pair)
        sc.df = df                      # <-- inject REAL data, no _generate_mock_data
        sc.determine_signal()
        rsi = sc.calculate_rsi()
        macd = sc.calculate_macd()
        bb = sc.calculate_bollinger_bands()
        vol_ok = sc.calculate_volume_confirmation()

        def _coerce(v):
            if isinstance(v, np.bool_): return bool(v)
            if isinstance(v, np.integer): return int(v)
            if isinstance(v, np.floating): return float(v)
            return v

        rec = {
            "symbol": pair, "name": r["name"], "coingecko_id": r["id"],
            "price": float(df["close"].iloc[-1]),
            "rsi": round(float(rsi), 2),
            "macd": {k: (round(float(v), 4) if isinstance(v, (int, float, np.floating, np.integer)) else _coerce(v)) for k, v in macd.items()},
            "bollinger": {k: (round(float(v), 2) if isinstance(v, (int, float, np.floating, np.integer)) else _coerce(v)) for k, v in bb.items()},
            "volume_confirmed": bool(vol_ok),
            "conviction_score": sc.conviction_score,
            "signal": sc.signal,
            "chg_24h": r["chg_24h"], "chg_7d": r["chg_7d"],
            "volume_24h": r["volume_24h"], "mover_score": r["mover_score"],
        }
        results.append(rec)
        print(f"      {pair:12s} conv={sc.conviction_score:3d} {sc.signal:11s} "
              f"rsi={rsi:5.1f} 24h={r['chg_24h']:+.1f}% vol=${r['volume_24h']/1e9:.2f}B")
        time.sleep(0.25)

    results.sort(key=lambda x: x["conviction_score"], reverse=True)
    out = {
        "scanner": "CEREBRO", "mode": "cryptoweekend-liquid-movers",
        "generated": datetime.datetime.utcnow().isoformat() + "Z",
        "filters": {"min_volume_24h": MIN_VOL, "min_abs_move_24h_pct": MIN_MOVE, "top_n": TOP_N},
        "count": len(results), "results": results,
    }
    path = HOME / f"cerebro_crypto_weekend_{DATE}.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"[4/4] wrote {path}  ({len(results)} symbols scored)")

    print("\nTOP CONVICTION (liquid + moving):")
    for x in results[:10]:
        print(f"  {x['symbol']:12s} {x['signal']:11s} conv={x['conviction_score']:3d} "
              f"rsi={x['rsi']:5.1f} 24h={x['chg_24h']:+.1f}%")


if __name__ == "__main__":
    main()
