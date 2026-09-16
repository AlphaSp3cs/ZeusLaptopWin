#!/usr/bin/env python3
"""Bar-by-bar single-run tracer for one challenge trial.
Use this to catch a fake backtest before trusting the aggregate number:
  * if equity jumps past target on day 1 -> same-bar look-ahead
  * if a losing stop shows a profit -> cash not debited at entry
Run:  python3 debug_single_run.py   (edits s=200 inside for the first trial)
"""
import json
from pathlib import Path
import numpy as np, pandas as pd
from honest_backtest import load_frame, run_challenge  # reuse cached loader

FRAME, COMMON = load_frame()
all_idx=list(COMMON)
P={"max_pos":3,"risk_pct":0.01,"stop_pct":0.04,"target_pct":0.10,"timeout":20,"entry":"pullback"}
s=200; e=min(s+30, len(all_idx)-1)
print(f"trial {all_idx[s].date()} -> {all_idx[e].date()}")
# instrumented copy: print each bar
cash=25000.0; pos=[]; prev_eq=25000.0
def frame(d): return d["df"]
for k in range(s,e):
    still=[]
    for p in pos:
        c=frame(FRAME[p["ticker"]])["c"].values[k]; l=frame(FRAME[p["ticker"]])["l"].values[k]; h=frame(FRAME[p["ticker"]])["h"].values[k]
        if l<=p["stop"]: cash+=p["shares"]*p["stop"]; print(f"  k={k} {p['ticker']} STOP")
        elif h>=p["target"]: cash+=p["shares"]*p["target"]; print(f"  k={k} {p['ticker']} TGT win ${p['shares']*(p['target']-p['entry']):.0f}")
        elif p["held"]>=P["timeout"]: cash+=p["shares"]*c; print(f"  k={k} {p['ticker']} TIMEOUT")
        else: p["held"]+=1; still.append(p)
    pos=still
    eq=cash
    for p in pos: eq+=p["shares"]*frame(FRAME[p["ticker"]])["c"].values[k]
    if eq<prev_eq*0.95:
        print(f"  k={k} DAILY BREACH eq={eq:.0f}"); break
    if eq<22500.0:
        print(f"  k={k} TOTAL BREACH eq={eq:.0f}"); break
    if eq>=27000.0:
        print(f"  k={k} TARGET HIT eq={eq:.0f}"); break
    for tk,d in FRAME.items():
        if len(pos)>=P["max_pos"]: break
        dd=frame(d); sma50=dd["sma50"].values[k]; sma200=dd["sma200"].values[k]; rsi=dd["rsi"].values[k]; c=dd["c"].values[k]; sma20=dd["sma20"].values[k]
        if np.isnan(sma50) or np.isnan(sma200) or np.isnan(rsi): continue
        if sma50>sma200 and 30<rsi<48 and c>0.97*sma50:
            entry=c; stop=entry*(1-P["stop_pct"]); target=entry*(1+P["target_pct"]); shares=(P["risk_pct"]*eq)/(entry-stop)
            cash-=shares*entry
            pos.append({"ticker":tk,"shares":shares,"entry":entry,"stop":stop,"target":target,"held":0})
            print(f"  k={k} ENTRY {tk} @ {entry:.2f} shares={shares:.1f} risk=${shares*(entry-stop):.0f}")
    print(f"-- bar {k} end: eq={eq:.0f} open={[p['ticker'] for p in pos]}")
    prev_eq=eq
for p in pos: cash+=p["shares"]*frame(FRAME[p["ticker"]])["c"].values[e-1]
print("FINAL eq", round(cash,2), "pass?", cash>=27000.0)
