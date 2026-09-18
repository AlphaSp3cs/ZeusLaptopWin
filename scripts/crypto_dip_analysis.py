#!/usr/bin/env python3
"""Deep crypto analysis — find oversold dip buys with liquidity for weekend."""
import json, pathlib, sys
import pandas as pd
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent / "bt"))
import bt_store as B

universe = json.loads(pathlib.Path(r"C:\Hermes\workflow\data\universe_comprehensive.json").read_text(encoding="utf-8"))
crypto_assets = {sym: data for sym, data in universe["assets"].items() if sym.endswith("-USD")}
crypto_syms = list(crypto_assets.keys())

frames = B.load_bars(crypto_syms)
print(f"Loaded {len(frames)} crypto symbols")

COMMON = None
for d in frames.values():
    COMMON = d.index if COMMON is None else COMMON.union(d.index)
COMMON = COMMON.sort_values()

results = []
for sym, df in frames.items():
    d = df.reindex(COMMON).ffill().infer_objects(copy=False)
    d = B.add_indicators(d)
    d = d.dropna()
    if len(d) < 50:
        continue
    
    c = d["close"]
    rsi = d["rsi"]
    price = c.iloc[-1]
    current_rsi = rsi.iloc[-1]
    
    lookback = min(len(c), 365)
    hist_low = c.iloc[-lookback:].min()
    hist_high = c.iloc[-lookback:].max()
    pct_rank = (price - hist_low) / (hist_high - hist_low) * 100 if hist_high > hist_low else 50
    
    rsi_lookback = rsi.iloc[-lookback:]
    vol = d["volume"].iloc[-lookback:]
    avg_vol = vol.mean()
    recent_vol = vol.iloc[-5:].mean()
    vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
    
    dist_from_low = (price - hist_low) / hist_low * 100 if hist_low > 0 else 0
    ret_30d = (c.iloc[-1] / c.iloc[-30] - 1) * 100 if len(c) >= 30 else 0
    ret_7d = (c.iloc[-1] / c.iloc[-7] - 1) * 100 if len(c) >= 7 else 0
    
    results.append({
        "symbol": sym, "price": price, "rsi": current_rsi,
        "pct_rank": pct_rank, "hist_low": hist_low, "hist_high": hist_high,
        "dist_from_low_pct": dist_from_low, "vol_ratio": vol_ratio,
        "avg_vol": avg_vol, "ret_7d": ret_7d, "ret_30d": ret_30d, "n_bars": len(c),
    })

df = pd.DataFrame(results).dropna()
liquid = df[df["avg_vol"] > 500_000].copy()

print(f"\nLiquid crypto (>$500K avg daily vol): {len(liquid)}")

# Oversold
oversold = liquid[liquid["rsi"] < 35].sort_values("rsi")
print(f"\n=== OVERSOLD (RSI < 35) ===")
for _, r in oversold.head(10).iterrows():
    print(f"  {r['symbol']:<12} RSI={r['rsi']:>5.1f}  ${r['price']:>10,.2f}  7d={r['ret_7d']:>+6.1f}%  Vol={r['vol_ratio']:.1f}x")

# Near historical low
near_low = liquid[liquid["dist_from_low_pct"] < 20].sort_values("dist_from_low_pct")
print(f"\n=== NEAR 1Y LOW (<20% above) ===")
for _, r in near_low.head(10).iterrows():
    print(f"  {r['symbol']:<12} ${r['price']:>10,.2f}  DistFromLow={r['dist_from_low_pct']:>5.1f}%  RSI={r['rsi']:>5.1f}  7d={r['ret_7d']:>+6.1f}%")

# Volume spike + dip
vol_dip = liquid[(liquid["vol_ratio"] > 2.0) & (liquid["ret_7d"] < -5)].sort_values("vol_ratio", ascending=False)
print(f"\n=== VOLUME SPIKE + DIP (Vol >2x, 7d <-5%) ===")
for _, r in vol_dip.head(10).iterrows():
    print(f"  {r['symbol']:<12} Vol={r['vol_ratio']:.1f}x  7d={r['ret_7d']:>+6.1f}%  RSI={r['rsi']:>5.1f}  ${r['price']:>10,.2f}")

# Best dip buy score
liquid["dip_score"] = (
    (100 - liquid["rsi"]) * 0.3 +
    (100 - liquid["pct_rank"]) * 0.3 +
    liquid["vol_ratio"].clip(0, 5) / 5 * 100 * 0.2 +
    (-liquid["ret_7d"]).clip(0, 50) / 50 * 100 * 0.2
)
best_dips = liquid.sort_values("dip_score", ascending=False)
print(f"\n=== BEST DIP BUY SCORES (RSI + percentile + vol + dip) ===")
for _, r in best_dips.head(15).iterrows():
    print(f"  {r['symbol']:<12} Score={r['dip_score']:>5.1f}  RSI={r['rsi']:>5.1f}  Pctl={r['pct_rank']:>5.1f}%  Vol={r['vol_ratio']:.1f}x  7d={r['ret_7d']:>+6.1f}%  30d={r['ret_30d']:>+6.1f}%")

# Top liquid coins
top_vol = liquid.sort_values("avg_vol", ascending=False)
print(f"\n=== TOP 15 BY LIQUIDITY ===")
for _, r in top_vol.head(15).iterrows():
    print(f"  {r['symbol']:<12} AvgVol={r['avg_vol']:>14,.0f}  RSI={r['rsi']:>5.1f}  7d={r['ret_7d']:>+6.1f}%  Pctl={r['pct_rank']:>5.1f}%")

# Save results
report = {
    "timestamp": pd.Timestamp.now().isoformat(),
    "oversold": oversold.head(10).to_dict("records"),
    "near_low": near_low.head(10).to_dict("records"),
    "vol_dip": vol_dip.head(10).to_dict("records"),
    "best_dips": best_dips.head(15).to_dict("records"),
    "top_liquid": top_vol.head(15).to_dict("records"),
}
pathlib.Path(r"C:\Hermes\workflow\reports\crypto_dip_analysis.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
print(f"\nSaved to C:\\Hermes\\workflow\\reports\\crypto_dip_analysis.json")
