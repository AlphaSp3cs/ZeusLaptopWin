#!/usr/bin/env python3
"""Walk-forward (out-of-sample) disprover for an FTMO-style swing system.

Reads ob_universe_data.json (cached 4y daily history). Runs the SAME params on two
disjoint windows and prints both pass rates. If OOS << in-sample, the system is
overfit -- that is the finding. No re-tuning on OOS.

Usage:
  python walk_forward.py            # uses cached json
  python walk_forward.py --force    # refetch 4y first (needs fetch_universe.py beside it)

Rules modeled (FTMO Phase 1): start 25000, target +8% in <=30d, 5% daily / 10% total loss.
Bookkeeping is the CORRECTED version: position opens at bar-k close, risked from k+1,
cash debited at entry, equity = cash + mark-to-market.
"""
import json, sys, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"C:\Users\victo")
RAW = json.loads((ROOT/"ob_universe_data.json").read_text())["data"]
tickers = {}
for t, d in RAW.items():
    if "error" in d: continue
    df = pd.DataFrame(d["history"]); df["date"]=pd.to_datetime(df["d"]); df=df.set_index("date").sort_index()
    d2 = d.copy(); d2["df"] = df; tickers[t] = d2
COMMON = None
for t,d in tickers.items():
    COMMON = d["df"].index if COMMON is None else COMMON.union(d["df"].index)
COMMON = COMMON.sort_values()
for t,d in tickers.items():
    d["df"] = d["df"].reindex(COMMON).ffill()
def ind(df):
    c=df["c"]; df=df.copy()
    df["sma20"]=c.rolling(20).mean(); df["sma50"]=c.rolling(50).mean(); df["sma200"]=c.rolling(200).mean()
    delta=c.diff(); up=delta.clip(lower=0).rolling(14).mean(); dn=(-delta.clip(upper=0)).rolling(14).mean()
    rs=up/dn.replace(0,np.nan); df["rsi"]=100-100/(1+rs); return df
for t,d in tickers.items(): d["df"]=ind(d["df"])
FRAME = {t:d for t,d in tickers.items() if d["df"]["c"].iloc[-1] > 15}

def breadth(k):
    n=a=0
    for t,d in FRAME.items():
        s=d["df"]["sma200"].values[k]; c=d["df"]["c"].values[k]
        if np.isnan(s): continue
        a+=1; n+= 1 if c>s else 0
    return (n/a) if a else 0.5
BREADTH=[breadth(k) for k in range(len(COMMON))]

START=25000.0; TARGET=START*1.08; TOTAL_LIM=START*0.90
REGIME_TH=0.50; HALT_PCT=0.03
P = {"max_pos":4,"risk_pct":0.03,"stop_pct":0.05,"target_pct":0.14,"timeout":25,"entry":"pullback"}

def run(s,e):
    cash=START; pos=[]; total_b=False; prev_eq=START; halted=False; halt_day=None
    def fr(d): return d["df"]
    def eq_of(positions,k):
        v=cash
        for p in positions: v+=p["shares"]*fr(FRAME[p["ticker"]])["c"].values[k]
        return v
    for k in range(s,e):
        day=COMMON[k].date()
        if halt_day!=day: halted=False; halt_day=day
        still=[]
        for p in pos:
            c=fr(FRAME[p["ticker"]])["c"].values[k]; l=fr(FRAME[p["ticker"]])["l"].values[k]; h=fr(FRAME[p["ticker"]])["h"].values[k]
            if l<=p["stop"]: cash+=p["shares"]*p["stop"]
            elif h>=p["target"]: cash+=p["shares"]*p["target"]
            elif p["held"]>=P["timeout"]: cash+=p["shares"]*c
            else: p["held"]+=1; still.append(p)
        pos=still
        eq=eq_of(pos,k)
        if (prev_eq-eq)/prev_eq >= HALT_PCT and not halted:
            halted=True
            for p in pos: cash+=p["shares"]*fr(FRAME[p["ticker"]])["c"].values[k]
            pos=[]
        if eq<TOTAL_LIM:
            total_b=True
            for p in pos: cash+=p["shares"]*fr(FRAME[p["ticker"]])["c"].values[k]
            pos=[]; break
        if eq>=TARGET: return True
        if not halted and BREADTH[k]>=REGIME_TH:
            for tk,d in FRAME.items():
                if len(pos)>=P["max_pos"]: break
                dd=fr(d); sma50=dd["sma50"].values[k]; sma200=dd["sma200"].values[k]; rsi=dd["rsi"].values[k]; c=dd["c"].values[k]; sma20=dd["sma20"].values[k]
                if np.isnan(sma50) or np.isnan(sma200) or np.isnan(rsi): continue
                if sma50>sma200 and 30<rsi<48 and c>0.97*sma50:
                    entry=c; stop=entry*(1-P["stop_pct"]); target=entry*(1+P["target_pct"]); shares=(P["risk_pct"]*eq)/(entry-stop)
                    cash-=shares*entry; pos.append({"ticker":tk,"shares":shares,"entry":entry,"stop":stop,"target":target,"held":0})
        prev_eq=eq
    for p in pos: cash+=p["shares"]*fr(FRAME[p["ticker"]])["c"].values[e-1]
    return cash>=TARGET

def window(name,a,b):
    ai=next(i for i,x in enumerate(COMMON) if x.date()>=a)
    bi=next((i for i,x in enumerate(COMMON) if x.date()>b), len(COMMON)-1)
    trials=passes=0
    for s in range(ai,bi-30,10):
        e=min(s+30,bi)
        if e-s<25: break
        trials+=1
        if run(s,e): passes+=1
    r=passes/trials*100 if trials else 0
    print(f"{name:26} pass_rate={r:5.1f}%  ({passes}/{trials})")
    return r

if __name__=="__main__":
    if "--force" in sys.argv:
        import subprocess; subprocess.run([sys.executable,"fetch_universe.py","--force"],cwd=ROOT)
        print("refetched; re-run without --force"); raise SystemExit(0)
    is_r = window("in_sample_2025_2026", dt.date(2025,5,1), dt.date(2026,8,7))
    os_r = window("out_of_sample_2022_2024", dt.date(2022,1,1), dt.date(2024,12,31))
    print(f"\nOOS gap = {is_r-os_r:.1f} pts  -> {'OVERFIT/regime-dependent' if os_r < is_r-5 else 'ok-ish'}")
