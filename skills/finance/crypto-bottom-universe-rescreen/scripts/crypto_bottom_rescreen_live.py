#!/usr/bin/env python3
"""Live bottom-universe rescreen.
Pulls top-500 by mcap (CoinGecko) -> filter %-from-ATH <= -90 (only proven-pay bucket)
-> compute live RSI(14) on survivors via Binance ccxt to confirm oversold.
Usage: python3 crypto_bottom_rescreen_live.py
Needs: ccxt, requests  (both present on this box, no install)
"""
import ccxt, requests, time, sys
from datetime import datetime, timezone

CG = "https://api.coingecko.com/api/v3"
MIN_ATH_DROP = 90.0      # % below ATH; user's only positive base-rate bucket
MIN_VOL = 5_000_000      # liquid enough to ladder
OVERSOLD_RSI = 35.0


def cg_markets(pages=2, per=250):
    out = []
    for p in range(1, pages + 1):
        r = requests.get(f"{CG}/coins/markets", params={
            "vs_currency": "usd", "order": "market_cap_desc",
            "per_page": per, "page": p, "sparkline": "false"}, timeout=30)
        r.raise_for_status()
        out += r.json()
        time.sleep(1.5)   # avoid CoinGecko 429 between pages
    return out


def rsi14(closes):
    if len(closes) < 15:
        return None
    gains = [max(closes[i] - closes[i-1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i-1] - closes[i], 0) for i in range(1, len(closes))]
    ag = sum(gains[-14:]) / 14
    al = sum(losses[-14:]) / 14
    if al == 0:
        return 100.0
    rs = ag / al
    return 100 - (100 / (1 + rs))


def main():
    print(f"[{datetime.now(timezone.utc):%H:%M UTC}] pulling top-500 markets...")
    mk = cg_markets()
    total = len(mk)
    far = [m for m in mk if m.get("ath_change_percentage") is not None
           and m["ath_change_percentage"] <= -MIN_ATH_DROP]
    print(f"  {total} coins | {len(far)} at <= -{MIN_ATH_DROP:.0f}% from ATH")
    ex = ccxt.binance()
    ex.load_markets()
    rows = []
    for m in far:
        sym = m["symbol"].upper()
        pair = f"{sym}/USDT"
        if pair not in ex.markets:
            continue
        vol = m.get("total_volume") or 0
        if vol < MIN_VOL:
            continue
        try:
            ohlcv = ex.fetch_ohlcv(pair, "1h", limit=120)
            closes = [c[4] for c in ohlcv]
            r = rsi14(closes)
        except Exception:
            r = None
        rows.append({
            "sym": sym, "name": m["name"],
            "price": m["current_price"],
            "ath_pct": m["ath_change_percentage"],
            "chg24h": m.get("price_change_percentage_24h"),
            "vol": vol, "rsi": r,
        })
        time.sleep(0.25)
    rows.sort(key=lambda x: x["ath_pct"])
    print(f"\n  liquid far-from-ATH survivors: {len(rows)}")
    print(f"  {'SYM':6} {'ATH%':>7} {'RSI':>6} {'24h%':>7} {'vol$M':>7}  name")
    for x in rows:
        rsi = f"{x['rsi']:.1f}" if x['rsi'] is not None else "n/a"
        c24 = f"{x['chg24h']:.1f}" if x['chg24h'] is not None else "n/a"
        flag = " <<OVERSOLD" if (x['rsi'] is not None and x['rsi'] < OVERSOLD_RSI) else ""
        print(f"  {x['sym']:6} {x['ath_pct']:7.1f} {rsi:>6} {c24:>7} {x['vol']/1e6:7.1f}{flag}  {x['name']}")
    oversold = [x for x in rows if x['rsi'] is not None and x['rsi'] < OVERSOLD_RSI]
    print(f"\n  OVERSOLD (<{OVERSOLD_RSI}) far-from-ATH names: {len(oversold)}")
    # exclude -100% ATH red flags from the quality subset print
    bad = [x['sym'] for x in oversold if x['ath_pct'] <= -99.9]
    if bad:
        print(f"  (exclude as -100%/dead: {', '.join(bad)})")


if __name__ == "__main__":
    main()
