"""Backtest the scan's setup rules on the current GO symbols.

Rule replicated from universal_premarket_scan/enhanced_trade_gate:
  LONG  trigger: RSI(14) < 40 and close < VWAP(20)
  SHORT trigger: RSI(14) > 60 and close > VWAP(20)
  stop  = entry -/+ 2.0*ATR(14)
  target= entry +/- 2.0*R   (swing rr_1 = 2.0)
  max holding 20 bars, exit at close otherwise.
Bar-by-bar, stop checked before target (conservative).
"""
from __future__ import annotations
import json, logging
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
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    v = df["Volume"].fillna(0)
    if v.sum() <= 0:  # volume-less feed (FX/indices) -> TWAP fallback
        return tp.rolling(n).mean()
    pv = (tp * v).rolling(n).sum()
    vv = v.rolling(n).sum().replace(0, np.nan)
    out = pv / vv
    return out.fillna(tp.rolling(n).mean())


def backtest(sym: str, side: str, period: str = "10y") -> dict | None:
    side = side.upper()  # normalize: callers pass 'long'/'short'
    # Backtest window = 10y (or max available). Per standing rule the edge must
    # be validated on a decade of data, not a 3y snippet.
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

    trades = []
    i = 0
    n = len(df)
    while i < n - 1:
        r = df.iloc[i]
        trig = (side == "LONG" and r.rsi < 40 and r.Close < r.vwap) or \
               (side == "SHORT" and r.rsi > 60 and r.Close > r.vwap)
        if not trig or r.atr <= 0:
            i += 1
            continue
        entry = float(df.iloc[i + 1]["Open"])
        risk = ATR_MULT * float(r.atr)
        if side == "LONG":
            sl, tp = entry - risk, entry + RR * risk
        else:
            sl, tp = entry + risk, entry - RR * risk
        out, bars = None, 0
        for j in range(i + 1, min(i + 1 + MAX_BARS, n)):
            b = df.iloc[j]
            bars = j - i
            if side == "LONG":
                if b.Low <= sl:
                    out = -1.0; break
                if b.High >= tp:
                    out = RR; break
            else:
                if b.High >= sl:
                    out = -1.0; break
                if b.Low <= tp:
                    out = RR; break
        if out is None:
            last = float(df.iloc[min(i + MAX_BARS, n - 1)]["Close"])
            out = ((last - entry) if side == "LONG" else (entry - last)) / risk
        trades.append(out)
        i += bars + 1

    if not trades:
        return None
    t = np.array(trades)
    wins = t[t > 0]
    losses = t[t <= 0]
    return {
        "symbol": sym, "side": side, "trades": int(t.size),
        "win_rate": round(100 * wins.size / t.size, 1),
        "avg_R": round(float(t.mean()), 3),
        "total_R": round(float(t.sum()), 1),
        "expectancy": round(float(t.mean()), 3),
        "max_dd_R": round(float((np.maximum.accumulate(t.cumsum()) - t.cumsum()).max()), 1),
        "profit_factor": round(float(wins.sum() / abs(losses.sum())), 2)
        if losses.size and losses.sum() != 0
        else (float("inf") if wins.size else None),
    }


def main() -> None:
    go = json.loads((HOME / "go_setups_tmp.json").read_text())
    seen, rows = set(), []
    for prof in ("swing", "day"):
        for s in go[prof]:
            key = (s["sym"], s["side"])
            if key in seen:
                continue
            seen.add(key)
            dl = s.get("yf", s["sym"])  # yfinance download ticker (suffixed)
            try:
                r = backtest(dl, s["side"])
            except Exception as e:  # noqa: BLE001
                r = None
                print(f"ERR {s['sym']} ({dl}): {e}")
            if r:
                r["symbol"] = s["sym"]  # restore display symbol on output
                r["category"] = s["cat"]
                rows.append(r)
                print(r)
    (HOME / "backtest_go_results.json").write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {HOME / 'backtest_go_results.json'}  ({len(rows)} symbols)")


if __name__ == "__main__":
    main()
