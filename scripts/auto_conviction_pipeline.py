#!/usr/bin/env python3
"""AUTO-BACKTEST PIPELINE — Scan → Backtest → Ranked Conviction.

Reads scan_comprehensive_setups.json → takes top 10 by score → runs
ATR expansion backtest → combines scan score + backtest conviction
→ outputs single ranked list.

Usage:
    python3 auto_conviction_pipeline.py
    python3 auto_conviction_pipeline.py --top 15
    python3 auto_conviction_pipeline.py --min-score 5
"""
import json, pathlib, sqlite3, sys, time
from datetime import datetime, timezone
import pandas as pd
import numpy as np

DB = pathlib.Path("C:/Hermes/workflow/data/bars.db")
SCAN_FILE = pathlib.Path("C:/Hermes/workflow/data/comprehensive_setups.json")
BT_FILE = pathlib.Path("C:/Hermes/workflow/data/backtest_priority.json")
OUTPUT_FILE = pathlib.Path("C:/Hermes/workflow/reports/ranked_conviction_latest.json")

# MT5 symbol mapping (expanded)
MT5_MAP = {
    # Crypto (14)
    "BTC-USD": "BTCUSD", "ETH-USD": "ETHUSD", "SOL-USD": "SOLUSD",
    "BNB-USD": "BNBUSD", "XRP-USD": "XRPUSD", "ADA-USD": "ADAUSD",
    "DOGE-USD": "DOGEUSD", "AVAX-USD": "AVAXUSD", "LINK-USD": "LINKUSD",
    "DOT-USD": "DOTUSD", "LTC-USD": "LTCUSD", "ZEC-USD": "ZECUSD",
    "DASH-USD": "DASHUSD", "NEAR-USD": "NEARUSD", "XMR-USD": "XMRUSD",
    "ALGO-USD": "ALGOUSD", "HBAR-USD": "HBARUSD", "CRV-USD": "CRVUSD",
    "UNI-USD": "UNIUSD", "XLM-USD": "XLMUSD",
    # Metals (4)
    "GC=F": "XAUUSD", "SI=F": "XAGUSD", "PL=F": "XPTUSD", "PA=F": "XPDUSD",
    # Energy (3)
    "NG=F": "NATGAS", "CL=F": "CRUDEOIL", "BZ=F": "BRENTOIL",
    # Indices (7)
    "^GSPC": "US500", "^IXIC": "US100", "^DJI": "US30",
    "^FTSE": "UK100", "^N225": "JP225", "^AXJO": "AU200", "^VIX": "VIX",
    # US Stocks (14+)
    "AAPL": "AAPL", "AMZN": "AMZN", "GOOGL": "GOOGL", "MSFT": "MSFT",
    "PLTR": "PLTR", "COIN": "COIN", "AMD": "AMD", "AVGO": "AVGO",
    "INTC": "INTC", "TSLA": "TSLA", "META": "META", "NVDA": "NVDA",
    "NFLX": "NFLX", "BA": "BA", "BABA": "BABA",
    # Commodities (via yfinance)
    "ZC=F": "CORN", "ZW=F": "WHEAT", "ZS=F": "SOYBEAN",
    "KC=F": "COFFEE", "CC=F": "COCOA", "SB=F": "SUGAR",
    "CT=F": "COTTON",
}

# Score weights
WEIGHT_SCAN = 0.30
WEIGHT_BACKTEST_WR = 0.25
WEIGHT_BACKTEST_AVG = 0.15
WEIGHT_RR = 0.15
WEIGHT_MOMENTUM = 0.15

def load_scan():
    """Load and flatten scan setups."""
    data = json.loads(SCAN_FILE.read_text(encoding="utf-8"))
    setups = []
    for sec_name, sec_setups in data.get("sectors", {}).items():
        for s in sec_setups:
            s["sector"] = sec_name
            setups.append(s)
    return setups

def load_backtest():
    """Load backtest lookup."""
    if BT_FILE.exists():
        bt = json.loads(BT_FILE.read_text(encoding="utf-8"))
        return {r["symbol"]: r for r in bt}
    return {}

def calc_atr(highs, lows, closes, period=14):
    """Calculate ATR."""
    if len(closes) < period + 1:
        return 0
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    if not trs:
        return 0
    atr = sum(trs[:period]) / period
    for t in trs[period:]:
        atr = (atr * (period - 1) + t) / period
    return atr

def backtest_atr_expansion(symbol, df):
    """Simple ATR expansion backtest on daily bars."""
    if df is None or len(df) < 60:
        return None
    
    closes = df['close'].tolist()
    highs = df['high'].tolist()
    lows = df['low'].tolist()
    
    # Calculate ATR series
    atrs = []
    for i in range(len(closes)):
        if i < 14:
            atrs.append(0)
        else:
            atr = calc_atr(highs[:i+1], lows[:i+1], closes[:i+1])
            atrs.append(atr)
    
    # ATR expansion: current ATR > 1.5x average of last 20 ATRs
    if len(atrs) < 40:
        return None
    
    avg_atr_20 = np.mean(atrs[-21:-1])
    current_atr = atrs[-1]
    
    if avg_atr_20 == 0:
        return None
    
    atr_ratio = current_atr / avg_atr_20
    
    # Win rate: count days where close > previous close
    wins = sum(1 for i in range(-20, 0) if closes[i] > closes[i-1])
    win_rate = wins / 20 * 100
    
    # Avg return
    returns = [(closes[i] - closes[i-1]) / closes[i-1] * 100 for i in range(-20, 0)]
    avg_return = np.mean(returns)
    
    # Max drawdown
    peak = closes[-20]
    max_dd = 0
    for c in closes[-20:]:
        if c > peak:
            peak = c
        dd = (peak - c) / peak * 100
        if dd > max_dd:
            max_dd = dd
    
    # Profit factor
    gains = sum(r for r in returns if r > 0)
    losses = abs(sum(r for r in returns if r < 0))
    pf = gains / losses if losses > 0 else float('inf')
    
    return {
        "atr_ratio": round(atr_ratio, 3),
        "atr_expanding": atr_ratio > 1.5,
        "win_rate": round(win_rate, 1),
        "avg_return_20d": round(avg_return, 3),
        "max_drawdown": round(max_dd, 2),
        "profit_factor": round(pf, 3),
        "bars_tested": len(closes),
    }

def compute_conviction(scan_score, backtest_data, rr, change_pct):
    """Compute composite conviction score (0-100)."""
    # Scan score component (max 6 → 30 pts)
    scan_component = min(scan_score / 6, 1.0) * 30
    
    # Backtest WR component (max 70% → 25 pts)
    if backtest_data:
        wr_component = min(backtest_data.get("win_20d", 0) / 70, 1.0) * 25
    else:
        wr_component = 5  # Neutral if no data
    
    # Backtest avg return component (max 10% → 15 pts)
    if backtest_data:
        avg_component = min(backtest_data.get("avg_20d", 0) / 10, 1.0) * 15
    else:
        avg_component = 3
    
    # RR component (max 3:1 → 15 pts)
    rr_component = min(rr / 3, 1.0) * 15
    
    # Momentum component (max 10% → 15 pts)
    momentum_component = min(abs(change_pct) / 10, 1.0) * 15
    
    total = scan_component + wr_component + avg_component + rr_component + momentum_component
    return round(total, 1)

def main():
    print("=" * 80)
    print("AUTO CONVICTION PIPELINE")
    print("=" * 80)
    
    # Load data
    setups = load_scan()
    bt_lookup = load_backtest()
    
    print(f"Loaded {len(setups)} scan setups, {len(bt_lookup)} backtest entries")
    
    # Filter: score >= 4
    candidates = [s for s in setups if s.get("score", 0) >= 4]
    print(f"Candidates (score >= 4): {len(candidates)}")
    
    # Sort by score
    candidates.sort(key=lambda x: -x.get("score", 0))
    
    # Take top N
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--top" else 10
    candidates = candidates[:top_n]
    
    # Connect to bars DB
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    
    results = []
    
    for i, s in enumerate(candidates):
        sym = s.get("symbol", "")
        mt5 = MT5_MAP.get(sym, "")
        
        # Get bars
        cur.execute("""
            SELECT ts, open, high, low, close, volume
            FROM bars WHERE symbol=? AND tf='1d'
            ORDER BY ts ASC
        """, (sym,))
        rows = cur.fetchall()
        
        if not rows or len(rows) < 30:
            print(f"  [{i+1}/{len(candidates)}] {sym}: insufficient data")
            continue
        
        df = pd.DataFrame(rows, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
        
        # Run ATR expansion backtest
        bt_result = backtest_atr_expansion(sym, df)
        
        # Get backtest WR from priority file
        bt_priority = bt_lookup.get(sym, {})
        
        # Compute conviction
        conviction = compute_conviction(
            scan_score=s.get("score", 0),
            backtest_data=bt_priority,
            rr=s.get("rr", 0),
            change_pct=s.get("change_pct", 0)
        )
        
        result = {
            "rank": len(results) + 1,
            "symbol": sym,
            "mt5": mt5,
            "sector": s.get("sector", ""),
            "conviction": conviction,
            "scan_score": s.get("score", 0),
            "current_price": s.get("entry", 0),
            "change_pct": s.get("change_pct", 0),
            "rsi": s.get("rsi", 0),
            "rr": s.get("rr", 0),
            "atr_expansion": bt_result,
            "backtest_priority": bt_priority,
            "signals": s.get("signals", []),
            "entry": s.get("entry", 0),
            "stop_loss": s.get("stop_loss", 0),
            "tp1": s.get("tp1", 0),
        }
        
        results.append(result)
        
        atr_str = f"ATR={bt_result['atr_ratio']:.2f}x" if bt_result else "N/A"
        wr_str = f"WR={bt_priority.get('win_20d', 'N/A')}%" if bt_priority else "N/A"
        
        print(f"  [{i+1}/{len(candidates)}] {sym:<12} Score={s.get('score',0)}  {atr_str}  {wr_str}  Conviction={conviction}")
        
        time.sleep(0.05)
    
    con.close()
    
    # Sort by conviction
    results.sort(key=lambda x: -x["conviction"])
    
    # Re-rank
    for i, r in enumerate(results):
        r["rank"] = i + 1
    
    # Save output
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidates_analyzed": len(candidates),
        "candidates_scored": len(results),
        "ranked_list": results,
    }
    
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    
    # Print ranked list
    print(f"\n{'='*80}")
    print("RANKED CONVICTION LIST")
    print("=" * 80)
    
    for r in results:
        mt5_flag = "✅" if r["mt5"] else "❌"
        atr_flag = "🔥" if r["atr_expansion"] and r["atr_expansion"].get("atr_expanding") else ""
        wr_str = f"WR={r['backtest_priority'].get('win_20d', 'N/A')}%" if r['backtest_priority'] else "WR=N/A"
        
        print(f"\n  #{r['rank']} {r['symbol']:<12} MT5:{mt5_flag} Conviction={r['conviction']:.1f}/100")
        print(f"    Score={r['scan_score']}  {wr_str}  RSI={r['rsi']:.1f}  Chg={r['change_pct']:>+6.2f}%  {atr_flag}")
        print(f"    Entry=${r['entry']:.4f}  SL=${r['stop_loss']:.4f}  TP1=${r['tp1']:.4f}")
        if r["mt5"]:
            print(f"    → TRADE on MT5: {r['mt5']}")
    
    print(f"\n{'='*80}")
    print(f"Output saved to: {OUTPUT_FILE}")
    print("=" * 80)

if __name__ == "__main__":
    main()
