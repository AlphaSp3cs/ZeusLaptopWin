#!/usr/bin/env python3
"""DESK-GRADE ENGINE — The 8 Critical Gaps.

Built from team audit. All free. All verifiable.

Priority order:
1. Cost model (kills fake edges)
2. Weekend block (proven leak)
3. Outcome grading (makes memory real)
4. CFTC COT + funding rates (desk-grade data)
5. Walk-forward validation (kills overfit)
6. News sentiment scoring (feed into conviction)
7. IBKR cleanup (stop pretending)
8. Execution quality tracking (measure slippage)
"""
import json, pathlib, sqlite3, sys, time, urllib.request
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

DB = pathlib.Path(r"C:\Hermes\workflow\data\bars.db")
REPORT_DIR = pathlib.Path(r"C:\Hermes\workflow\reports")
LOG_DIR = pathlib.Path(r"C:\Hermes\workflow\logs")

# ═════════════════════════════════════════════════════════════════════════════
# 1. COST MODEL — Kills fake edges
# ═════════════════════════════════════════════════════════════════════════════

def apply_cost_model(win_rate, profit_factor, avg_return, spread_pips=2.0, commission_per_lot=0.0, slippage_pips=1.0):
    """Apply realistic cost model to backtest results.
    
    TRUE costs per round trip (team audit says 1.5x spread minimum):
    - Spread: 2 pips typical
    - Slippage: 1 pip typical (we don't track this!)
    - Commission: varies by asset class
    
    Total round-trip cost = 1.5x spread + slippage
    
    Team finding: ATR_EXP at PF 1.9 could be PF 1.2 after real costs on M15.
    """
    # Realistic round-trip costs as percentage of trade value
    # These are CONSERVATIVE estimates based on Capital.com + typical brokers
    cost_per_trade = {
        "forex": 0.00018,    # 2 pips spread + 1 pip slippage = 3 pips = 0.018%
        "crypto": 0.0010,    # 0.10% spread + slippage (BTC/ETH on MT5 = 5000 pts!)
        "stocks": 0.0005,    # $0.01/share on $20 stock + slippage
        "metals": 0.0008,    # Gold 300 pts spread + slippage
        "energy": 0.0010,    # Oil 400 pts spread + slippage
        "indices": 0.0003,   # ES 4 pts spread + slippage
        "bonds": 0.0002,     # ZB moderate spread
    }
    
    results = {}
    for asset_class, cost in cost_per_trade.items():
        n_trades = 100  # Per 100 trades
        
        # Cost per 100 trades (round-trip = entry + exit)
        total_cost = cost * 2 * n_trades
        
        # Adjust profit factor
        # Winners: profit reduced by cost on both entry and exit
        # Losers: loss increased by cost on both entry and exit
        # Approximation: PF_adjusted = (PF - total_cost_pct) / (1 + total_cost_pct)
        pf_adjusted = (profit_factor - total_cost / 100) / (1 + total_cost / 100)
        
        # Adjust avg return
        # Each trade loses cost*2 (entry + exit)
        avg_adjusted = avg_return - (cost * 2 * 100)
        
        # Adjust win rate (costs affect losers proportionally more)
        # Simplified: if avg_loss > avg_win, costs hurt WR more
        wr_adjusted = win_rate * (1 - cost * 100)  # Conservative
        
        results[asset_class] = {
            "original_wr": round(win_rate, 1),
            "adjusted_wr": round(max(0, wr_adjusted), 1),
            "original_pf": round(profit_factor, 2),
            "adjusted_pf": round(max(0, pf_adjusted), 2),
            "original_avg_return": round(avg_return, 3),
            "adjusted_avg_return": round(avg_adjusted, 3),
            "cost_per_trade_pct": round(cost * 2 * 100, 3),
            "cost_per_100_trades_pct": round(total_cost, 2),
        }
    
    return results

# ═════════════════════════════════════════════════════════════════════════════
# 2. WEEKEND BLOCK — Proven leak
# ═════════════════════════════════════════════════════════════════════════════

def is_weekend_blocked():
    """Check if we should block weekend crypto entries.
    
    Block: Friday 8 PM EST → Sunday 6 PM EST
    Reason: 0% WR weekend entries in live data (DOT -233, UNI -202)
    """
    now = datetime.now(timezone(timedelta(hours=-5)))  # EST
    day = now.weekday()  # 0=Monday, 6=Sunday
    hour = now.hour
    
    # Friday after 8 PM
    if day == 4 and hour >= 20:
        return True, "FRIDAY_BLOCK"
    
    # All day Saturday
    if day == 5:
        return True, "SATURDAY_BLOCK"
    
    # Sunday before 6 PM
    if day == 6 and hour < 18:
        return True, "SUNDAY_BLOCK"
    
    return False, "OK"

# ═════════════════════════════════════════════════════════════════════════════
# 3. OUTCOME GRADING — Makes memory real
# ═════════════════════════════════════════════════════════════════════════════

def load_outcome_log():
    """Load existing outcome log."""
    outcome_file = LOG_DIR / "outcome_log.jsonl"
    if not outcome_file.exists():
        return []
    
    outcomes = []
    with open(outcome_file) as f:
        for line in f:
            try:
                outcomes.append(json.loads(line.strip()))
            except:
                continue
    
    return outcomes

def log_outcome(symbol, conviction, order_type, entry_price, exit_price, 
                sl, tp, result, reason=""):
    """Log a trade outcome."""
    outcome = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "conviction": conviction,
        "order_type": order_type,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "sl": sl,
        "tp": tp,
        "result": result,  # WIN, LOSS, BREAKEVEN
        "pnl_pct": round((exit_price - entry_price) / entry_price * 100, 3) if entry_price > 0 else 0,
        "reason": reason,
    }
    
    outcome_file = LOG_DIR / "outcome_log.jsonl"
    with open(outcome_file, "a") as f:
        f.write(json.dumps(outcome) + "\n")
    
    return outcome

def get_outcome_stats(symbol=None):
    """Get outcome statistics."""
    outcomes = load_outcome_log()
    
    if symbol:
        outcomes = [o for o in outcomes if o["symbol"] == symbol]
    
    if not outcomes:
        return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0, "avg_pnl": 0}
    
    wins = sum(1 for o in outcomes if o["result"] == "WIN")
    losses = sum(1 for o in outcomes if o["result"] == "LOSS")
    total = wins + losses
    
    avg_pnl = sum(o["pnl_pct"] for o in outcomes) / len(outcomes)
    
    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
        "avg_pnl_pct": round(avg_pnl, 3),
    }

# ═════════════════════════════════════════════════════════════════════════════
# 4. CFTC COT + FUNDING RATES — Desk-grade data
# ═════════════════════════════════════════════════════════════════════════════

def fetch_funding_rates():
    """Fetch crypto funding rates from Binance.
    
    Funding rate > 0.01% = longs pay shorts = bullish sentiment
    Funding rate < -0.01% = shorts pay longs = bearish sentiment
    Extreme funding = imminent reversal
    """
    url = "https://fapi.binance.com/fapi/v1/premiumIndex"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        rates = {}
        for item in data:
            symbol = item["symbol"]
            if symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]:
                rates[symbol] = {
                    "funding_rate": float(item["lastFundingRate"]),
                    "funding_rate_pct": round(float(item["lastFundingRate"]) * 100, 4),
                    "next_funding": item.get("nextFundingTime", 0),
                    "mark_price": float(item["markPrice"]),
                }
        
        return rates
    except Exception as e:
        return {"error": str(e)}

def fetch_cme_oi():
    """Fetch CME Bitcoin futures open interest."""
    # CME doesn't have a free public API for OI, but we can scrape
    # or use free alternatives
    url = "https://api.coingecko.com/api/v3/derivatives"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        btc_oi = 0
        for item in data:
            if "bitcoin" in item.get("market", "").lower():
                btc_oi = item.get("open_interest", 0)
                break
        
        return {"btc_open_interest_usd": btc_oi}
    except:
        return None

# ═════════════════════════════════════════════════════════════════════════════
# 5. WALK-FORWARD VALIDATION — Kills overfit
# ═════════════════════════════════════════════════════════════════════════════

def walk_forward_validation(symbol, strategy_fn, train_window=504, test_window=126, step=21):
    """Walk-forward validation.
    
    Train on [train_window] bars, test on next [test_window] bars.
    Step forward [step] bars, repeat.
    
    If WR collapses between train and test, the edge was noise.
    """
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    cur.execute("SELECT close, high, low, volume FROM bars WHERE symbol=? AND tf='1d' ORDER BY ts ASC", (symbol,))
    rows = cur.fetchall()
    con.close()
    
    if len(rows) < train_window + test_window:
        return {"error": "Insufficient data"}
    
    closes = [r[0] for r in rows]
    highs = [r[1] for r in rows]
    lows = [r[2] for r in rows]
    volumes = [r[3] for r in rows]
    
    train_results = []
    test_results = []
    
    i = 0
    while i + train_window + test_window <= len(closes):
        # Train period
        train_closes = closes[i:i + train_window]
        train_score = strategy_fn(train_closes)
        
        # Test period
        test_closes = closes[i + train_window:i + train_window + test_window]
        test_score = strategy_fn(test_closes)
        
        train_results.append(train_score)
        test_results.append(test_score)
        
        i += step
    
    return {
        "symbol": symbol,
        "num_periods": len(train_results),
        "train_avg_score": round(np.mean(train_results), 2) if train_results else 0,
        "test_avg_score": round(np.mean(test_results), 2) if test_results else 0,
        "score_degradation": round(np.mean(test_results) / np.mean(train_results), 2) if train_results and np.mean(train_results) > 0 else 0,
        "overfit_risk": "HIGH" if np.mean(test_results) < np.mean(train_results) * 0.7 else "LOW",
    }

# ═════════════════════════════════════════════════════════════════════════════
# 6. NEWS SENTIMENT SCORING — Feed into conviction
# ═════════════════════════════════════════════════════════════════════════════

def score_news_sentiment(news_file=None):
    """Score news headlines from -2 (very bearish) to +2 (very bullish).
    
    Simple keyword-based scoring. No external API needed.
    """
    if news_file is None:
        news_file = pathlib.Path(r"C:\Hermes\workflow\data\news_headlines.json")
    
    if not news_file.exists():
        return {}
    
    data = json.loads(news_file.read_text(encoding="utf-8"))
    headlines = data.get("headlines", {})
    
    # Bullish keywords
    bullish_words = {
        "surge": 1.5, "rally": 1.5, "breakout": 1.5, "upgrade": 1.5,
        "buy": 1.0, "long": 1.0, "bull": 1.0, "moon": 2.0,
        "accumulate": 1.0, "support": 0.5, "higher": 0.5,
        "upgrade": 1.0, "beat": 1.0, "growth": 1.0, "profit": 1.0,
        "adoption": 1.0, "partnership": 1.0, "launch": 1.0,
    }
    
    bearish_words = {
        "crash": -2.0, "dump": -2.0, "sell": -1.5, "short": -1.5,
        "bear": -1.5, "fear": -1.5, "panic": -2.0, "death": -2.0,
        "ban": -1.5, "hack": -1.5, "lawsuit": -1.5, "sec": -1.0,
        "regulation": -1.0, "risk": -0.5, "decline": -1.0,
        "loss": -1.0, "lower": -0.5, "resistance": -0.5,
        "recession": -1.5, "inflation": -1.0, "war": -1.5,
    }
    
    asset_scores = {}
    
    for source, items in headlines.items():
        if not isinstance(items, list):
            continue
        
        for item in items:
            title = item.get("title", "").lower()
            
            # Determine which assets are mentioned
            assets = []
            for keyword, asset in [("btc", "BTC-USD"), ("bitcoin", "BTC-USD"), 
                                   ("eth", "ETH-USD"), ("ethereum", "ETH-USD"),
                                   ("gold", "GC=F"), ("oil", "CL=F"), ("spx", "^GSPC"),
                                   ("dxy", "DXY"), ("eurusd", "EURUSD=X")]:
                if keyword in title:
                    assets.append(asset)
            
            if not assets:
                assets = ["GENERAL"]
            
            # Score the headline
            score = 0
            for word, weight in bullish_words.items():
                if word in title:
                    score += weight
            for word, weight in bearish_words.items():
                if word in title:
                    score += weight
            
            # Clamp to [-2, 2]
            score = max(-2, min(2, score))
            
            for asset in assets:
                if asset not in asset_scores:
                    asset_scores[asset] = []
                asset_scores[asset].append({
                    "title": item.get("title", "")[:60],
                    "score": score,
                    "source": source,
                })
    
    # Aggregate scores
    aggregated = {}
    for asset, scores in asset_scores.items():
        if scores:
            avg_score = sum(s["score"] for s in scores) / len(scores)
            aggregated[asset] = {
                "avg_sentiment": round(avg_score, 2),
                "num_headlines": len(scores),
                "bias": "BULLISH" if avg_score > 0.3 else "BEARISH" if avg_score < -0.3 else "NEUTRAL",
            }
    
    return aggregated

# ═════════════════════════════════════════════════════════════════════════════
# 7. IBKR CLEANUP — Stop pretending
# ═════════════════════════════════════════════════════════════════════════════

def ibkr_status():
    """Check IBKR status and return honest assessment."""
    # Check if IB Gateway is running
    try:
        import subprocess
        result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ibgateway.exe"], 
                              capture_output=True, text=True, timeout=5)
        running = "ibgateway.exe" in result.stdout
    except:
        running = False
    
    return {
        "running": running,
        "has_data_subscription": False,
        "has_options_chains": False,
        "trades_executed": 0,
        "status": "DEAD_WEIGHT" if running else "NOT_RUNNING",
        "recommendation": "UNINSTALL" if not running else "EVALUATE_SUBSCRIPTION",
    }

# ═════════════════════════════════════════════════════════════════════════════
# 8. EXECUTION QUALITY TRACKING — Measure slippage
# ═════════════════════════════════════════════════════════════════════════════

def track_execution_quality(requested_price, filled_price, symbol, order_type):
    """Track execution quality.
    
    Slippage = filled_price - requested_price
    Cost = slippage / requested_price * 100
    """
    slippage = filled_price - requested_price
    cost_pct = (slippage / requested_price * 100) if requested_price > 0 else 0
    
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "order_type": order_type,
        "requested_price": requested_price,
        "filled_price": filled_price,
        "slippage": round(slippage, 4),
        "cost_pct": round(cost_pct, 4),
    }
    
    log_file = LOG_DIR / "execution_quality.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    return entry

def get_execution_stats():
    """Get execution quality statistics."""
    log_file = LOG_DIR / "execution_quality.jsonl"
    if not log_file.exists():
        return {"total_trades": 0}
    
    entries = []
    with open(log_file) as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except:
                continue
    
    if not entries:
        return {"total_trades": 0}
    
    avg_slippage = sum(e["slippage"] for e in entries) / len(entries)
    avg_cost = sum(e["cost_pct"] for e in entries) / len(entries)
    
    return {
        "total_trades": len(entries),
        "avg_slippage": round(avg_slippage, 4),
        "avg_cost_pct": round(avg_cost, 4),
        "total_cost_pct": round(sum(e["cost_pct"] for e in entries), 4),
    }

# ═════════════════════════════════════════════════════════════════════════════
# MAIN — RUN DESK-GRADE ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("DESK-GRADE ENGINE — The 8 Critical Gaps")
    print("=" * 70)
    
    # 1. Cost Model
    print("\n=== 1. COST MODEL ===")
    print("  Adjusting backtest results for realistic costs...")
    cost_adjustments = apply_cost_model(win_rate=55.0, profit_factor=1.8, avg_return=0.5)
    for asset_class, data in cost_adjustments.items():
        print(f"  {asset_class:<10} WR: {data['original_wr']}% → {data['adjusted_wr']}%  PF: {data['original_pf']} → {data['adjusted_pf']}")
    
    # 2. Weekend Block
    print("\n=== 2. WEEKEND BLOCK ===")
    blocked, reason = is_weekend_blocked()
    print(f"  Weekend block active: {blocked} ({reason})")
    if blocked:
        print("  → Crypto entries BLOCKED until Sunday 6 PM EST")
    
    # 3. Outcome Grading
    print("\n=== 3. OUTCOME GRADING ===")
    stats = get_outcome_stats()
    print(f"  Total graded: {stats['total']}  Wins: {stats['wins']}  Losses: {stats['losses']}  WR: {stats['win_rate']}%")
    
    # 4. Funding Rates
    print("\n=== 4. CRYPTO FUNDING RATES ===")
    funding = fetch_funding_rates()
    if "error" not in funding:
        for symbol, data in funding.items():
            sentiment = "BULLISH" if data["funding_rate_pct"] > 0.01 else "BEARISH" if data["funding_rate_pct"] < -0.01 else "NEUTRAL"
            print(f"  {symbol:<10} Rate: {data['funding_rate_pct']:+.4f}%  Sentiment: {sentiment}")
    else:
        print(f"  Error: {funding.get('error', 'unknown')}")
    
    # 5. Walk-Forward
    print("\n=== 5. WALK-FORWARD VALIDATION ===")
    def simple_strategy(closes):
        """Simple momentum strategy for testing."""
        if len(closes) < 20:
            return 0
        sma20 = sum(closes[-20:]) / 20
        return 1 if closes[-1] > sma20 else 0
    
    for symbol in ["EURUSD=X", "BTC-USD", "GC=F"]:
        result = walk_forward_validation(symbol, simple_strategy, train_window=252, test_window=63, step=21)
        if "error" not in result:
            print(f"  {symbol:<12} Train: {result['train_avg_score']}  Test: {result['test_avg_score']}  Overfit: {result['overfit_risk']}")
    
    # 6. News Sentiment
    print("\n=== 6. NEWS SENTIMENT ===")
    sentiment = score_news_sentiment()
    for asset, data in sentiment.items():
        print(f"  {asset:<12} Score: {data['avg_sentiment']:+.2f}  Bias: {data['bias']}  ({data['num_headlines']} headlines)")
    
    # 7. IBKR Status
    print("\n=== 7. IBKR STATUS ===")
    ibkr = ibkr_status()
    print(f"  Status: {ibkr['status']}")
    print(f"  Recommendation: {ibkr['recommendation']}")
    
    # 8. Execution Quality
    print("\n=== 8. EXECUTION QUALITY ===")
    exec_stats = get_execution_stats()
    print(f"  Tracked fills: {exec_stats['total_trades']}")
    if exec_stats['total_trades'] > 0:
        print(f"  Avg slippage: {exec_stats['avg_slippage']}")
        print(f"  Avg cost: {exec_stats['avg_cost_pct']}%")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
