#!/usr/bin/env python3
"""
FREYA GAP SCANNER — Competitive Microstructure Coverage
======================================================
Freya (Pack Research & Intelligence / scout) built this to COVER THE GAPS the
Pack was blind on: Wyckoff accumulation/distribution, VSA (Volume Spread
Analysis / effort-vs-result), HVF (Hunt Volatility Funnel), and Market Profile
(POC / VAH / VAL).

It reads the canonical bar store (D:/Hermes/workflow/data/bars.db), never
fabricates. Each detector is real signal math on real OHLCV. Output:
  - JSON  -> freya_gap_scan_latest.json  (machine readable, gate-compatible)
  - SCOUT -> a short "scout list" of names that look like live setups

No external API, no keys. Pure bars.db.

Usage:
  python3 gap_scanner.py                 # default slice (crypto+commodities+indices)
  python3 gap_scanner.py --symbol BTC-USD
  python3 gap_scanner.py --tf 1d --limit 120
  python3 gap_scanner.py --out /path/report.json
"""
from __future__ import annotations
import argparse, json, math, os, sqlite3, sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB = Path(r"D:/Hermes/workflow/data/bars.db")
OUT = Path(r"C:/Users/victo/freya_intel/freya_gap_scan_latest.json")

# ---------------------------------------------------------------------------
# Data layer (real bars.db)
# ---------------------------------------------------------------------------
def load_bars(symbol: str, tf: str = "1d", limit: int = 400) -> list[dict]:
    if not DB.exists():
        raise FileNotFoundError(f"bars.db not found at {DB}")
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT ts,open,high,low,close,volume FROM bars "
        "WHERE symbol=? AND tf=? ORDER BY ts ASC LIMIT ?",
        (symbol, tf, limit),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]

def load_slice(limit_syms: int = 80, tf: str = "1d") -> list[str]:
    """Pick symbols that actually have enough daily bars to detect structure."""
    con = sqlite3.connect(str(DB))
    syms = [r[0] for r in con.execute(
        "SELECT symbol FROM bars WHERE tf=? GROUP BY symbol "
        "HAVING COUNT(*) >= 120 ORDER BY COUNT(*) DESC LIMIT ?",
        (tf, limit_syms),
    ).fetchall()]
    con.close()
    return syms

# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------
def sma(vals: list[float], n: int) -> list[float]:
    out = []
    for i in range(len(vals)):
        if i < n - 1:
            out.append(float("nan"))
        else:
            out.append(sum(vals[i - n + 1:i + 1]) / n)
    return out

# ---------------------------------------------------------------------------
# Detector 1: WYCKOFF accumulation / distribution footprint
# A selling climax (volume spike + wide down bar near low) -> automatic rally ->
# secondary test (lower volume) -> spring (undercut on lower volume) -> recovery.
# We detect the simplified "climax low + lower-volume test + recovery" signature.
# ---------------------------------------------------------------------------
def wyckoff(bars: list[dict]) -> Optional[dict]:
    if len(bars) < 60:
        return None
    closes = [b["close"] for b in bars]
    vols = [b["volume"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    avgv = sma(vols, 20)
    n = len(bars)
    # candidate selling climax in the last 60 bars: highest volume bar that is a down bar
    window = bars[-60:]
    wv = [b["volume"] for b in window]
    sc_i_local = max(range(len(window)), key=lambda i: wv[i])
    sc = window[sc_i_local]
    sc_i = n - 60 + sc_i_local
    if sc["volume"] < 1.8 * avgv[sc_i] or sc["close"] >= sc["open"]:
        return None  # not a real climax
    sc_low = sc["low"]
    sc_high = sc["high"]
    # look for a later test/spring: a low at/below sc_low on LOWER volume, then recovery
    tested = False
    sprung = False
    recovery = False
    for j in range(sc_i + 1, n):
        if lows[j] <= sc_low * 1.002 and vols[j] < sc["volume"] * 0.8:
            tested = True
            if lows[j] < sc_low:  # undercut = spring
                sprung = True
        if tested and closes[j] > sc_high * 0.6 + sc_low * 0.4:
            recovery = True
    if not (tested and recovery):
        return None
    return {
        "method": "WYCKOFF",
        "phase": "accumulation_spring" if sprung else "accumulation_test",
        "climax_low": round(sc_low, 4),
        "climax_vol_x": round(sc["volume"] / avgv[sc_i], 2),
        "spring": sprung,
        "last_close": round(closes[-1], 4),
        "bias": "LONG",
        "confidence": 0.8 if sprung else 0.55,
    }

# ---------------------------------------------------------------------------
# Detector 2: VSA effort-vs-result (Volume Spread Analysis)
# Big volume (effort) with small range (result) = absorption.
# Upper-half close => demand absorbing supply (bullish). Lower-half => bearish.
# ---------------------------------------------------------------------------
def vsa(bars: list[dict]) -> Optional[dict]:
    if len(bars) < 30:
        return None
    ranges = [b["high"] - b["low"] for b in bars]
    vols = [b["volume"] for b in bars]
    avgv = sma(vols, 20)
    avgr = sma(ranges, 20)
    i = len(bars) - 1
    eff = vols[i] / avgv[i] if avgv[i] else 1.0
    res = ranges[i] / avgr[i] if avgr[i] else 1.0
    close_pos = (bars[i]["close"] - bars[i]["low"]) / ranges[i] if ranges[i] else 0.5
    if eff > 1.8 and res < 0.6:
        bull = close_pos > 0.5
        return {
            "method": "VSA",
            "signal": "absorption_demand" if bull else "absorption_supply",
            "effort_x": round(eff, 2),
            "result_ratio": round(res, 2),
            "close_position": round(close_pos, 2),
            "bias": "LONG" if bull else "SHORT",
            "confidence": 0.7,
        }
    return None

# ---------------------------------------------------------------------------
# Detector 3: HVF — Hunt Volatility Funnel
# A contracting funnel (lower highs + higher lows = volatility compressing) on a
# down leg, then a breakout close above the 3rd high on expanding volume.
# ---------------------------------------------------------------------------
def hvf(bars: list[dict]) -> Optional[dict]:
    if len(bars) < 40:
        return None
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    vols = [b["volume"] for b in bars]
    closes = [b["close"] for b in bars]
    n = len(bars)
    w = 30
    seg_h = highs[n - w:n]
    seg_l = lows[n - w:n]
    # three swing highs (local maxima) descending; three swing lows ascending
    h_peaks, l_troughs = [], []
    for k in range(1, w - 1):
        if seg_h[k] > seg_h[k - 1] and seg_h[k] > seg_h[k + 1]:
            h_peaks.append(seg_h[k])
        if seg_l[k] < seg_l[k - 1] and seg_l[k] < seg_l[k + 1]:
            l_troughs.append(seg_l[k])
    if len(h_peaks) < 2 or len(l_troughs) < 2:
        return None
    funnel_down = h_peaks[-1] < h_peaks[0] and l_troughs[-1] > l_troughs[0]
    if not funnel_down:
        return None
    # breakout: last close above last swing high on volume expansion
    last_high = h_peaks[-1]
    avgv = sma(vols, 20)[-1] or 1
    if closes[-1] > last_high and vols[-1] > 1.3 * avgv:
        return {
            "method": "HVF",
            "signal": "funnel_breakout",
            "funnel_high": round(h_peaks[0], 4),
            "funnel_low": round(l_troughs[-1], 4),
            "breakout_level": round(last_high, 4),
            "last_close": round(closes[-1], 4),
            "bias": "LONG",
            "confidence": 0.75,
        }
    return None

# ---------------------------------------------------------------------------
# Detector 4: Market Profile (POC / VAH / VAL) from intraday bars if available
# ---------------------------------------------------------------------------
def market_profile(bars: list[dict], bins: int = 24) -> Optional[dict]:
    if len(bars) < 30:
        return None
    # price extent
    allp = [b["high"] for b in bars] + [b["low"] for b in bars]
    lo, hi = min(allp), max(allp)
    if hi == lo:
        return None
    width = (hi - lo) / bins
    vol_at = [0.0] * bins
    for b in bars:
        # distribute bar volume across its range
        b_lo = b["low"]; b_hi = b["high"]
        if b_hi == b_lo:
            idx = min(bins - 1, int((b_lo - lo) / width))
            vol_at[idx] += b["volume"]
            continue
        steps = max(1, int((b_hi - b_lo) / width))
        per = b["volume"] / steps
        for s in range(steps):
            p = b_lo + (s + 0.5) * (b_hi - b_lo) / steps
            idx = min(bins - 1, max(0, int((p - lo) / width)))
            vol_at[idx] += per
    total = sum(vol_at)
    poc_idx = max(range(bins), key=lambda i: vol_at[i])
    poc = lo + (poc_idx + 0.5) * width
    # value area: expand from POC until 70% of volume captured
    cum = vol_at[poc_idx]
    li, ri = poc_idx, poc_idx
    while cum < 0.7 * total and (li > 0 or ri < bins - 1):
        if li > 0 and (ri >= bins - 1 or vol_at[li - 1] >= vol_at[ri + 1]):
            li -= 1; cum += vol_at[li]
        elif ri < bins - 1:
            ri += 1; cum += vol_at[ri]
        else:
            break
    val = lo + li * width
    vah = lo + (ri + 1) * width
    last = bars[-1]["close"]
    # Only flag a real scout signal when price is at a liquidity level:
    #  - below VAL (acceptance lower, continuation short) or
    #  - above VAH (acceptance higher, continuation long) or
    #  - within 0.5% of VAL/VAH (liquidity-level rejection setup)
    at_val = abs(last - val) / val < 0.005 if val else False
    at_vah = abs(last - vah) / vah < 0.005 if vah else False
    if not (last < val or last > vah or at_val or at_vah):
        return None
    if last < val:
        bias = "SHORT"
    elif last > vah:
        bias = "LONG"
    else:
        bias = "LONG" if at_val else "SHORT"
    return {
        "method": "MARKET_PROFILE",
        "poc": round(poc, 4),
        "val": round(val, 4),
        "vah": round(vah, 4),
        "value_area_pct": round(100 * cum / total, 1),
        "last_close": round(last, 4),
        "at_liquidity_level": at_val or at_vah,
        "bias": bias,
        "confidence": 0.6,
    }

# ---------------------------------------------------------------------------
# Run all detectors for one symbol
# ---------------------------------------------------------------------------
DETECTORS = [wyckoff, vsa, hvf]

def scan_symbol(symbol: str, tf: str, mp_tf: Optional[str] = "1h") -> dict:
    out = {"symbol": symbol, "hits": []}
    try:
        bars = load_bars(symbol, tf)
        if len(bars) < 40:
            return out
        for det in DETECTORS:
            r = det(bars)
            if r:
                out["hits"].append(r)
        # market profile from finer tf if present
        if mp_tf:
            mp_bars = load_bars(symbol, mp_tf, limit=500)
            if len(mp_bars) >= 60:
                mp = market_profile(mp_bars)
                if mp:
                    out["hits"].append(mp)
    except Exception as e:
        out["error"] = str(e)
    return out

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", help="single symbol")
    ap.add_argument("--tf", default="1d")
    ap.add_argument("--mp-tf", default="1h")
    ap.add_argument("--limit", type=int, default=120, help="symbols to scan")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    syms = [a.symbol] if a.symbol else load_slice(a.limit, a.tf)
    print(f"FREYA GAP SCAN — {len(syms)} symbols @ tf={a.tf} "
          f"(mp_tf={a.mp_tf}) | source={DB}", file=sys.stderr)

    results = []
    scout = []
    for s in syms:
        r = scan_symbol(s, a.tf, a.mp_tf)
        if r.get("hits"):
            results.append(r)
            methods = ",".join(h["method"] for h in r["hits"])
            bias = r["hits"][0]["bias"]
            scout.append(f"  {s:12s} {bias:5s} {methods}")
            print(f"  HIT {s}: {methods}", file=sys.stderr)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(DB),
        "tf": a.tf,
        "mp_tf": a.mp_tf,
        "symbols_scanned": len(syms),
        "symbols_with_signals": len(results),
        "results": results,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(payload, f, indent=2)

    print("\n=== FREYA SCOUT LIST (gaps covered) ===")
    if scout:
        print("\n".join(scout))
    else:
        print("  (no gap-methodology setups detected this pass)")
    print(f"\nJSON written: {a.out}")
    print(f"Scanned {len(syms)}, signals {len(results)}")

if __name__ == "__main__":
    main()
