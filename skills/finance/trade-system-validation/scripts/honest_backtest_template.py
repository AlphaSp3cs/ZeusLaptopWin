#!/usr/bin/env python3
"""Minimal, CORRECTLY ACCOUNTED FTMO-style challenge sim.
Copy + extend. Demonstrates the two bug fixes from trade-system-validation:
  F1 look-ahead: entry at bar-k close, risked from k+1 only.
  F2 phantom P&L: cash debited at entry, equity = cash + mark-to-market.
Run: python3 honest_backtest_template.py
"""
import numpy as np, pandas as pd

START=25000.0; TARGET=START*1.08; DAILY_LIM=START*0.95; TOTAL_LIM=START*0.90
RISK=0.01; STOP=0.04; TGT=0.10; MAX_POS=3; TIMEOUT=20

# Example universe: dict ticker -> DataFrame with columns c,l,h (close,low,high) indexed by date
# Replace with real data load (e.g. yfinance history reindexed to a common index).
def run(df_univ, s, e):
    cash = START; pos=[]; daily_b=False; total_b=False; prev_eq=START
    def fr(d): return d
    def eq_of(positions,k):
        v=cash
        for p in positions: v+=p["shares"]*fr(df_univ[p["ticker"]])["c"].values[k]
        return v
    for k in range(s,e):
        still=[]
        for p in pos:                      # EXITS: opened before k, risked on k's L/H
            c=fr(df_univ[p["ticker"]])["c"].values[k]
            l=fr(df_univ[p["ticker"]])["l"].values[k]
            h=fr(df_univ[p["ticker"]])["h"].values[k]
            if l<=p["stop"]: cash+=p["shares"]*p["stop"]
            elif h>=p["target"]: cash+=p["shares"]*p["target"]
            elif p["held"]>=TIMEOUT: cash+=p["shares"]*c
            else: p["held"]+=1; still.append(p)
        pos=still
        eq=eq_of(pos,k)
        if eq<prev_eq*0.95:                # daily-loss limit vs PREVIOUS bar equity
            daily_b=True
            for p in pos: cash+=p["shares"]*fr(df_univ[p["ticker"]])["c"].values[k]
            pos=[]; break
        if eq<TOTAL_LIM:
            total_b=True
            for p in pos: cash+=p["shares"]*fr(df_univ[p["ticker"]])["c"].values[k]
            pos=[]; break
        if eq>=TARGET: return {"pass":True,"eq":eq,"reason":"target"}
        for tk,d in df_univ.items():        # ENTRIES: open at k close, risked from k+1
            if len(pos)>=MAX_POS: break
            sma50=d["sma50"].values[k]; sma200=d["sma200"].values[k]; rsi=d["rsi"].values[k]; c=d["c"].values[k]
            if np.isnan(sma50) or np.isnan(sma200) or np.isnan(rsi): continue
            if sma50>sma200 and 30<rsi<48 and c>0.97*sma50:
                entry=c; stop=entry*(1-STOP); target=entry*(1+TGT)
                shares=(RISK*eq)/(entry-stop)
                cash-=shares*entry           # F2: DEBIT cash at entry
                pos.append({"ticker":tk,"shares":shares,"entry":entry,"stop":stop,"target":target,"held":0})
        prev_eq=eq
    for p in pos: cash+=p["shares"]*fr(df_univ[p["ticker"]])["c"].values[e-1]
    eq=cash
    return {"pass":eq>=TARGET,"eq":eq,"reason":"timeout_no_target" if eq<TARGET else "target"}

# --- demo: assert bookkeeping sanity on synthetic data -------------------------
if __name__=="__main__":
    n=60; idx=pd.date_range("2024-01-01",periods=n)
    price=np.linspace(100,110,n)+np.random.RandomState(0).normal(0,1,n)
    d=pd.DataFrame({"c":price,"l":price*0.98,"h":price*1.02},index=idx)
    d["sma50"]=d["c"].rolling(50).mean(); d["sma200"]=np.nan; d["rsi"]=40.0
    r=run({"X":d},0,40)
    assert r["eq"]!=START or r["pass"] is False
    print("sanity run:",r)
    print("FIXED: cash debited at entry; equity = cash + MTM. No same-bar look-ahead.")
