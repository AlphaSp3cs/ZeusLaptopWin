#!/usr/bin/env python3
"""NIGHT SHIFT FULL ANALYSIS — all focus sectors with vectorbt + optuna."""
from __future__ import annotations
import json, pathlib, sys, time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import vectorbt as vbt
import optuna

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent / "bt"))
import bt_store as B

REPORT_DIR = pathlib.Path(r"C:\Hermes\workflow\backtest\reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

START = 25000.0

# Night shift focus symbols
NIGHTSHIFT_SYMBOLS = {
    "crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "DOT-USD", "LTC-USD", "ZEC-USD", "DASH-USD"],
    "forex": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X"],
    "metals": ["GC=F", "SI=F", "PL=F", "PA=F", "HG=F"],
    "energy": ["CL=F", "BZ=F", "NG=F", "USO", "UNG"],
    "indices": ["^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX", "^TNX", "^N225", "^TWII", "^FTSE", "^GDAXI"],
    "futures": ["ES=F", "NQ=F", "YM=F", "RTY=F"],
}

def load_bars(symbols):
    frames = B.load_bars(symbols)
    if not frames:
        return {}
    COMMON = None
    for d in frames.values():
        COMMON = d.index if COMMON is None else COMMON.union(d.index)
    COMMON = COMMON.sort_values()
    prepared = {}
    for sym, df in frames.items():
        d = df.reindex(COMMON).ffill().infer_objects(copy=False)
        d = B.add_indicators(d)
        d = d.dropna()
        if len(d) > 200:
            prepared[sym] = d
    return prepared

def backtest_vectorbt(sym, df, entry_type="pullback"):
    c, rsi, sma20 = df["close"], df["rsi"], df["sma20"]
    sma50 = df["sma50"]
    
    if entry_type == "pullback":
        entries = (rsi < 40) & (c < sma20)
        exits = (rsi > 70)
    elif entry_type == "momentum":
        entries = (rsi > 50) & (rsi < 60) & (c > sma50)
        exits = (rsi > 80) | (c < sma20)
    else:
        return {"symbol": sym, "error": "Unknown entry type"}
    
    entries = entries & ~entries.shift(1).fillna(False)
    if entries.sum() == 0:
        return {"symbol": sym, "error": "No entries"}
    
    try:
        portfolio = vbt.Portfolio.from_signals(
            close=c, entries=entries, exits=exits,
            init_cash=START, size=0.02, size_type="percent", freq="1d",
            fees=0.001, slippage=0.001,
        )
        stats = portfolio.stats()
        return {
            "symbol": sym, "total_return": round(stats.get("Total Return [%]", 0), 2),
            "sharpe": round(stats.get("Sharpe Ratio", 0), 3),
            "max_drawdown": round(stats.get("Max Drawdown [%]", 0), 2),
            "win_rate": round(stats.get("Win Rate [%]", 0), 2) if "Win Rate [%]" in stats else 0,
            "final_equity": round(START * (1 + stats.get("Total Return [%]", 0) / 100), 2),
            "n_trades": int(entries.sum()), "entry_type": entry_type,
        }
    except Exception as e:
        return {"symbol": sym, "error": str(e)}

def optimize_optuna(sym, df, n_trials=50):
    c, rsi, sma20 = df["close"], df["rsi"], df["sma20"]
    sma50 = df["sma50"]
    
    def objective(trial):
        rsi_low = trial.suggest_int("rsi_low", 20, 50, step=5)
        rsi_high = trial.suggest_int("rsi_high", 60, 85, step=5)
        use_sma20 = trial.suggest_categorical("use_sma20", [True, False])
        use_sma50 = trial.suggest_categorical("use_sma50", [True, False])
        
        if use_sma20:
            entries = (rsi < rsi_low) & (c < sma20)
        else:
            entries = rsi < rsi_low
        
        if use_sma50:
            exits = (rsi > rsi_high) | (c > sma50)
        else:
            exits = rsi > rsi_high
        
        entries = entries & ~entries.shift(1).fillna(False)
        if entries.sum() < 5:
            return -1.0
        
        try:
            portfolio = vbt.Portfolio.from_signals(
                close=c, entries=entries, exits=exits,
                init_cash=START, size=0.02, size_type="percent", freq="1d",
                fees=0.001, slippage=0.001,
            )
            stats = portfolio.stats()
            ret = stats.get("Total Return [%]", 0)
            sharpe = stats.get("Sharpe Ratio", 0)
            return sharpe if sharpe == sharpe else -1.0  # Return Sharpe
        except:
            return -1.0
    
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler())
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    
    best = study.best_trial
    return {
        "symbol": sym,
        "best_sharpe": round(best.value, 3) if best.value else None,
        "best_params": best.params if best else None,
        "n_trials": len(study.trials),
    }

def main():
    print("=" * 80)
    print("NIGHT SHIFT FULL ANALYSIS — All Focus Sectors")
    print("=" * 80)
    
    all_results = {}
    
    for sector, symbols in NIGHTSHIFT_SYMBOLS.items():
        print(f"\n--- {sector.upper()} ---")
        frames = load_bars(symbols)
        if not frames:
            print(f"  No data")
            continue
        
        sector_results = []
        for sym, df in frames.items():
            r = backtest_vectorbt(sym, df, "pullback")
            if "error" not in r:
                sector_results.append(r)
                status = "✓" if r["total_return"] > 0 else "✗"
                print(f"  {status} {sym:<12} Return={r['total_return']:>+6.1f}% Sharpe={r['sharpe']:>5.2f} MaxDD={r['max_drawdown']:>5.1f}% Trades={r['n_trades']}")
            else:
                print(f"  ⚠ {sym}: {r['error']}")
        
        all_results[sector] = sector_results
    
    # Save
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {"timestamp": stamp, "results": all_results}
    json_path = REPORT_DIR / f"nightshift_full_{stamp}.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print("=" * 80)
    for sector, results in all_results.items():
        if not results:
            continue
        avg_ret = np.mean([r["total_return"] for r in results])
        avg_sharpe = np.mean([r["sharpe"] for r in results if r["sharpe"] != 0])
        positive = sum(1 for r in results if r["total_return"] > 0)
        print(f"  {sector:<12} Avg Return: {avg_ret:+.1f}% | Avg Sharpe: {avg_sharpe:.2f} | Positive: {positive}/{len(results)}")
    
    print(f"\nReport: {json_path}")

if __name__ == "__main__":
    main()
