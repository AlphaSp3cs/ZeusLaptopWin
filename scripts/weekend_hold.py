#!/usr/bin/env python3
"""Weekend hold analysis — NEAR, BCH, ETH for 2-3 day hold."""
import json, pathlib, sqlite3, sys
import pandas as pd
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent / "bt"))
import bt_store as B

REPORT_DIR = pathlib.Path(r"C:\Hermes\workflow\backtest\reports")

SYMBOLS = ["NEAR-USD", "BCH-USD", "ETH-USD"]

def analyze_symbol(sym, df):
    """Deep analysis for weekend hold."""
    c = df["close"]
    rsi = df["rsi"]
    sma20 = df["sma20"]
    sma50 = df["sma50"]
    vol = df["volume"]
    
    # Current state
    price = c.iloc[-1]
    current_rsi = rsi.iloc[-1]
    
    # RSI trend (last 5 days)
    rsi_trend = rsi.iloc[-5:].values
    rsi_slope = np.polyfit(range(len(rsi_trend)), rsi_trend, 1)[0]
    
    # Price vs MAs
    above_sma20 = price > sma20.iloc[-1]
    above_sma50 = price > sma50.iloc[-1]
    sma20_above_sma50 = sma20.iloc[-1] > sma50.iloc[-1]
    
    # Volume trend
    avg_vol_20 = vol.iloc[-20:].mean()
    avg_vol_5 = vol.iloc[-5:].mean()
    vol_trend = avg_vol_5 / avg_vol_20 if avg_vol_20 > 0 else 1.0
    
    # Recent performance
    ret_1d = (c.iloc[-1] / c.iloc[-2] - 1) * 100 if len(c) >= 2 else 0
    ret_3d = (c.iloc[-1] / c.iloc[-4] - 1) * 100 if len(c) >= 4 else 0
    ret_7d = (c.iloc[-1] / c.iloc[-8] - 1) * 100 if len(c) >= 8 else 0
    ret_14d = (c.iloc[-1] / c.iloc[-15] - 1) * 100 if len(c) >= 15 else 0
    
    # 3-day hold backtest (buy and hold 3 days)
    three_day_returns = []
    for i in range(len(c) - 3):
        ret = (c.iloc[i+3] / c.iloc[i] - 1) * 100
        three_day_returns.append(ret)
    
    avg_3d = np.mean(three_day_returns)
    median_3d = np.median(three_day_returns)
    win_rate_3d = sum(1 for r in three_day_returns if r > 0) / len(three_day_returns)
    best_3d = np.max(three_day_returns)
    worst_3d = np.min(three_day_returns)
    
    # 2-day hold
    two_day_returns = []
    for i in range(len(c) - 2):
        ret = (c.iloc[i+2] / c.iloc[i] - 1) * 100
        two_day_returns.append(ret)
    
    avg_2d = np.mean(two_day_returns)
    median_2d = np.median(two_day_returns)
    win_rate_2d = sum(1 for r in two_day_returns if r > 0) / len(two_day_returns)
    
    # Conditional 3-day returns (when RSI < 40)
    oversold_3d = []
    for i in range(len(c) - 3):
        if rsi.iloc[i] < 40:
            ret = (c.iloc[i+3] / c.iloc[i] - 1) * 100
            oversold_3d.append(ret)
    
    # Conditional 3-day returns (when RSI > 60)
    overbought_3d = []
    for i in range(len(c) - 3):
        if rsi.iloc[i] > 60:
            ret = (c.iloc[i+3] / c.iloc[i] - 1) * 100
            overbought_3d.append(ret)
    
    return {
        "symbol": sym,
        "price": price,
        "rsi": current_rsi,
        "rsi_slope": rsi_slope,
        "above_sma20": above_sma20,
        "above_sma50": above_sma50,
        "sma20_above_sma50": sma20_above_sma50,
        "vol_trend": vol_trend,
        "ret_1d": ret_1d,
        "ret_3d": ret_3d,
        "ret_7d": ret_7d,
        "ret_14d": ret_14d,
        "avg_2d": avg_2d,
        "median_2d": median_2d,
        "win_rate_2d": win_rate_2d,
        "avg_3d": avg_3d,
        "median_3d": median_3d,
        "win_rate_3d": win_rate_3d,
        "best_3d": best_3d,
        "worst_3d": worst_3d,
        "oversold_3d_avg": np.mean(oversold_3d) if oversold_3d else None,
        "oversold_3d_count": len(oversold_3d),
        "overbought_3d_avg": np.mean(overbought_3d) if overbought_3d else None,
        "overbought_3d_count": len(overbought_3d),
    }

def main():
    print("=" * 80)
    print("WEEKEND HOLD ANALYSIS — NEAR, BCH, ETH (2-3 day hold)")
    print("=" * 80)
    
    frames = B.load_bars(SYMBOLS)
    if not frames:
        print("ERROR: No data")
        return
    
    COMMON = None
    for d in frames.values():
        COMMON = d.index if COMMON is None else COMMON.union(d.index)
    COMMON = COMMON.sort_values()
    
    results = []
    for sym in SYMBOLS:
        if sym not in frames:
            print(f"\n{sym}: NOT IN DATA")
            continue
        
        df = frames[sym].reindex(COMMON).ffill().infer_objects(copy=False)
        df = B.add_indicators(df)
        df = df.dropna()
        
        if len(df) < 30:
            print(f"\n{sym}: Insufficient data ({len(df)} bars)")
            continue
        
        r = analyze_symbol(sym, df)
        results.append(r)
        
        print(f"\n{'='*60}")
        print(f"{sym}")
        print(f"{'='*60}")
        print(f"  Price: ${r['price']:,.2f}")
        print(f"  RSI: {r['rsi']:.1f} (slope: {r['rsi_slope']:+.2f})")
        print(f"  Trend: {'Bullish' if r['above_sma20'] and r['sma20_above_sma50'] else 'Bearish' if not r['above_sma20'] else 'Neutral'}")
        print(f"  Above SMA20: {r['above_sma20']} | Above SMA50: {r['above_sma50']}")
        print(f"  Volume: {r['vol_trend']:.1f}x avg ({'Accumulation' if r['vol_trend'] > 1.5 else 'Distribution' if r['vol_trend'] < 0.7 else 'Normal'})")
        print(f"  Returns: 1d={r['ret_1d']:+.1f}% | 3d={r['ret_3d']:+.1f}% | 7d={r['ret_7d']:+.1f}% | 14d={r['ret_14d']:+.1f}%")
        
        print(f"\n  --- 2-DAY HOLD ---")
        print(f"  Avg Return: {r['avg_2d']:+.2f}% | Median: {r['median_2d']:+.2f}% | Win Rate: {r['win_rate_2d']:.1%}")
        
        print(f"\n  --- 3-DAY HOLD (WEEKEND) ---")
        print(f"  Avg Return: {r['avg_3d']:+.2f}% | Median: {r['median_3d']:+.2f}% | Win Rate: {r['win_rate_3d']:.1%}")
        print(f"  Best: {r['best_3d']:+.1f}% | Worst: {r['worst_3d']:+.1f}%")
        
        if r['oversold_3d_avg'] is not None:
            print(f"\n  --- 3-DAY HOLD WHEN RSI < 40 (BUY DIP) ---")
            print(f"  Avg Return: {r['oversold_3d_avg']:+.2f}% | Occurrences: {r['oversold_3d_count']}")
        
        if r['overbought_3d_avg'] is not None:
            print(f"\n  --- 3-DAY HOLD WHEN RSI > 60 (BUY STRENGTH) ---")
            print(f"  Avg Return: {r['overbought_3d_avg']:+.2f}% | Occurrences: {r['overbought_3d_count']}")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY — WEEKEND HOLD RANKING")
    print("=" * 80)
    
    print(f"\n{'Symbol':<12} {'Price':>10} {'RSI':>5} {'3d Avg':>7} {'3d Win':>7} {'Dip 3d':>7} {'Best':>7} {'Worst':>7}")
    print("-" * 75)
    for r in results:
        dip_str = f"{r['oversold_3d_avg']:+.1f}%" if r['oversold_3d_avg'] is not None else "N/A"
        print(f"  {r['symbol']:<12} ${r['price']:>9,.2f} {r['rsi']:>5.1f} {r['avg_3d']:>+6.2f}% {r['win_rate_3d']:>6.1%} {dip_str:>7} {r['best_3d']:>+6.1f}% {r['worst_3d']:>+6.1f}%")
    
    # Best weekend hold
    if results:
        best = min(results, key=lambda x: -x['avg_3d'])
        print(f"\n  🏆 BEST WEEKEND HOLD: {best['symbol']}")
        print(f"     3-Day Avg Return: {best['avg_3d']:+.2f}%")
        print(f"     Win Rate: {best['win_rate_3d']:.1%}")
        print(f"     Current RSI: {best['rsi']:.1f}")
        if best['oversold_3d_avg'] is not None:
            print(f"     Dip Buy 3d Avg: {best['oversold_3d_avg']:+.2f}%")
    
    # Save
    json_path = REPORT_DIR / "weekend_hold_analysis.json"
    json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved to: {json_path}")

if __name__ == "__main__":
    main()
