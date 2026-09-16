"""Refresh live tape for the bottom-study DCA ladder.

For each ladder symbol:
  1. CoinGecko spot (source of truth for price sanity)
  2. yfinance 10y daily -> recompute cycle low, MA50/MA200, ATR14, base score
  3. CEREBRO conviction score on REAL 1h ccxt OHLCV (injected, never sc.scan())
  4. Rewrite dca_ladder_levels.json which dca_ladder_check.py reads at runtime

Run:  python3 dca_tape_refresh.py
"""
import json, pathlib, sys, time, warnings
from datetime import datetime, timezone
import numpy as np, pandas as pd, requests, yfinance as yf

warnings.filterwarnings("ignore")
sys.path.insert(0, str(pathlib.Path.home() / "workspace" / "think-tank" / "scanners"))

HOME = pathlib.Path.home()
LEVELS = HOME / "dca_ladder_levels.json"
SYMBOLS = ["NEAR", "INJ"]
CG_IDS = {"NEAR": "near", "INJ": "injective-protocol"}


def cg_spot(coin_ids):
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                         params={"ids": ",".join(coin_ids), "vs_currencies": "usd"},
                         timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  CoinGecko error: {e}", file=sys.stderr)
        return {}


def yf_metrics(sym):
    df = yf.download(f"{sym}-USD", period="10y", interval="1d",
                     auto_adjust=False, progress=False, threads=False)
    if df is None or len(df) == 0:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])
    if len(df) < 300:
        return None
    c = df["Close"].astype(float)
    h, l = df["High"].astype(float), df["Low"].astype(float)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)

    last = float(c.iloc[-1])
    ath_i = int(c.values.argmax())
    post = c.iloc[ath_i:]
    low_i = int(post.values.argmin())
    low = float(post.iloc[low_i])
    low_date = post.index[low_i]
    ma50 = float(c.rolling(50).mean().iloc[-1])
    ma200s = c.rolling(200).mean()
    ma200 = float(ma200s.iloc[-1])
    slope90 = float(ma200s.iloc[-1] / ma200s.iloc[-91] - 1)
    off_low = last / low - 1
    months_off_low = round((c.index[-1] - low_date).days / 30.44, 1)
    higher_low = bool(float(c.iloc[-90:].min()) > low * 1.15)
    atr = float(tr.rolling(14).mean().iloc[-1])

    score = 100 * (0.30 * (off_low > 0.20) + 0.20 * (last > ma200)
                   + 0.15 * (last > ma50) + 0.15 * (slope90 > 0)
                   + 0.10 * higher_low + 0.10 * (months_off_low > 6))
    wk = c.resample("W").last()
    return {"yf_last": last, "cycle_low": low, "low_date": str(low_date.date()),
            "months_off_low": months_off_low, "off_low_pct": round(off_low * 100, 1),
            "ma50": ma50, "ma200": ma200, "ma200_slope90": round(slope90, 4),
            "atr14": atr, "atr_pct": round(atr / last * 100, 2),
            "higher_low": higher_low, "base_score": round(score, 1),
            "weekly_close": float(wk.iloc[-1]),
            "ath_dd_pct": round((last / float(c.iloc[ath_i]) - 1) * 100, 1)}


def cerebro(sym):
    """Conviction score on REAL 1h data. Injects sc.df — never calls sc.scan()."""
    try:
        import ccxt
        from cerebro_scan import CerebroScanner
    except Exception as e:
        return {"error": f"import: {e}"}
    try:
        ex = ccxt.binance()
        mk = ex.load_markets()
        pair = f"{sym}/USDT"
        if pair not in mk or not mk[pair].get("active"):
            return {"error": f"no active binance pair {pair}"}
        ohlcv = ex.fetch_ohlcv(pair, timeframe="1h", limit=200)
        if not ohlcv or len(ohlcv) < 60:
            return {"error": "insufficient ohlcv"}
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        df = df.set_index("ts")

        sc = CerebroScanner(pair, timeframe="1h")
        sc.df = df                      # bypass mock fallback
        rsi = sc.calculate_rsi()
        macd = sc.calculate_macd()
        bb = sc.calculate_bollinger_bands()
        volok = sc.calculate_volume_confirmation()
        conv = sc.calculate_conviction_score()
        sig = sc.determine_signal()
        return {"pair": pair, "price_1h": float(df["close"].iloc[-1]),
                "rsi": round(float(rsi), 1), "conviction": int(conv),
                "signal": str(sig), "volume_confirmed": bool(volok),
                "macd_hist": round(float(macd.get("histogram", 0)), 6),
                "bb_position": bb.get("position") if isinstance(bb, dict) else None,
                "bars": len(df)}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def main():
    now = datetime.now(timezone.utc)
    spot = cg_spot([CG_IDS[s] for s in SYMBOLS])
    out = {"refreshed": now.isoformat(), "symbols": {}}
    print(f"TAPE REFRESH  {now:%Y-%m-%d %H:%M} UTC\n")

    for sym in SYMBOLS:
        print(f"[{sym}]")
        cg = spot.get(CG_IDS[sym], {}).get("usd")
        m = yf_metrics(sym)
        if m is None:
            print("  yfinance: NO DATA - levels unchanged")
            out["symbols"][sym] = {"error": "no_yf_data"}
            continue
        ok = cg is not None and abs(m["yf_last"] / cg - 1) <= 0.15
        if not ok:
            print(f"  !! PRICE MISMATCH yf={m['yf_last']:.6g} cg={cg} - REFUSING to update")
            out["symbols"][sym] = {"error": "price_mismatch", "yf": m["yf_last"], "cg": cg}
            continue

        cb = cerebro(sym)
        # tranche levels recomputed off live structure, floored above invalidation
        low = m["cycle_low"]
        px = m["yf_last"]
        t4 = round(max(px * 0.85, low * 1.30), 4)
        t5 = round(max(px * 0.72, low * 1.12), 4)
        warn = round(max(px * 0.73, low * 1.15), 4)

        rec = {"cg_price": cg, **m, "cerebro": cb,
               "invalidation": round(low, 4), "warn_level": warn,
               "tranche4_level": t4, "tranche5_level": t5}
        out["symbols"][sym] = rec

        print(f"  px=${px:,.4f} (cg ${cg:,.4f} ok)  MA200=${m['ma200']:,.4f} "
              f"({(px/m['ma200']-1)*100:+.1f}%)  slope90={m['ma200_slope90']:+.4f}")
        print(f"  cycle_low=${low:,.4f} ({m['low_date']}, {m['months_off_low']}mo)  "
              f"ATR14={m['atr_pct']}%  base_score={m['base_score']}")
        if "error" in cb:
            print(f"  CEREBRO: unavailable ({cb['error']})")
        else:
            print(f"  CEREBRO {cb['pair']}: {cb['signal']} conviction={cb['conviction']} "
                  f"RSI={cb['rsi']} vol_conf={cb['volume_confirmed']}")
        print(f"  -> invalidation ${low:,.4f} | warn ${warn:,.4f} | "
              f"T4 ${t4:,.4f} | T5 ${t5:,.4f}\n")

    LEVELS.write_text(json.dumps(out, indent=1))
    print(f"wrote {LEVELS}")


if __name__ == "__main__":
    main()
