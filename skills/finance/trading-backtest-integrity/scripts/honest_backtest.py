#!/usr/bin/env python3
"""Parameterized FTMO-style backtest with HONEST bookkeeping.
Use this instead of hand-rolling a sim — the two classic fake-win bugs are already fixed:
  * entry at bar-k close, risked from bar k+1 (no same-bar look-ahead)
  * cash debited at entry, equity = cash + mark-to-market
Run:  python3 honest_backtest.py
Requires: pandas, numpy, yfinance; daily history cached to ob_universe_data.json (<24h reuse).
"""
import json, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
import yfinance as yf

DATA = Path(r"C:\Users\victo\ob_universe_data.json")

def load_frame(price_min=15.0):
    if DATA.exists():
        raw = json.loads(DATA.read_text())["data"]
    else:
        raise SystemExit("ob_universe_data.json missing; run fetch_universe.py first")
    tickers = {}
    for t, d in raw.items():
        if "error" in d:
            continue
        df = pd.DataFrame(d["history"]); df["date"] = pd.to_datetime(df["d"])
        df = df.set_index("date").sort_index()
        d2 = d.copy(); d2["df"] = df; tickers[t] = d2
    COMMON = None
    for d in tickers.values():
        COMMON = d["df"].index if COMMON is None else COMMON.union(d["df"].index)
    COMMON = COMMON.sort_values()
    for d in tickers.values():
        d["df"] = d["df"].reindex(COMMON).ffill()
    def ind(df):
        c = df["c"]; df = df.copy()
        df["sma20"] = c.rolling(20).mean(); df["sma50"] = c.rolling(50).mean(); df["sma200"] = c.rolling(200).mean()
        delta = c.diff(); up = delta.clip(lower=0).rolling(14).mean(); dn = (-delta.clip(upper=0)).rolling(14).mean()
        rs = up / dn.replace(0, np.nan); df["rsi"] = 100 - 100/(1+rs); return df
    for d in tickers.values():
        d["df"] = ind(d["df"])
    return {t: d for t, d in tickers.items() if d["df"]["c"].iloc[-1] > price_min}, COMMON

START=25000.0; TARGET=START*1.08; TOTAL_LIM=START*0.90

def run_challenge(df_univ, s, e, P):
    MAX_POS=P["max_pos"]; RISK=P["risk_pct"]; STOP=P["stop_pct"]; TGT=P["target_pct"]
    TIMEOUT=P["timeout"]; ENTRY=P["entry"]
    cash=START; pos=[]; daily_b=False; total_b=False; prev_eq=START
    def frame(d): return d["df"]
    def eq_of(positions, k):
        v=cash
        for p in positions: v+=p["shares"]*frame(df_univ[p["ticker"]])["c"].values[k]
        return v
    for k in range(s, e):
        still=[]
        for p in pos:
            c=frame(df_univ[p["ticker"]])["c"].values[k]; l=frame(df_univ[p["ticker"]])["l"].values[k]; h=frame(df_univ[p["ticker"]])["h"].values[k]
            if l<=p["stop"]: cash+=p["shares"]*p["stop"]
            elif h>=p["target"]: cash+=p["shares"]*p["target"]
            elif p["held"]>=TIMEOUT: cash+=p["shares"]*c
            else: p["held"]+=1; still.append(p)
        pos=still
        eq=eq_of(pos,k)
        if eq<prev_eq*0.95:
            daily_b=True
            for p in pos: cash+=p["shares"]*frame(df_univ[p["ticker"]])["c"].values[k]
            pos=[]; break
        if eq<TOTAL_LIM:
            total_b=True
            for p in pos: cash+=p["shares"]*frame(df_univ[p["ticker"]])["c"].values[k]
            pos=[]; break
        if eq>=TARGET: return {"pass":True,"eq":eq,"reason":"target","days":k-s}
        for tk,d in df_univ.items():
            if len(pos)>=MAX_POS: break
            dd=frame(d); sma50=dd["sma50"].values[k]; sma200=dd["sma200"].values[k]; rsi=dd["rsi"].values[k]; c=dd["c"].values[k]; sma20=dd["sma20"].values[k]
            if np.isnan(sma50) or np.isnan(sma200) or np.isnan(rsi): continue
            sig=False
            if ENTRY=="pullback" and sma50>sma200 and 30<rsi<48 and c>0.97*sma50: sig=True
            elif ENTRY=="momentum" and sma50>sma200 and c>sma20 and 55<rsi<75: sig=True
            if sig:
                entry=c; stop=entry*(1-STOP); target=entry*(1+TGT); shares=(RISK*eq)/(entry-stop)
                cash-=shares*entry
                pos.append({"ticker":tk,"shares":shares,"entry":entry,"stop":stop,"target":target,"held":0})
        prev_eq=eq
    for p in pos: cash+=p["shares"]*frame(df_univ[p["ticker"]])["c"].values[e-1]
    eq=cash
    reason="target" if eq>=TARGET else ("daily_breach" if daily_b else ("total_breach" if total_b else "timeout_no_target"))
    return {"pass":eq>=TARGET,"eq":eq,"reason":reason,"days":e-s}

if __name__=="__main__":
    FRAME, COMMON = load_frame()
    all_idx=list(COMMON)
    variants={
        "v1_pullback_1pct":{"max_pos":3,"risk_pct":0.01,"stop_pct":0.04,"target_pct":0.10,"timeout":20,"entry":"pullback"},
        "v4_pullback_3pct":{"max_pos":4,"risk_pct":0.03,"stop_pct":0.05,"target_pct":0.14,"timeout":25,"entry":"pullback"},
    }
    for vn,P in variants.items():
        trials=passes=0; reasons={}
        for s in range(200, len(all_idx)-30, 10):
            e=min(s+30, len(all_idx)-1)
            if e-s<25: break
            r=run_challenge(FRAME, s, e, P); trials+=1
            if r["pass"]: passes+=1
            reasons[r["reason"]]=reasons.get(r["reason"],0)+1
        print(f"{vn}: pass {passes}/{trials} ({round(passes/trials*100,1)}%)  {reasons}")
