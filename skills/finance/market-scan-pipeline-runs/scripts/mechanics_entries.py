"""Mechanics-based entries — entries built on WHY price moves, not just
indicator conditions. Implements Drivers 1-4 from D:\\Hermes\\MARKET_MECHANICS.txt:

  D1 LIQUIDITY GRAB (stop-run reversal):
      sweep a prior swing low/high, then reject back inside + bullish/bearish
      candle. Entry next bar.
  D3 VWAP RECLAIM w/ VOLUME:
      close back through VWAP after being below, on volume > vol_mult * avg,
      with a directional candle.
  D4 EXHAUSTION (climax fade):
      volume spike (> vol_mult2 * avg) at extended RSI, with reversal candle.

DEPS: must sit next to robustness_proof.py (imports _load, _pf, _sig, rsi, atr,
vwap). Each trigger is proven via the same 3-test harness (walk-forward OOS,
param grid, t-test) reused from robustness_proof.
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

from robustness_proof import _load, _pf, _sig, rsi, atr, vwap

RR0, ATM0, MAX_BARS = 2.0, 2.0, 20


def _pivots(df, left=5, right=5):
    hi = df["High"]
    lo = df["Low"]
    sh = (hi == hi.rolling(2 * left + 1, center=True).max())
    sl = (lo == lo.rolling(2 * right + 1, center=True).min())
    return sh.fillna(False), sl.fillna(False)


def _trig_liqgrab(df, side, swing_window=20, atr_stop=2.0, rr=2.0):
    """Driver 1: liquidity grab / stop-run reversal."""
    n = len(df)
    sh, sl = _pivots(df, max(3, swing_window // 4), max(3, swing_window // 4))
    trades = []
    i = swing_window
    while i < n - 1:
        r = df.iloc[i]
        if side == "LONG":
            sw_lo = df["Low"].iloc[max(0, i - swing_window):i].min()
            swept = r.Low < sw_lo
            rej = r.Close > sw_lo and r.Close > r.Open
            cond = swept and rej and r.atr > 0
        else:
            sw_hi = df["High"].iloc[max(0, i - swing_window):i].max()
            swept = r.High > sw_hi
            rej = r.Close < sw_hi and r.Close < r.Open
            cond = swept and rej and r.atr > 0
        if not cond:
            i += 1
            continue
        entry = float(df.iloc[i + 1]["Open"])
        risk = atr_stop * float(r.atr)
        sl_, tp = (entry - risk, entry + rr * risk) if side == "LONG" \
            else (entry + risk, entry - rr * risk)
        out, bars = None, 0
        for j in range(i + 1, min(i + 1 + MAX_BARS, n)):
            b = df.iloc[j]
            bars = j - i
            if side == "LONG":
                if b.Low <= sl_:
                    out = -1.0
                    break
                if b.High >= tp:
                    out = rr
                    break
            else:
                if b.High >= sl_:
                    out = -1.0
                    break
                if b.Low <= tp:
                    out = rr
                    break
        if out is None:
            last = float(df.iloc[min(i + MAX_BARS, n - 1)]["Close"])
            out = ((last - entry) if side == "LONG" else (entry - last)) / risk
        trades.append(out)
        i += bars + 1
    return trades


def _trig_reclaim(df, side, vol_mult=1.5, atr_stop=2.0, rr=2.0):
    """Driver 3: VWAP reclaim with volume acceptance."""
    n = len(df)
    df = df.copy()
    df["vol_avg"] = df["Volume"].rolling(20).mean()
    trades = []
    i = 20
    while i < n - 1:
        r = df.iloc[i]
        if r.atr <= 0:
            i += 1
            continue
        if side == "LONG":
            below = df["Close"].iloc[i - 1] < df["vwap"].iloc[i - 1]
            reclaim = r.Close > r.vwap and r.Close > r.Open
            vol_ok = r.Volume > vol_mult * r.vol_avg
            cond = below and reclaim and vol_ok
        else:
            above = df["Close"].iloc[i - 1] > df["vwap"].iloc[i - 1]
            reclaim = r.Close < r.vwap and r.Close < r.Open
            vol_ok = r.Volume > vol_mult * r.vol_avg
            cond = above and reclaim and vol_ok
        if not cond:
            i += 1
            continue
        entry = float(df.iloc[i + 1]["Open"])
        risk = atr_stop * float(r.atr)
        sl_, tp = (entry - risk, entry + rr * risk) if side == "LONG" \
            else (entry + risk, entry - rr * risk)
        out, bars = None, 0
        for j in range(i + 1, min(i + 1 + MAX_BARS, n)):
            b = df.iloc[j]
            bars = j - i
            if side == "LONG":
                if b.Low <= sl_:
                    out = -1.0
                    break
                if b.High >= tp:
                    out = rr
                    break
            else:
                if b.High >= sl_:
                    out = -1.0
                    break
                if b.Low <= tp:
                    out = rr
                    break
        if out is None:
            last = float(df.iloc[min(i + MAX_BARS, n - 1)]["Close"])
            out = ((last - entry) if side == "LONG" else (entry - last)) / risk
        trades.append(out)
        i += bars + 1
    return trades


def _trig_exhaust(df, side, vol_mult2=2.5, atr_stop=2.0, rr=2.0):
    """Driver 4: exhaustion / climax fade."""
    n = len(df)
    df = df.copy()
    df["vol_avg"] = df["Volume"].rolling(20).mean()
    trades = []
    i = 20
    while i < n - 1:
        r = df.iloc[i]
        if r.atr <= 0:
            i += 1
            continue
        spike = r.Volume > vol_mult2 * r.vol_avg
        if side == "LONG":
            ext = r.rsi < 35
            rev = r.Close > r.Open
            cond = spike and ext and rev
        else:
            ext = r.rsi > 65
            rev = r.Close < r.Open
            cond = spike and ext and rev
        if not cond:
            i += 1
            continue
        entry = float(df.iloc[i + 1]["Open"])
        risk = atr_stop * float(r.atr)
        sl_, tp = (entry - risk, entry + rr * risk) if side == "LONG" \
            else (entry + risk, entry - rr * risk)
        out, bars = None, 0
        for j in range(i + 1, min(i + 1 + MAX_BARS, n)):
            b = df.iloc[j]
            bars = j - i
            if side == "LONG":
                if b.Low <= sl_:
                    out = -1.0
                    break
                if b.High >= tp:
                    out = rr
                    break
            else:
                if b.High >= sl_:
                    out = -1.0
                    break
                if b.Low <= tp:
                    out = rr
                    break
        if out is None:
            last = float(df.iloc[min(i + MAX_BARS, n - 1)]["Close"])
            out = ((last - entry) if side == "LONG" else (entry - last)) / risk
        trades.append(out)
        i += bars + 1
    return trades


TRIGGERS = {"D1_liqgrab": _trig_liqgrab, "D3_reclaim": _trig_reclaim, "D4_exhaust": _trig_exhaust}


def prove_trigger(sym, side, trig_name):
    side = side.upper()
    df = _load(sym)
    if df is None:
        return {"symbol": sym, "side": side, "trigger": trig_name, "error": "no data"}
    fn = TRIGGERS[trig_name]
    cut = int(len(df) * 0.6)
    tr_t = fn(df.iloc[:cut], side)
    te_t = fn(df.iloc[cut:], side)
    pf_is, pf_oos = _pf(tr_t), _pf(te_t)
    grid_total = 0
    grid_pass = 0
    for sw in (10, 20, 30):
        for vm in (1.3, 1.5, 2.0):
            for a in (1.5, 2.0, 2.5):
                for rr in (1.5, 2.0, 2.5):
                    grid_total += 1
                    if trig_name == "D1_liqgrab":
                        g = fn(df, side, swing_window=sw, atr_stop=a, rr=rr)
                    elif trig_name == "D3_reclaim":
                        g = fn(df, side, vol_mult=vm, atr_stop=a, rr=rr)
                    else:
                        g = fn(df, side, vol_mult2=vm, atr_stop=a, rr=rr)
                    p = _pf(g)
                    if p is not None and p >= 1.0:
                        grid_pass += 1
    grid_ok = grid_pass / grid_total >= 0.5
    sig = _sig(fn(df, side))
    oos_ok = pf_oos is not None and pf_oos >= 1.0
    is_ok = pf_is is not None and pf_is >= 1.0
    sig_ok = sig["p"] is not None and sig["p"] < 0.05
    green = is_ok and oos_ok and grid_ok and sig_ok
    return {
        "symbol": sym, "side": side, "trigger": trig_name,
        "pf_in_sample": pf_is, "pf_out_of_sample": pf_oos,
        "oos_pf_ok": oos_ok, "is_pf_ok": is_ok,
        "grid_pass": f"{grid_pass}/{grid_total}", "grid_ok": grid_ok,
        "sig_t": sig["t"], "sig_p": sig["p"], "sig_n": sig["n"], "sig_ok": sig_ok,
        "verdict": "GREEN_PROVEN" if green else "NOT_PROVEN",
        "failed": [k for k, v in
                   {"in_sample_PF>=1": is_ok, "out_of_sample_PF>=1": oos_ok,
                    "grid_majority_PF>=1": grid_ok, "t_test_p<0.05": sig_ok}.items() if not v],
    }


if __name__ == "__main__":
    import sys
    syms = sys.argv[1].split(",")
    sides = sys.argv[2].split(",")
    out = []
    for s, sd in zip(syms, sides):
        for tn in TRIGGERS:
            out.append(prove_trigger(s, sd, tn))
    print(json.dumps(out, indent=2))
