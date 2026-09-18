#!/usr/bin/env python3
"""Gold-Crypto correlation + narrative analysis for best crypto longs."""
import json, pathlib, sys
import pandas as pd
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent / "bt"))
import bt_store as B

REPORT_DIR = pathlib.Path(r"C:\Hermes\workflow\backtest\reports")

GOLD = ["GC=F"]
SILVER = ["SI=F"]
COPPER = ["HG=F"]
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "DOGE-USD", 
           "AVAX-USD", "LINK-USD", "DOT-USD", "LTC-USD", "ZEC-USD", "DASH-USD", "NEAR-USD",
           "OP-USD", "TIA-USD", "WIF-USD", "DYDX-USD", "XMR-USD", "WLD-USD"]
FOREX = ["EURUSD=X", "GBPUSD=X", "USDJPY=X"]
INDICES = ["^GSPC", "^IXIC", "^VIX", "^TNX"]
ENERGY = ["CL=F", "NG=F"]

ALL_SYMBOLS = GOLD + SILVER + COPPER + CRYPTO + FOREX + INDICES + ENERGY

def load_all():
    frames = B.load_bars(ALL_SYMBOLS)
    if not frames:
        return None
    COMMON = None
    for d in frames.values():
        COMMON = d.index if COMMON is None else COMMON.union(d.index)
    COMMON = COMMON.sort_values()
    prepared = {}
    for sym, df in frames.items():
        d = df.reindex(COMMON).ffill().infer_objects(copy=False)
        d = B.add_indicators(d)
        d = d.dropna()
        if len(d) > 100:
            prepared[sym] = d["close"]
    return pd.DataFrame(prepared)

def calculate_all_correlations(df):
    returns = df.pct_change(fill_method=None).dropna()
    
    gold_ret = returns["GC=F"]
    gold_corrs = {}
    for col in returns.columns:
        if col == "GC=F":
            continue
        gold_corrs[col] = gold_ret.corr(returns[col])
    
    spx_ret = returns["^GSPC"] if "^GSPC" in returns.columns else None
    spx_corrs = {}
    if spx_ret is not None:
        for col in returns.columns:
            if col == "^GSPC":
                continue
            spx_corrs[col] = spx_ret.corr(returns[col])
    
    vix_ret = returns["^VIX"] if "^VIX" in returns.columns else None
    vix_corrs = {}
    if vix_ret is not None:
        for col in returns.columns:
            if col == "^VIX":
                continue
            vix_corrs[col] = vix_ret.corr(returns[col])
    
    return {"gold": gold_corrs, "spx": spx_corrs, "vix": vix_corrs}, returns

def calculate_beta(returns, market_col="GC=F"):
    market_ret = returns[market_col]
    betas = {}
    for col in returns.columns:
        if col == market_col:
            continue
        covariance = returns[col].cov(market_ret)
        variance = market_ret.var()
        betas[col] = covariance / variance if variance > 0 else 0
    return betas

def main():
    print("=" * 80)
    print("GOLD-CRYPTO CORRELATION + NARRATIVE ANALYSIS")
    print("=" * 80)
    
    df = load_all()
    if df is None:
        print("ERROR: Could not load data")
        return
    
    print(f"Loaded {len(df)} bars across {len(df.columns)} symbols")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    
    corrs, returns = calculate_all_correlations(df)
    gold_beta = calculate_beta(returns, "GC=F")
    
    crypto_syms = [s for s in returns.columns if s.endswith("-USD")]
    
    print(f"\n=== GOLD CORRELATION + BETA ===")
    print(f"{'Symbol':<12} {'Gold Corr':>10} {'Gold Beta':>10} {'SPX Corr':>10} {'VIX Corr':>10}")
    print("-" * 60)
    
    results = []
    for sym in crypto_syms:
        gc = corrs["gold"].get(sym, 0)
        gb = gold_beta.get(sym, 0)
        sc = corrs["spx"].get(sym, 0)
        vc = corrs["vix"].get(sym, 0)
        results.append({"symbol": sym, "gold_corr": gc, "gold_beta": gb, "spx_corr": sc, "vix_corr": vc})
        print(f"  {sym:<12} {gc:>+9.3f} {gb:>+9.3f} {sc:>+9.3f} {vc:>+9.3f}")
    
    results.sort(key=lambda x: -abs(x["gold_corr"]))
    
    print(f"\n=== RANKED BY GOLD CORRELATION ===")
    for i, r in enumerate(results[:10]):
        direction = "Positive" if r["gold_corr"] > 0 else "Negative"
        strength = "Very Strong" if abs(r["gold_corr"]) > 0.5 else "Strong" if abs(r["gold_corr"]) > 0.3 else "Moderate" if abs(r["gold_corr"]) > 0.15 else "Weak"
        print(f"  #{i+1}. {r['symbol']:<12} GoldCorr={r['gold_corr']:+.3f} ({direction} {strength})")
    
    print(f"\n=== BEST CRYPTO LONGS (Correlation + Narrative) ===")
    for r in results[:10]:
        sym = r["symbol"]
        narrative_parts = []
        if r["gold_corr"] > 0.1:
            narrative_parts.append("Follows gold up")
        elif r["gold_corr"] < -0.1:
            narrative_parts.append("Hedges gold down")
        if r["spx_corr"] > 0.2:
            narrative_parts.append("Tracks stocks")
        elif r["spx_corr"] < -0.1:
            narrative_parts.append("Hedges stocks")
        if r["vix_corr"] > 0.1:
            narrative_parts.append("Fear beneficiary")
        elif r["vix_corr"] < -0.1:
            narrative_parts.append("Calm beneficiary")
        if r["gold_beta"] > 0.5:
            narrative_parts.append("High gold beta")
        narrative = " | ".join(narrative_parts) if narrative_parts else "Idiosyncratic"
        print(f"  {sym:<12} Gold={r['gold_corr']:+.2f} Beta={r['gold_beta']:+.2f} -> {narrative}")
    
    report = {"timestamp": str(pd.Timestamp.now()), "correlations": corrs["gold"], "betas": gold_beta}
    json_path = REPORT_DIR / "gold_crypto_correlation_report.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved to: {json_path}")

if __name__ == "__main__":
    main()
