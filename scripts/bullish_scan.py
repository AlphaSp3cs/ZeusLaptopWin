"""BULLISH-ONLY QUICK SCAN — all sectors, fresh prices, tight filter."""
import json, sys, time, pathlib, subprocess
import urllib.request, urllib.error
from datetime import datetime, timezone

def fetch_json_yahoo(symbols, timeout=15):
    results = []
    for s in symbols:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{s}?interval=1d&range=1mo"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode())
            meta = data["chart"]["result"][0]["meta"]
            results.append({
                "symbol": s,
                "price": meta.get("regularMarketPrice", 0),
                "change_pct": meta.get("regularMarketChangePercent", 0),
                "chart": data,
            })
        except Exception as e:
            print(f"  {s}: ERROR {e}")
    return results

def main():
    print("=" * 70)
    print("BULLISH-ONLY ALL-SECTOR SCAN")
    print("=" * 70)
    
    # Broad universe for bullish-only scan
    us_equity = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLB", "XLRE", "XLU", "XLC", "SOXX", "KWEB"]
    bonds = ["TLT", "IEF", "SHY", "HYG", "LQD", "TIP"]
    commodities = ["GLD", "SLV", "USO", "UNG", "PDBC", "DBA"]
    indices = ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX", "^TNX"]
    fx = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X"]
    crypto = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "MATIC-USD"]
    
    all_syms = us_equity + bonds + commodities + indices + fx + crypto
    labels = (
        ["US_EQUITY"] * len(us_equity) +
        ["BONDS"] * len(bonds) +
        ["COMMODITIES"] * len(commodities) +
        ["INDICES"] * len(indices) +
        ["FX"] * len(fx) +
        ["CRYPTO"] * len(crypto)
    )
    
    print(f"Fetching {len(all_syms)} symbols...")
    results = fetch_json_yahoo(all_syms, timeout=15)
    
    bullish = []
    bearish = []
    
    for r in results:
        price = r.get("price", 0)
        change = r.get("change_pct", 0)
        sym = r["symbol"]
        idx = all_syms.index(sym)
        cat = labels[idx]
        
        if price <= 0:
            continue
        
        # Bullish filter: positive daily change + price > 0
        if change > 0.5:
            bullish.append({"symbol": sym, "category": cat, "price": price, "change_pct": round(change, 2)})
        elif change < -0.5:
            bearish.append({"symbol": sym, "category": cat, "price": price, "change_pct": round(change, 2)})
    
    print(f"\n{'=' * 70}")
    print(f"BULLISH ({len(bullish)}):")
    print(f"{'=' * 70}")
    for b in sorted(bullish, key=lambda x: -x["change_pct"]):
        print(f"  {b['symbol']:<12} {b['category']:<12} ${b['price']:>10,.2f}  +{b['change_pct']:.2f}%")
    
    print(f"\n{'=' * 70}")
    print(f"BEARISH ({len(bearish)}):")
    print(f"{'=' * 70}")
    for b in sorted(bearish, key=lambda x: x["change_pct"]):
        print(f"  {b['symbol']:<12} {b['category']:<12} ${b['price']:>10,.2f}  {b['change_pct']:.2f}%")
    
    # Save
    out = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "bullish_only_all_sector",
        "bullish": bullish,
        "bearish": bearish,
    }
    pathlib.Path.home().joinpath("bullish_scan_latest.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    
    print(f"\nSaved to ~/bullish_scan_latest.json")

if __name__ == "__main__":
    main()
