"""Backtest the scan's setup rules against the current GO symbols.

Purpose: a GO verdict from enhanced_trade_gate.py only proves the RISK MECHANICS
are sane (R:R, stop width, size, concentration, earnings, liquidity, extension).
It says nothing about whether the entry rule has ever made money. This replays
the scan's own rule on 3y of daily bars so the report can separate
positive-expectancy setups from negative-expectancy ones.

Rule replicated from universal_premarket_scan / enhanced_trade_gate:
  LONG  trigger: RSI(14) < 40 and close < VWAP(20)
  SHORT trigger: RSI(14) > 60 and close > VWAP(20)
  stop   = entry -/+ ATR_MULT * ATR(14)
  target = entry +/- RR * risk            (swing rr_1 = 2.0)
  max holding MAX_BARS bars, else exit at close.
Bar-by-bar; stop is checked BEFORE target (conservative — assumes the worst
intrabar ordering).

Input : ~/go_setups_tmp.json  -> {"swing": [{sym, cat, side, ...}], "day": [...]}
        (write this by projecting validation.verdict == 'GO' rows out of
         enhanced_setups_{swing,day}_latest.json — never dump the raw gate JSON)
Output: ~/backtest_go_results.json

Run with the interpreter that actually has yfinance (usually system python3,
NOT the Hermes agent venv).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.WARNING)
HOME = Path.home()

RR = 2.0
ATR_MULT = 2.0
MAX_BARS = 20


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
    """Volume-weighted, with TWAP fallback for volume-less feeds.

    yfinance FX '=X' pairs and cash indices report volume 0; without this
    fallback vwap_distance collapses to 0.00 and those classes never trigger.
    """
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    v = df["Volume"].fillna(0)
    if v.sum() <= 0:
        return tp.rolling(n).mean()
    pv = (tp * v).rolling(n).sum()
    vv = v.rolling(n).sum().replace(0, np.nan)
    return (pv / vv).fillna(tp.rolling(n).mean())


def backtest(sym: str, side: str, period: str = "3y") -> dict | None:
    df = yf.download(sym, period=period, interval="1d",
                     progress=False, auto_adjust=False)
    if df is None or len(df) < 120:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])
    df["rsi"] = rsi(df["Close"])
    df["atr"] = atr(df)
    df["vwap"] = vwap(df)
    df = df.dropna()

    trades: list[float] = []
    i, n = 0, len(df)
    while i < n - 1:
        r = df.iloc[i]
        trig = (side == "LONG" and r.rsi < 40 and r.Close < r.vwap) or \
               (side == "SHORT" and r.rsi > 60 and r.Close > r.vwap)
        if not trig or r.atr <= 0:
            i += 1
            continue
        entry = float(df.iloc[i + 1]["Open"])   # next-bar open, no lookahead
        risk = ATR_MULT * float(r.atr)
        sl, tp = ((entry - risk, entry + RR * risk) if side == "LONG"
                  else (entry + risk, entry - RR * risk))
        out, bars = None, 0
        for j in range(i + 1, min(i + 1 + MAX_BARS, n)):
            b = df.iloc[j]
            bars = j - i
            if side == "LONG":
                if b.Low <= sl:
                    out = -1.0
                    break
                if b.High >= tp:
                    out = RR
                    break
            else:
                if b.High >= sl:
                    out = -1.0
                    break
                if b.Low <= tp:
                    out = RR
                    break
        if out is None:
            last = float(df.iloc[min(i + MAX_BARS, n - 1)]["Close"])
            out = ((last - entry) if side == "LONG" else (entry - last)) / risk
        trades.append(out)
        i += bars + 1

    if not trades:
        return None
    t = np.array(trades)
    wins, losses = t[t > 0], t[t <= 0]
    curve = t.cumsum()
    return {
        "symbol": sym,
        "side": side,
        "trades": int(t.size),
        "win_rate": round(100 * wins.size / t.size, 1),
        "avg_R": round(float(t.mean()), 3),
        "total_R": round(float(t.sum()), 1),
        "expectancy": round(float(t.mean()), 3),
        "max_dd_R": round(float((np.maximum.accumulate(curve) - curve).max()), 1),
        "profit_factor": (round(float(wins.sum() / abs(losses.sum())), 2)
                          if losses.size and losses.sum() != 0 else None),
    }


def main() -> None:
    go = json.loads((HOME / "go_setups_tmp.json").read_text())
    seen: set[tuple[str, str]] = set()
    rows: list[dict] = []
    for prof in ("swing", "day"):
        for s in go.get(prof, []):
            key = (s["sym"], s["side"])
            if key in seen:
                continue
            seen.add(key)
            try:
                r = backtest(s["sym"], s["side"])
            except Exception as exc:  # noqa: BLE001 - report and continue
                logging.warning("backtest failed for %s: %s", s["sym"], exc)
                r = None
            if r:
                r["category"] = s["cat"]
                rows.append(r)
                print(r)
    (HOME / "backtest_go_results.json").write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {HOME / 'backtest_go_results.json'} ({len(rows)} symbols)")


if __name__ == "__main__":
    main()
