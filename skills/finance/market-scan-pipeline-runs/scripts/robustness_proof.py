"""Robustness harness — proves a setup is profitable, not just one lucky run.

Three independent stress tests on the scanner's own rule:
  1. WALK-FORWARD (out-of-sample): train 2016-2021, test 2021-2026. Edge must
     hold on data the in-sample fit never saw.
  2. PARAMETER GRID: sweep RSI band, ATR multiplier, and R:R. Edge must survive
     a majority of parameter sets (proves it isn't one magic combination).
  3. SIGNIFICANCE: one-sample t-test on per-trade R. Edge must be statistically
     distinguishable from zero (p < 0.05).

A setup is GREEN only if ALL THREE pass. This is the "prove profitable all we
can" bar — anything less is flagged with exactly which test failed.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

RR0, ATM0, MAX_BARS = 2.0, 2.0, 20


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift()
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def vwap(df: pd.DataFrame, n: int = 20) -> pd.Series:
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    v = df["Volume"].fillna(0)
    if v.sum() <= 0:
        return tp.rolling(n).mean()
    pv = (tp * v).rolling(n).sum()
    vv = v.rolling(n).sum().replace(0, np.nan)
    return (pv / vv).fillna(tp.rolling(n).mean())


def _load(sym: str) -> pd.DataFrame | None:
    df = yf.download(sym, period="10y", interval="1d", progress=False, auto_adjust=False)
    if df is None or len(df) < 120:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])
    df["rsi"] = rsi(df["Close"])
    df["atr"] = atr(df)
    df["vwap"] = vwap(df)
    return df.dropna()


def _run(df: pd.DataFrame, side: str, rsi_band: int, atm: float, rr: float) -> list[float]:
    """Return list of per-trade R multiples. side in {LONG,SHORT}."""
    lo, hi = (rsi_band, 40) if side == "LONG" else (60, rsi_band)
    n = len(df)
    trades = []
    i = 0
    while i < n - 1:
        r = df.iloc[i]
        if side == "LONG":
            trig = r.rsi < lo and r.Close < r.vwap
        else:
            trig = r.rsi > hi and r.Close > r.vwap
        if not trig or r.atr <= 0:
            i += 1
            continue
        entry = float(df.iloc[i + 1]["Open"])
        risk = atm * float(r.atr)
        sl, tp = (entry - risk, entry + rr * risk) if side == "LONG" \
            else (entry + risk, entry - rr * risk)
        out, bars = None, 0
        for j in range(i + 1, min(i + 1 + MAX_BARS, n)):
            b = df.iloc[j]
            bars = j - i
            if side == "LONG":
                if b.Low <= sl:
                    out = -1.0
                    break
                if b.High >= tp:
                    out = rr
                    break
            else:
                if b.High >= sl:
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


def _pf(trades: list[float]) -> float | None:
    t = np.array(trades)
    if t.size == 0:
        return None
    w = t[t > 0]
    l = t[t <= 0]
    if l.size and l.sum() != 0:
        return round(float(w.sum() / abs(l.sum())), 3)
    return float("inf") if w.size else None


def _sig(trades: list[float]) -> dict:
    t = np.array(trades, dtype=float)
    if t.size < 5:
        return {"t": None, "p": None, "n": int(t.size)}
    res = stats.ttest_1samp(t, 0.0)
    return {"t": round(float(res.statistic), 3),
            "p": round(float(res.pvalue), 4), "n": int(t.size)}


def validate(sym: str, side: str) -> dict:
    side = side.upper()
    df = _load(sym)
    if df is None:
        return {"symbol": sym, "side": side, "error": "no data / <120 bars"}
    # Walk-forward split on calendar: train first 60%, test last 40% (~6y/4y)
    cut = int(len(df) * 0.6)
    df_tr, df_te = df.iloc[:cut], df.iloc[cut:]
    tr_t = _run(df_tr, side, 40, ATM0, RR0)
    te_t = _run(df_te, side, 40, ATM0, RR0)
    pf_is, pf_oos = _pf(tr_t), _pf(te_t)
    # Parameter grid
    grid_total = 0
    grid_pass = 0
    for rb in ([35, 38, 40, 42, 45] if side == "LONG" else [55, 58, 60, 62, 65]):
        for a in (1.5, 2.0, 2.5, 3.0):
            for rr in (1.5, 2.0, 2.5):
                grid_total += 1
                g = _run(df, side, rb, a, rr)
                p = _pf(g)
                if p is not None and p >= 1.0:
                    grid_pass += 1
    grid_ok = grid_pass / grid_total >= 0.5
    # Significance on full-sample trades
    sig = _sig(_run(df, side, 40, ATM0, RR0))
    # Verdict
    oos_ok = pf_oos is not None and pf_oos >= 1.0
    is_ok = pf_is is not None and pf_is >= 1.0
    sig_ok = sig["p"] is not None and sig["p"] < 0.05
    green = is_ok and oos_ok and grid_ok and sig_ok
    return {
        "symbol": sym, "side": side,
        "pf_in_sample": pf_is, "pf_out_of_sample": pf_oos,
        "oos_pf_ok": oos_ok, "is_pf_ok": is_ok,
        "grid_pass": f"{grid_pass}/{grid_total}",
        "grid_pct": round(100 * grid_pass / grid_total, 0),
        "grid_ok": grid_ok,
        "sig_t": sig["t"], "sig_p": sig["p"], "sig_n": sig["n"], "sig_ok": sig_ok,
        "verdict": "GREEN_PROVEN" if green else "NOT_PROVEN",
        "failed": [k for k, v in
                   {"in_sample_PF>=1": is_ok, "out_of_sample_PF>=1": oos_ok,
                    "grid_majority_PF>=1": grid_ok, "t_test_p<0.05": sig_ok}.items() if not v],
    }


if __name__ == "__main__":
    import sys, json
    out = []
    for arg in sys.argv[1:]:
        sym, s = arg.split(":")
        out.append(validate(sym, s))
    print(json.dumps(out, indent=2))
