#!/usr/bin/env python3
"""
GOLD 5-MIN EDGE PROOF — 3-test bar, NO lookahead.

Strategy = the recommended capital.com 5-min XAUUSD set:
  Core:   24h-rolling VWAP, EMA21, EMA50, RSI14, ATR14
  Confirm: relative volume (vol / 20-bar avg) > threshold
  Filter:  entries only in London (02:00-05:00 ET) or NY (08:30-11:00 ET)
  Sizing:  stop = stop_mult*ATR; target = entry + rr*stop_distance; R:R = rr
  Cost:    net a measured capital.com round-trip of $5/oz (spread 0.06% @ ~$4316)

DATA HORIZON CAVEAT (critical): yfinance caps gold 5m at the LAST 60 DAYS.
It rejects anything older with "5m data not available ... must be within the
last 60 days." So this is NOT a 10y test — it is the maximal HONEST window from
this source. Stated plainly in the output. A real 10y 5m proof needs a paid
intraday vendor (Polygon, Databento, capital.com history).

Proof bar (escalated "prove profitable all we can"):
  T1  IS  PF >= 1.0   (full 60d window, net of cost)
  T2  OOS PF >= 1.0   (walk-forward: hold out last 1/3, test on unseen tail)
  T3  param grid >= 50% of combos PF >= 1.0 (robustness to tuning)
  T4  per-trade returns one-sample t-test p < 0.05 (statistical significance)

RESULT 2026-08-06 (calibration, not a market rule):
  Realistic VWAP-bounce trigger -> 25 trades / 60d, PF 0.38, 62% losers,
  t-test p=0.029 (PASS = negative edge is statistically RELIABLE, i.e. loses).
  VERDICT: NOT PROVEN. Do NOT trade this set on capital.com.
  Why: 0.06% gold spread (~$5/oz RT) vs ~$10/oz 5m ATR = ~half a bar of range
  paid in cost every round trip; 1.5xATR stop / 2xATR target too tight for the
  noise. Capital.com 5m gold is a cost trap for mean-reversion.

Usage:  python3 gold_5m_proof.py   (writes gold_5m_proof.json)
"""
import json, os
import numpy as np
import pandas as pd
from scipy import stats

COST_PER_OZ = 5.0          # capital.com gold round-trip (spread 0.06% @ ~4316)
MAX_HOLD_BARS = 288        # 1 trading day (5m x 288)
SESSIONS = [("london", (2,0,5,0)), ("ny", (8,30,11,0))]  # (sh,sm,eh,em) ET

def ema(s, n):
    return pd.Series(s).ewm(span=n, adjust=False).mean().to_numpy()

def rsi(s, n=14):
    s = pd.Series(s, dtype=float)
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up/(dn+1e-9)
    return (100 - 100/(1+rs)).to_numpy()

def atr(h, l, c, n=14):
    h, l, c = pd.Series(h), pd.Series(l), pd.Series(c)
    pc = c.shift(1)
    tr = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean().to_numpy()

def vwap_rolling(h, l, c, v, n=288):
    typ = (h+l+c)/3
    tv = typ*v
    roll_tv = pd.Series(tv).rolling(n).sum().to_numpy()
    roll_v = pd.Series(v).rolling(n).sum().to_numpy()
    return np.where(roll_v>0, roll_tv/roll_v, np.nan)

def in_session(ts_et):
    t = ts_et.hour*60 + ts_et.minute
    for _, (sh,sm,eh,em) in SESSIONS:
        if sh*60+sm <= t < eh*60+em:
            return True
    return False

def backtest(df, ema_fast, ema_slow, stop_mult, rr, rsi_lo, rsi_hi, relvol_thr):
    c = np.asarray(df["Close"]).ravel().astype(float)
    h = np.asarray(df["High"]).ravel().astype(float)
    l = np.asarray(df["Low"]).ravel().astype(float)
    v = np.asarray(df["Volume"]).ravel().astype(float)
    N = len(c)
    ema_f = ema(c, ema_fast); ema_s = ema(c, ema_slow)
    r = rsi(c, 14); a = atr(h, l, c, 14)
    vw = vwap_rolling(h, l, c, v, 288)
    vol_avg = pd.Series(v).rolling(20).mean().to_numpy()
    relvol = np.where(vol_avg>0, v/vol_avg, 1.0)
    sess = np.array([in_session(t) for t in df.index])
    trades = []
    pos = 0; entry = stop = tgt = 0.0; entry_i = 0
    for i in range(2, N-1):
        if pos == 0:
            uptrend = (c[i] > ema_f[i]) and (ema_f[i] > ema_s[i])
            dntrend = (c[i] < ema_f[i]) and (ema_f[i] < ema_s[i])
            above_vwap = c[i] > vw[i]; below_vwap = c[i] < vw[i]
            pinned = abs(c[i]-vw[i])/c[i] < 0.004
            vwap_tag = (l[i] <= vw[i]) and (c[i] >= vw[i])
            vwap_tag_dn = (h[i] >= vw[i]) and (c[i] <= vw[i])
            rsi_ok = (r[i] >= rsi_lo) and (r[i] <= rsi_hi)
            rsi_turn_up = r[i] > r[i-1]; rsi_turn_dn = r[i] < r[i-1]
            vol_ok = relvol[i] > relvol_thr
            if sess[i] and uptrend and above_vwap and (pinned or vwap_tag) and rsi_ok and rsi_turn_up and vol_ok:
                pos = 1
            elif sess[i] and dntrend and below_vwap and (pinned or vwap_tag_dn) and rsi_ok and rsi_turn_dn and vol_ok:
                pos = -1
            else:
                continue
            entry = c[i+1]; sd = stop_mult * a[i]
            stop = entry - sd if pos == 1 else entry + sd
            tgt = entry + rr*sd if pos == 1 else entry - rr*sd
            entry_i = i+1
        else:
            for j in range(entry_i, min(entry_i+MAX_HOLD_BARS, N)):
                if pos == 1:
                    if l[j] <= stop: trades.append((stop-entry)-COST_PER_OZ); pos=0; break
                    if h[j] >= tgt: trades.append((tgt-entry)-COST_PER_OZ); pos=0; break
                else:
                    if h[j] >= stop: trades.append((entry-stop)-COST_PER_OZ); pos=0; break
                    if l[j] <= tgt: trades.append((entry-tgt)-COST_PER_OZ); pos=0; break
            if pos != 0:
                trades.append((c[min(entry_i+MAX_HOLD_BARS,N-1)]-entry)*pos - COST_PER_OZ); pos=0
    return np.array(trades, dtype=float)

def pf(trades):
    if len(trades)==0: return 0.0, 0, 0
    gp = trades[trades>0].sum(); gl = -trades[trades<0].sum()
    pf_ = (gp/gl) if gl>0 else float("inf")
    return pf_, int((trades>0).sum()), int((trades<0).sum())

def main():
    import yfinance as yf
    df = yf.download("GC=F", period="60d", interval="5m", auto_adjust=False, progress=False)
    df = df.dropna()
    N = len(df)
    base = dict(ema_fast=21, ema_slow=50, stop_mult=1.5, rr=2.0, rsi_lo=40, rsi_hi=60, relvol_thr=1.2)
    t_is = backtest(df, **base); pf_is, w, lo = pf(t_is)
    cut = int(N*2/3); df_te = df.iloc[cut:]
    t_oos = backtest(df_te, **base); pf_oos, w2, lo2 = pf(t_oos)
    grid = [(ef,50,sm,rr,rlo,60,rv) for ef in (13,21,34) for sm in (1.0,1.5,2.0)
            for rr in (1.5,2.0,2.5) for rlo in (35,40,45) for rv in (1.15,1.2)]
    pass_n = sum(1 for g in grid if (lambda p: p>=1.0 and len(t:=backtest(df,*g))>=10)(pf(backtest(df,*g))[0]))
    frac = pass_n/len(grid)
    tt = stats.ttest_1samp(t_is, 0.0); pval = tt.pvalue if len(t_is)>=2 else 1.0
    verdict = (pf_is>=1.0) and (pf_oos>=1.0) and (frac>=0.5) and (pval<0.05)
    print(f"T1 IS PF={pf_is:.2f} | T2 OOS PF={pf_oos:.2f} | T3 grid={frac*100:.0f}% | T4 t p={pval:.4f}")
    print(f"VERDICT: {'GREEN_PROVEN' if verdict else 'NOT_PROVEN'}")
    json.dump({"horizon_days":60,"bars":N,"cost_per_oz":COST_PER_OZ,"base_params":base,
               "t1_is":pf_is,"t2_oos":pf_oos,"t3_grid_frac":frac,"t4_p":float(pval),
               "verdict":"GREEN_PROVEN" if verdict else "NOT_PROVEN"},
              open(r"C:\Users\victo\gold_5m_proof.json","w"), indent=2)

if __name__ == "__main__":
    raise SystemExit(main())
