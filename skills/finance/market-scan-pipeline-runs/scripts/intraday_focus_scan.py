"""Focused intraday scan + backtest for a small symbol set (gold/oil etc).

Companion to backtest_go_setups.py. That one validates daily swing GOs from the
universal scan; this one handles "concentrate on these 2 assets, give me
intraday positions" requests.

Produces, per symbol:
  - live snapshot: session VWAP, 15m RSI/ATR, daily ATR, opening range,
    prior-day H/L/C
  - a 60-day 15m backtest of a VWAP-reversion rule, BOTH directions, so the
    tradeable side is decided by data rather than by the narrative

Key design notes (learned the hard way):
  * Volume-less feeds (FX '=X', cash indices '^') collapse a volume-weighted
    VWAP onto spot -> vwap_distance always 0.00. session_vwap() falls back to
    an expanding TWAP.
  * Always backtest BOTH sides. The 2026-08-05 run found gold shorts positive
    (GLD 1.42) and gold longs negative (GLD 0.84, GC=F 0.81, GDX 0.75), with
    oil the exact inverse (USO long 1.52, BZ=F short 0.81). Testing only the
    side the news implies would have produced a losing book.
  * ETFs generally beat raw futures on identical rules (USO 1.52 vs CL=F 1.00;
    GLD 1.42 vs GC=F 1.02) because wider futures ATR chops the same stop.
    Report the paired PFs so the vehicle choice is evidence-based.
  * Stop is checked before target within each bar (conservative).

Edit UNIVERSE for the assets requested, then:
    python3 intraday_focus_scan.py
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

UNIVERSE = {
    "GC=F": "Gold futures",
    "GLD": "Gold ETF",
    "GDX": "Gold miners",
    "CL=F": "WTI futures",
    "BZ=F": "Brent futures",
    "USO": "WTI ETF",
    "XLE": "Energy sector",
}


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["Close"].shift()
    tr = pd.concat(
        [df["High"] - df["Low"], (df["High"] - pc).abs(), (df["Low"] - pc).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """Session-anchored VWAP with a TWAP fallback for volume-less feeds."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    v = df["Volume"].fillna(0)
    day = df.index.date
    if v.sum() <= 0:
        return tp.groupby(day).transform(lambda x: x.expanding().mean())
    pv = (tp * v).groupby(day).cumsum()
    cv = v.groupby(day).cumsum().replace(0, np.nan)
    return (pv / cv).fillna(
        tp.groupby(day).transform(lambda x: x.expanding().mean())
    )


def fetch(sym: str, interval: str, period: str) -> pd.DataFrame | None:
    df = yf.download(
        sym, period=period, interval=interval,
        progress=False, auto_adjust=False, prepost=True,
    )
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Close"])


def snapshot(sym: str, label: str) -> dict | None:
    m15 = fetch(sym, "15m", "60d")
    if m15 is None or len(m15) < 100:
        return None
    m15["vwap"] = session_vwap(m15)
    m15["rsi"] = rsi(m15["Close"])
    m15["atr"] = atr(m15)
    last = m15.iloc[-1]

    d1 = fetch(sym, "1d", "1mo")
    prior = d1.iloc[-2] if d1 is not None and len(d1) > 1 else None
    today = m15[m15.index.date == m15.index[-1].date()]
    orb = today.iloc[:4] if len(today) >= 4 else today

    return {
        "symbol": sym,
        "name": label,
        "price": round(float(last.Close), 4),
        "vwap": round(float(last.vwap), 4),
        "vwap_dist_pct": round(100 * (last.Close - last.vwap) / last.vwap, 2),
        "rsi15": round(float(last.rsi), 1),
        "atr15": round(float(last.atr), 4),
        "day_atr": round(float(atr(d1).iloc[-1]), 4) if d1 is not None else None,
        "or_high": round(float(orb["High"].max()), 4),
        "or_low": round(float(orb["Low"].min()), 4),
        "prior_high": round(float(prior.High), 4) if prior is not None else None,
        "prior_low": round(float(prior.Low), 4) if prior is not None else None,
        "prior_close": round(float(prior.Close), 4) if prior is not None else None,
    }


def bt_vwap_reversion(sym: str, rr: float = 1.5, stop_mult: float = 1.5,
                      max_bars: int = 26) -> dict | None:
    """Fade extension from session VWAP. Tests LONG and SHORT independently."""
    df = fetch(sym, "15m", "60d")
    if df is None or len(df) < 200:
        return None
    df["vwap"] = session_vwap(df)
    df["rsi"] = rsi(df["Close"])
    df["atr"] = atr(df)
    df = df.dropna()

    res = {}
    for side in ("LONG", "SHORT"):
        trades, i, n = [], 0, len(df)
        while i < n - 1:
            r = df.iloc[i]
            dist = (r.Close - r.vwap) / r.atr if r.atr > 0 else 0
            trig = (side == "LONG" and r.rsi < 35 and dist < -0.5) or \
                   (side == "SHORT" and r.rsi > 65 and dist > 0.5)
            if not trig or r.atr <= 0:
                i += 1
                continue
            entry = float(df.iloc[i + 1]["Open"])
            risk = stop_mult * float(r.atr)
            sl = entry - risk if side == "LONG" else entry + risk
            tp = entry + rr * risk if side == "LONG" else entry - rr * risk
            out, bars = None, 0
            for j in range(i + 1, min(i + 1 + max_bars, n)):
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
                c = float(df.iloc[min(i + max_bars, n - 1)]["Close"])
                out = ((c - entry) if side == "LONG" else (entry - c)) / risk
            trades.append(out)
            i += bars + 1

        if trades:
            t = np.array(trades)
            w, l = t[t > 0], t[t <= 0]
            res[side] = {
                "trades": int(t.size),
                "win_rate": round(100 * w.size / t.size, 1),
                "avg_R": round(float(t.mean()), 3),
                "total_R": round(float(t.sum()), 1),
                "profit_factor": (
                    round(float(w.sum() / abs(l.sum())), 2)
                    if l.size and l.sum() else None
                ),
                "max_dd_R": round(
                    float((np.maximum.accumulate(t.cumsum()) - t.cumsum()).max()), 1
                ),
            }
    return {"symbol": sym, "strategy": "vwap_reversion_15m", "results": res}


def main() -> None:
    snaps, bts = [], []
    for sym, label in UNIVERSE.items():
        try:
            s = snapshot(sym, label)
            if s:
                snaps.append(s)
                print("SNAP", s)
        except Exception as e:  # noqa: BLE001
            print(f"snap err {sym}: {e}")
        try:
            b = bt_vwap_reversion(sym)
            if b and b["results"]:
                bts.append(b)
                print("BT", b)
        except Exception as e:  # noqa: BLE001
            print(f"bt err {sym}: {e}")

    out = HOME / "intraday_focus_results.json"
    out.write_text(json.dumps({"snapshots": snaps, "backtests": bts}, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
