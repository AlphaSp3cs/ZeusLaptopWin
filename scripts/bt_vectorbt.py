#!/usr/bin/env python3
"""VECTORBT BACKTEST ENGINE — pure-additive upgrade."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "bt"))  # Add C:\Users\victo\bt for bt_store
import bt_store as B

REPORT_DIR = Path(r"C:\Hermes\workflow\backtest\reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

START = 25000.0


def load_and_prepare(symbols):
    """Load bars from bars.db and prepare DataFrames."""
    frames = B.load_bars(symbols)
    if not frames:
        return None
    COMMON = None
    for d in frames.values():
        COMMON = d.index if COMMON is None else COMMON.union(d.index)
    COMMON = COMMON.sort_values()
    prepared = {}
    for sym, df in frames.items():
        d = df.reindex(COMMON).ffill()
        d = B.add_indicators(d)
        d = d.dropna()
        if len(d) > 200:
            prepared[sym] = d
    return prepared


def backtest_symbol(sym, df, entry_type="pullback", risk_pct=0.02):
    """Backtest a single symbol."""
    c = df["close"]
    rsi = df["rsi"]
    sma20 = df["sma20"]
    
    if entry_type == "pullback":
        entries = (rsi < 40) & (c < sma20)
        exits = (rsi > 70)
    elif entry_type == "momentum":
        entries = (rsi > 50) & (rsi < 60) & (c > df["sma50"])
        exits = (rsi > 80) | (c < sma20)
    else:
        return {"symbol": sym, "error": "Unknown entry type"}
    
    entries = entries & ~entries.shift(1).fillna(False)
    
    if entries.sum() == 0:
        return {"symbol": sym, "error": "No entries generated"}
    
    try:
        portfolio = vbt.Portfolio.from_signals(
            close=c,
            entries=entries,
            exits=exits,
            init_cash=START,
            size=risk_pct,
            size_type="percent",
            freq="1d",
            fees=0.001,
            slippage=0.001,
        )
        
        stats = portfolio.stats()
        
        return {
            "symbol": sym,
            "total_return": round(stats.get("Total Return [%]", 0), 2),
            "sharpe": round(stats.get("Sharpe Ratio", 0), 3),
            "max_drawdown": round(stats.get("Max Drawdown [%]", 0), 2),
            "win_rate": round(stats.get("Win Rate [%]", 0), 2) if "Win Rate [%]" in stats else 0,
            "final_equity": round(START * (1 + stats.get("Total Return [%]", 0) / 100), 2),
            "n_trades": int(entries.sum()),
            "entry_type": entry_type,
        }
    except Exception as e:
        return {"symbol": sym, "error": str(e)}


def main():
    print("=" * 80)
    print("VECTORBT BACKTEST ENGINE")
    print("=" * 80)
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"])
    parser.add_argument("--entry", default="pullback")
    parser.add_argument("--risk", type=float, default=0.02)
    args = parser.parse_args()
    
    start_time = time.time()
    frames = load_and_prepare(args.symbols)
    
    if not frames:
        print("No data loaded")
        return
    
    print(f"Loaded {len(frames)} symbols in {time.time()-start_time:.1f}s")
    
    results = []
    for sym, df in frames.items():
        r = backtest_symbol(sym, df, args.entry, args.risk)
        results.append(r)
        if "error" not in r:
            status = "✓" if r["total_return"] > 0 else "✗"
            print(f"  {status} {sym:<12} Return={r['total_return']:>+7.1f}% Sharpe={r['sharpe']:>5.2f} MaxDD={r['max_drawdown']:>5.1f}% Trades={r['n_trades']}")
        else:
            print(f"  ⚠ {sym}: {r['error']}")
    
    # Save
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "timestamp": stamp,
        "symbols": args.symbols,
        "entry_type": args.entry,
        "results": results,
    }
    json_path = REPORT_DIR / f"vectorbt_{stamp}.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    
    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.1f}s | Report: {json_path}")


if __name__ == "__main__":
    main()
