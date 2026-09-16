#!/usr/bin/env python3
"""Real FX setup scanner: intraday + swing plans with entry/SL/TP.
BASIS: SPOT FX via yfinance interbank/retail-CFD proxy (<PAIR>=X). NOT futures.
blogwatcher RSS sentiment is crypto-only (BTC/ETH/SOL); per-symbol FX layer = N/A.

Verified working 2026-08-05. Edit PAIRS / PRIOR below per request.
Method: structure swing extremes + ATR, TP = entry +/- k*risk (k=1.5, 2.5).
Rounding: JPY->3dp, else 5dp. SL/TP sign-correct for each direction.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# (ticker, label, direction) -- direction in {"buy","sell"}
PAIRS = [
    ("EURUSD=X", "EUR/USD", "sell"),
    ("USDCHF=X", "USD/CHF", "buy"),
    ("GBPCAD=X", "GBP/CAD", "buy"),
    ("NZDJPY=X", "NZD/JPY", "buy"),
]
# prior fx majors to re-check, bias auto from intraday close vs 20-bar ago
PRIOR = [
    ("GBPUSD=X", "GBP/USD"), ("USDJPY=X", "USD/JPY"), ("AUDUSD=X", "AUD/USD"),
    ("USDCAD=X", "USD/CAD"), ("NZDUSD=X", "NZD/USD"),
]


def dl(tkr, interval, period):
    try:
        df = yf.download(tkr, interval=interval, period=period, progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel(1, axis=1)
        return df
    except Exception as e:
        return None


def atr(high, low, close, n=14):
    tr = np.maximum(np.abs(high[1:]-low[1:]),
                    np.maximum(np.abs(high[1:]-close[:-1]), np.abs(low[1:]-close[:-1])))
    tr = np.concatenate([[np.nan], tr])
    a = np.full(len(tr), np.nan)
    a[n] = np.nanmean(tr[1:n+1])
    for i in range(n+1, len(tr)):
        a[i] = (a[i-1]*(n-1)+tr[i])/n
    return a


def swings(high, low, look=3):
    sh, sl = [], []
    for i in range(look, len(high)-look):
        if all(high[i] >= high[i-j] for j in range(1, look+1)) and all(high[i] >= high[i+j] for j in range(1, look+1)):
            sh.append(i)
        if all(low[i] <= low[i-j] for j in range(1, look+1)) and all(low[i] <= low[i+j] for j in range(1, look+1)):
            sl.append(i)
    return sh, sl


def dec(p, jpy):
    return round(p, 3 if jpy else 5)


def build(tkr, label, direction, d, h):
    jpy = "JPY" in label
    out = {"label": label, "dir": direction.upper(), "tkr": tkr}
    if h is None or len(h) < 50 or d is None or len(d) < 30:
        out["err"] = "insufficient data"; return out
    hc = np.array(h["Close"].astype(float)); hh = np.array(h["High"].astype(float)); hl = np.array(h["Low"].astype(float))
    dc = np.array(d["Close"].astype(float)); dh = np.array(d["High"].astype(float)); dl = np.array(d["Low"].astype(float))
    cur = float(hc[-1]); hatr = float(atr(hh, hl, hc)[-1])
    datr = float(atr(dh, dl, dc)[-1])
    sh, sl = swings(hh, hl, 4)
    sh, sl = [i for i in sh if i > len(hh)-60], [i for i in sl if i > len(hh)-60]
    ih = max([hh[i] for i in sh], default=float(np.max(hh[-40:])))
    il = min([hl[i] for i in sl], default=float(np.min(hl[-40:])))
    dd = dl.shape[0]
    dsh_s, dsl_s = swings(dh, dl, 2)
    dsh_s, dsl_s = [i for i in dsh_s if i > dd-30], [i for i in dsl_s if i > dd-30]
    dhi = [dh[i] for i in dsh_s]; dli = [dl[i] for i in dsl_s]
    d_high = max(dhi, default=float(np.max(dh[-20:]))); d_low = min(dli, default=float(np.min(dl[-20:])))
    out.update(cur=cur, hatr=hatr, ih=ih, il=il, d_high=d_high, d_low=d_low)

    # ---- INTRADAY (1h structure) ----
    if direction == "sell":
        entry = dec(min(cur, ih - 0.2*hatr), jpy)
        sl = dec(ih + 0.6*hatr, jpy); risk = sl - entry
        tp1 = dec(entry - 1.5*risk, jpy); tp2 = dec(entry - 2.5*risk, jpy)
        pb = dec(cur - 0.5*hatr, jpy)
    else:
        entry = dec(max(cur, il + 0.2*hatr), jpy)
        sl = dec(il - 0.6*hatr, jpy); risk = entry - sl
        tp1 = dec(entry + 1.5*risk, jpy); tp2 = dec(entry + 2.5*risk, jpy)
        pb = dec(cur + 0.5*hatr, jpy)
    out["intra"] = dict(entry=entry, pb=pb, sl=sl, risk=dec(abs(risk), jpy),
                        tp1=tp1, tp2=tp2, rr=round(abs(tp1-entry)/abs(risk), 2))

    # ---- SWING (daily structure, ATR-multiple off current) ----
    if direction == "sell":
        res = max([x for x in dhi if x >= cur*0.999], default=d_high)
        s_entry = dec(min(cur, res - 0.2*datr), jpy)
        s_sl = dec(res + 0.5*datr, jpy); srisk = s_sl - s_entry
        tp_below = sorted([x for x in dli if x < cur], reverse=True)
        stp1 = dec(tp_below[0], jpy) if tp_below else dec(s_entry - 2*srisk, jpy)
        stp2 = dec(tp_below[1], jpy) if len(tp_below) > 1 else dec(s_entry - 3.5*srisk, jpy)
    else:
        sup = min([x for x in dli if x <= cur*1.001], default=d_low)
        s_entry = dec(max(cur, sup + 0.2*datr), jpy)
        s_sl = dec(sup - 0.5*datr, jpy); srisk = s_entry - s_sl
        tp_above = sorted([x for x in dhi if x > cur])
        stp1 = dec(tp_above[0], jpy) if tp_above else dec(s_entry + 2*srisk, jpy)
        stp2 = dec(tp_above[1], jpy) if len(tp_above) > 1 else dec(s_entry + 3.5*srisk, jpy)
    out["swing"] = dict(entry=s_entry, sl=s_sl, risk=dec(abs(srisk), jpy),
                        tp1=stp1, tp2=stp2,
                        rr1=round(abs(stp1-s_entry)/abs(srisk), 2),
                        rr2=round(abs(stp2-s_entry)/abs(srisk), 2))
    return out


def fmt(r):
    if "err" in r:
        return f"  {r['label']}: {r['err']}"
    L = [f"  {r['label']} {r['dir']}   |  spot last = {r['cur']}   |  1h ATR = {r['hatr']}"]
    L.append(f"    intraday structure: H {r['ih']}  L {r['il']}   |   daily range: H {r['d_high']}  L {r['d_low']}")
    i = r["intra"]
    L.append(f"    [INTRADAY] entry {i['entry']}  (pullback limit {i['pb']})  SL {i['sl']}  risk {i['risk']}")
    L.append(f"              TP1 {i['tp1']}  TP2 {i['tp2']}   R:R {i['rr']}")
    s = r["swing"]
    L.append(f"    [SWING]    entry {s['entry']}  SL {s['sl']}  risk {s['risk']}")
    L.append(f"              TP1 {s['tp1']} (R:R {s['rr1']})   TP2 {s['tp2']} (R:R {s['rr2']})")
    return "\n".join(L)


if __name__ == "__main__":
    print(f"FX SETUPS  |  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  |  BASIS: SPOT FX proxy (yfinance interbank/retail-CFD)")
    print("NOTE: blogwatcher RSS sentiment is crypto-only (BTC/ETH/SOL); per-symbol FX sentiment layer = N/A.\n")
    print("=== REQUESTED SETUPS ===")
    for tkr, label, direction in PAIRS:
        r = build(tkr, label, direction, dl(tkr, "1d", "3mo"), dl(tkr, "1h", "5d"))
        print(fmt(r)); print()
    print("=== PRIOR FX MAJORS (re-checked, auto intraday bias) ===")
    for tkr, label in PRIOR:
        d = dl(tkr, "1d", "3mo"); h = dl(tkr, "1h", "5d")
        if h is None or len(h) < 30:
            print(f"  {label}: no data"); continue
        hc = np.array(h["Close"].astype(float))
        bias = "buy" if hc[-1] > hc[-20] else "sell"
        r = build(tkr, label, bias, d, h)
        print(fmt(r)); print()
