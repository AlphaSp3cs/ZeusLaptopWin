#!/usr/bin/env python3
"""
CRYPTOWEEKEND backtest-prep for CEREBRO liquid movers.

For each asset in cerebro_crypto_weekend_<date>.json, download 10y DAILY history
(yfinance <BASE>-USD) and backtest BOTH mean-reversion LONG (rsi<40 & close<vwap)
and extension SHORT (rsi>60 & close>vwap) with honest bookkeeping from
trading-backtest-integrity (entry at bar k close, exit from k+1, 2*ATR stop,
2R target, 20-bar cap). Splits history into in-sample (first 70%) and
out-of-sample walk-forward (last 30%). Reports PF / avgR / winrate for each.

3-TEST PROOF BAR (per standing rule):
  IS PF >= 1.0 AND OOS PF >= 1.0 on the SAME side -> GREEN_PROVEN.
  Only IS passes -> AMBER. Neither -> RED.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

HOME = Path.home()
DATE = __import__("datetime").datetime.utcnow().strftime("%Y%m%d")

RR = 2.0
ATR_MULT = 2.0
MAX_BARS = 20


def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1 + up/dn.replace(0, np.nan))


def atr(df, n=14):
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift()
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()


def vwap(df, n=20):
    tp = (df["High"]+df["Low"]+df["Close"])/3
    v = df["Volume"].fillna(0)
    if v.sum() <= 0:
        return tp.rolling(n).mean()
    pv = (tp*v).rolling(n).sum()
    vv = v.rolling(n).sum().replace(0, np.nan)
    return (pv/vv).fillna(tp.rolling(n).mean())


def backtest_hist(df, side):
    side = side.upper()
    df = df.dropna(subset=["Close"]).copy()
    df["rsi"], df["atr"], df["vwap"] = rsi(df["Close"]), atr(df), vwap(df)
    df = df.dropna()
    n = len(df)
    if n < 120:
        return None
    trades = []
    i = 0
    while i < n-1:
        r = df.iloc[i]
        trig = (side == "LONG" and r.rsi < 40 and r.Close < r.vwap) or \
               (side == "SHORT" and r.rsi > 60 and r.Close > r.vwap)
        if not trig or r.atr <= 0:
            i += 1; continue
        entry = float(df.iloc[i+1]["Open"])                     # entry at k+1 open
        risk = ATR_MULT*float(r.atr)
        sl, tp = (entry-risk, entry+RR*risk) if side == "LONG" else (entry+risk, entry-RR*risk)
        out, bars = None, 0
        for j in range(i+1, min(i+1+MAX_BARS, n)):              # exit from k+1
            b = df.iloc[j]; bars = j-i
            if side == "LONG":
                if b.Low <= sl: out = -1.0; break
                if b.High >= tp: out = RR; break
            else:
                if b.High >= sl: out = -1.0; break
                if b.Low <= tp: out = RR; break
        if out is None:
            last = float(df.iloc[min(i+MAX_BARS, n-1)]["Close"])
            out = ((last-entry) if side == "LONG" else (entry-last))/risk
        trades.append(out); i += bars+1
    if not trades:
        return None
    t = np.array(trades); wins = t[t > 0]; losses = t[t <= 0]
    pf = round(float(wins.sum()/abs(losses.sum())), 2) if losses.size and losses.sum() != 0 else (float("inf") if wins.size else 0.0)
    return {"trades": int(t.size), "win_rate": round(100*wins.size/t.size, 1),
            "avg_R": round(float(t.mean()), 3), "total_R": round(float(t.sum()), 1),
            "profit_factor": pf}


def main():
    scan = json.loads((HOME / f"cerebro_crypto_weekend_{DATE}.json").read_text())
    results = scan["results"]
    print(f"Backtesting {len(results)} liquid movers on 10y daily (yfinance -USD)\n")
    rows = []
    for r in results:
        base = r["symbol"].split("/")[0]
        yf_t = f"{base}-USD"
        try:
            df = yf.download(yf_t, period="10y", interval="1d", progress=False, auto_adjust=False)
        except Exception as e:
            print(f"  {base:8s} SKIP fetch: {e}"); continue
        if df is None or len(df) < 200:
            print(f"  {base:8s} SKIP insufficient history ({len(df) if df is not None else 0} bars)"); continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        cut = int(len(df)*0.70)
        is_df, oos_df = df.iloc[:cut], df.iloc[cut:]
        rec = {"symbol": r["symbol"], "yf": yf_t, "bars": len(df),
               "scan_conv": r["conviction_score"], "scan_signal": r["signal"]}
        any_pass = False
        for side in ("LONG", "SHORT"):
            is_r = backtest_hist(is_df, side)
            oos_r = backtest_hist(oos_df, side)
            rec[f"{side}_IS_PF"] = (is_r or {}).get("profit_factor")
            rec[f"{side}_IS_R"] = (is_r or {}).get("avg_R")
            rec[f"{side}_OS_PF"] = (oos_r or {}).get("profit_factor")
            rec[f"{side}_OS_R"] = (oos_r or {}).get("avg_R")
            rec[f"{side}_trades"] = (is_r or {}).get("trades", 0)
            if is_r and oos_r and is_r["profit_factor"] and is_r["profit_factor"] >= 1.0 and oos_r["profit_factor"] and oos_r["profit_factor"] >= 1.0:
                any_pass = True
        green = any(rec.get(f"{side}_IS_PF") and rec.get(f"{side}_OS_PF") and rec[f"{side}_IS_PF"] >= 1.0 and rec[f"{side}_OS_PF"] >= 1.0 for side in ("LONG", "SHORT"))
        rec["verdict"] = "GREEN_PROVEN" if green else ("AMBER_IS_ONLY" if any_pass else "RED")
        rows.append(rec)
        print(f"  {base:8s} {rec['verdict']:13s} LONG IS/OS PF={rec['LONG_IS_PF']}/{rec['LONG_OS_PF']} "
              f"SHORT IS/OS PF={rec['SHORT_IS_PF']}/{rec['SHORT_OS_PF']} (n={len(df)})")

    rows.sort(key=lambda x: 0 if x["verdict"] == "GREEN_PROVEN" else (1 if x["verdict"] == "AMBER_IS_ONLY" else 2))
    out = {"generated": __import__("datetime").datetime.utcnow().isoformat()+"Z",
           "proof_bar": "IS PF>=1.0 AND OOS PF>=1.0 on same side", "assets": rows}
    p = HOME / f"cerebro_crypto_backtest_{DATE}.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {p}  ({len(rows)} assets backtested)")
    green = [r for r in rows if r["verdict"] == "GREEN_PROVEN"]
    print(f"GREEN_PROVEN edges: {[r['symbol'] for r in green]}")


if __name__ == "__main__":
    main()
