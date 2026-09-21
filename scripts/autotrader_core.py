#!/usr/bin/env python3
"""AUTO-TRADER CORE — 24/7 fire-without-asking system.

Runs every 15 minutes via cron/job scheduler.
Scans → Scores → Checks drift → Passes gates → Fires → Logs.

Usage:
    python3 autotrader_core.py              # Single cycle
    python3 autotrader_core.py --loop       # Run every 15 min forever
    python3 autotrader_core.py --check      # Check pending orders only
"""
import json, pathlib, sqlite3, sys, time, os, subprocess
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

# Paths
WORKFLOW = pathlib.Path("C:/Hermes/workflow")
DB = WORKFLOW / "data" / "bars.db"
SCAN_FILE = WORKFLOW / "data" / "comprehensive_setups.json"
BT_FILE = WORKFLOW / "data" / "backtest_priority.json"
CONVICTION_FILE = WORKFLOW / "data" / "autotrader_convictions.json"
LOG_FILE = WORKFLOW / "logs" / "autotrader_fires.jsonl"
MEMORY_FILE = WORKFLOW / "data" / "autotrader_memory.json"

# MT5 executable
MT5_PYTHON = r"C:\Users\victo\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
MT5_ORDER_MGR = r"C:\Users\victo\mt5_order_manager.py"

# Risk params
MAX_RISK_PER_TRADE = 0.02  # 2%
MAX_PORTFOLIO_RISK = 0.05  # 5%
MIN_CONVICTION_FIRE = 60.0  # Conviction threshold to fire
MIN_HIT_RATE = 0.40  # 40% historical fill rate for limits

# Quality gates
GATES = {
    "min_conviction": 60.0,
    "min_backtest_wr": 40.0,  # If backtest data exists
    "min_rr": 1.5,
    "max_spread_pct": 2.0,  # Max 2% spread
    "min_hit_rate": 0.30,  # At least 30% chance limit fills
    "max_drift_down": -10.0,  # Don't fire if conviction dropped >10 points
    "min_atr_ratio": 0.8,  # ATR not contracting too much
}

# ═════════════════════════════════════════════════════════════════════════════
# CONVICTION SCORER
# ═════════════════════════════════════════════════════════════════════════════

def load_scan():
    """Load scan setups."""
    if not SCAN_FILE.exists():
        return []
    data = json.loads(SCAN_FILE.read_text(encoding="utf-8"))
    setups = []
    for sec_name, items in data.get("sectors", {}).items():
        for s in items:
            s["sector"] = sec_name
            setups.append(s)
    return setups

def load_backtest():
    """Load backtest lookup."""
    if not BT_FILE.exists():
        return {}
    bt = json.loads(BT_FILE.read_text(encoding="utf-8"))
    return {r["symbol"]: r for r in bt}

def compute_conviction(scan_score, backtest_data, rr, change_pct, atr_ratio=1.0):
    """Compute composite conviction (0-100)."""
    scan_component = min(scan_score / 6, 1.0) * 30
    wr_component = min(backtest_data.get("win_20d", 0) / 70, 1.0) * 25 if backtest_data else 5
    avg_component = min(backtest_data.get("avg_20d", 0) / 10, 1.0) * 15 if backtest_data else 3
    rr_component = min(rr / 3, 1.0) * 15
    momentum_component = min(abs(change_pct) / 10, 1.0) * 15
    return round(scan_component + wr_component + avg_component + rr_component + momentum_component, 1)

def check_drift(symbol, current_conviction):
    """Check if conviction is rising or falling vs last scan."""
    if not CONVICTION_FILE.exists():
        return 0.0, "new"
    
    history = json.loads(CONVICTION_FILE.read_text(encoding="utf-8"))
    prev = history.get(symbol)
    
    if not prev:
        return 0.0, "new"
    
    prev_conv = prev.get("conviction", 0)
    drift = current_conviction - prev_conv
    
    if drift > 5:
        direction = "rising"
    elif drift < -5:
        direction = "falling"
    else:
        direction = "stable"
    
    return drift, direction

# ═════════════════════════════════════════════════════════════════════════════
# QUALITY GATES
# ═════════════════════════════════════════════════════════════════════════════

def check_gates(symbol, conviction, backtest_data, rr, atr_ratio, spread_pct, hit_rate):
    """Check all quality gates. Returns (passed, reasons)."""
    reasons = []
    
    # Gate 1: Min conviction
    if conviction < GATES["min_conviction"]:
        reasons.append(f"conviction {conviction} < {GATES['min_conviction']}")
    
    # Gate 2: Min backtest WR (if data exists)
    if backtest_data:
        wr = backtest_data.get("win_20d", 0)
        if wr < GATES["min_backtest_wr"]:
            reasons.append(f"WR {wr}% < {GATES['min_backtest_wr']}%")
    
    # Gate 3: Min RR
    if rr < GATES["min_rr"]:
        reasons.append(f"RR {rr} < {GATES['min_rr']}")
    
    # Gate 4: Max spread
    if spread_pct > GATES["max_spread_pct"]:
        reasons.append(f"spread {spread_pct:.2f}% > {GATES['max_spread_pct']}%")
    
    # Gate 5: Min hit rate for limits
    if hit_rate < GATES["min_hit_rate"]:
        reasons.append(f"hit rate {hit_rate:.0%} < {GATES['min_hit_rate']:.0%}")
    
    # Gate 6: ATR not contracting too much
    if atr_ratio < GATES["min_atr_ratio"]:
        reasons.append(f"ATR ratio {atr_ratio:.2f} < {GATES['min_atr_ratio']}")
    
    # Gate 7: Drift check
    drift, direction = check_drift(symbol, conviction)
    if drift < GATES["max_drift_down"]:
        reasons.append(f"conviction drifting down {drift:.1f} points")
    
    passed = len(reasons) == 0
    return passed, reasons

# ═════════════════════════════════════════════════════════════════════════════
# MT5 EXECUTION
# ═════════════════════════════════════════════════════════════════════════════

def get_mt5_price(mt5_symbol):
    """Get current MT5 price via inline script."""
    try:
        result = subprocess.run([
            MT5_PYTHON, "-c",
            f"""
import MetaTrader5 as mt5
if mt5.initialize():
    mt5.symbol_select('{mt5_symbol}', True)
    tick = mt5.symbol_info_tick('{mt5_symbol}')
    info = mt5.symbol_info('{mt5_symbol}')
    if tick and info and tick.bid > 0:
        spread_pct = (tick.ask - tick.bid) / tick.bid * 100
        print(f"{{tick.bid}}|{{tick.ask}}|{{spread_pct:.4f}}|{{info.trade_mode}}")
    else:
        print("0|0|0|closed")
    mt5.shutdown()
else:
    print("0|0|0|error")
"""
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("|")
            if len(parts) == 4:
                bid, ask, spread_pct, trade_mode = parts
                return {
                    "bid": float(bid),
                    "ask": float(ask),
                    "spread_pct": float(spread_pct),
                    "trade_mode": trade_mode
                }
    except Exception as e:
        pass
    
    return {"bid": 0, "ask": 0, "spread_pct": 0, "trade_mode": "unknown"}

def fire_order(symbol, mt5_symbol, order_type, lots, price, sl, tp):
    """Fire order via MT5 order manager."""
    try:
        if order_type == "market":
            cmd = [MT5_PYTHON, MT5_ORDER_MGR, "--buy-market", mt5_symbol, "--lots", str(lots), "--sl", str(sl), "--tp", str(tp)]
        elif order_type == "limit":
            cmd = [MT5_PYTHON, MT5_ORDER_MGR, "--buy-limit", mt5_symbol, "--price", str(price), "--lots", str(lots), "--sl", str(sl), "--tp", str(tp)]
        else:
            return False, f"Unknown order type: {order_type}"
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and "SUCCESS" in result.stdout:
            return True, result.stdout.strip()
        else:
            return False, result.stdout.strip() + result.stderr.strip()
    except Exception as e:
        return False, str(e)

# ═════════════════════════════════════════════════════════════════════════════
# MEMORY BANK
# ═════════════════════════════════════════════════════════════════════════════

def load_memory():
    """Load autotrader memory."""
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    return {"fires": [], "stats": {"total_fires": 0, "total_wins": 0, "total_losses": 0}}

def save_memory(memory):
    """Save autotrader memory."""
    MEMORY_FILE.write_text(json.dumps(memory, indent=2, default=str), encoding="utf-8")

def log_fire(symbol, conviction, drift, gates_passed, order_type, lots, price, sl, tp, result, reason=""):
    """Log a fire event."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "conviction": conviction,
        "drift": drift,
        "gates_passed": gates_passed,
        "order_type": order_type,
        "lots": lots,
        "price": price,
        "sl": sl,
        "tp": tp,
        "result": result,
        "reason": reason
    }
    
    # Append to log file
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    
    # Update memory
    memory = load_memory()
    memory["fires"].append(entry)
    memory["stats"]["total_fires"] += 1
    save_memory(memory)

def save_convictions(convictions):
    """Save current convictions for drift tracking."""
    CONVICTION_FILE.write_text(json.dumps(convictions, indent=2, default=str), encoding="utf-8")

# ═════════════════════════════════════════════════════════════════════════════
# MAIN CYCLE
# ═════════════════════════════════════════════════════════════════════════════

def run_cycle():
    """Run one full cycle: scan → score → check gates → fire."""
    print(f"\n{'='*70}")
    print(f"AUTO-TRADER CYCLE — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print('='*70)
    
    # Load data
    setups = load_scan()
    bt_lookup = load_backtest()
    
    if not setups:
        print("No scan data available. Run scan first.")
        return
    
    # MT5 symbol mapping
    MT5_MAP = {
        "BTC-USD": "BTCUSD", "ETH-USD": "ETHUSD", "SOL-USD": "SOLUSD",
        "BNB-USD": "BNBUSD", "XRP-USD": "XRPUSD", "ADA-USD": "ADAUSD",
        "DOGE-USD": "DOGEUSD", "AVAX-USD": "AVAXUSD", "LINK-USD": "LINKUSD",
        "DOT-USD": "DOTUSD", "LTC-USD": "LTCUSD", "UNI-USD": "UNIUSD",
        "GC=F": "XAUUSD", "SI=F": "XAGUSD", "PL=F": "XPTUSD", "PA=F": "XPDUSD",
        "NG=F": "NATGAS",
        "^GSPC": "US500", "^IXIC": "US100", "^DJI": "US30",
        "AAPL": "AAPL", "AMZN": "AMZN", "GOOGL": "GOOGL", "MSFT": "MSFT",
        "PLTR": "PLTR", "COIN": "COIN",
    }
    
    # Score all setups
    scored = []
    for s in setups:
        sym = s.get("symbol", "")
        score = s.get("score", 0)
        bt_data = bt_lookup.get(sym, {})
        rr = s.get("rr", 0)
        change = s.get("change_pct", 0)
        conviction = compute_conviction(score, bt_data, rr, change)
        mt5_sym = MT5_MAP.get(sym)
        
        scored.append({
            "symbol": sym,
            "mt5": mt5_sym,
            "score": score,
            "conviction": conviction,
            "backtest": bt_data,
            "rr": rr,
            "change": change,
            "rsi": s.get("rsi", 50),
            "entry": s.get("entry", 0),
            "sl": s.get("stop_loss", 0),
            "tp": s.get("tp1", 0),
            "sector": s.get("sector", ""),
        })
    
    # Sort by conviction
    scored.sort(key=lambda x: -x["conviction"])
    
    # Save convictions for drift tracking
    conviction_map = {s["symbol"]: {"conviction": s["conviction"], "timestamp": datetime.now(timezone.utc).isoformat()} for s in scored}
    save_convictions(conviction_map)
    
    # Get existing positions to avoid doubling
    existing_positions = set()
    try:
        pos_result = subprocess.run([MT5_PYTHON, MT5_ORDER_MGR, "--positions"], capture_output=True, text=True, timeout=15)
        for line in pos_result.stdout.split("\n"):
            parts = line.split()
            if len(parts) >= 2 and parts[0] != "Ticket":
                existing_positions.add(parts[1])
    except:
        pass
    
    # Check top candidates
    fired = 0
    for s in scored[:15]:
        # Skip if already in position
        if s.get("mt5") in existing_positions:
            print(f"\n  {s['symbol']:<12} Already in position — skip")
            continue
        sym = s["symbol"]
        mt5_sym = s["mt5"]
        conviction = s["conviction"]
        
        if not mt5_sym:
            continue
        
        if conviction < MIN_CONVICTION_FIRE:
            print(f"\n  {sym:<12} Conviction {conviction} — below threshold, skip")
            continue
        
        # Get live price
        price_data = get_mt5_price(mt5_sym)
        if price_data["trade_mode"] == "closed":
            print(f"\n  {sym:<12} Market closed — skip")
            continue
        
        if price_data["bid"] <= 0:
            print(f"\n  {sym:<12} No price data — skip")
            continue
        
        spread_ok = price_data["spread_pct"] < GATES["max_spread_pct"]
        
        # Check gates
        passed, reasons = check_gates(
            sym, conviction, s["backtest"], s["rr"],
            atr_ratio=1.0,  # Would need ATR calc
            spread_pct=price_data["spread_pct"],
            hit_rate=0.5 if s["score"] >= 5 else 0.3
        )
        
        if not passed:
            print(f"\n  {sym:<12} Conviction {conviction} — gates failed: {', '.join(reasons)}")
            continue
        
        # Fire!
        print(f"\n  🔥 FIRING {sym:<12} Conviction={conviction} RR={s['rr']} Spread={price_data['spread_pct']:.2f}%")
        
        # Determine order type
        current_price = price_data["ask"]
        if current_price <= s["entry"] * 1.02:  # Within 2% of entry
            order_type = "market"
            fire_price = None
        else:
            order_type = "limit"
            fire_price = s["entry"]
        
        # Calculate lots (simplified)
        lots = 0.01  # Default small size
        
        success, result = fire_order(
            sym, mt5_sym, order_type, lots,
            fire_price, s["sl"], s["tp"]
        )
        
        # Log
        drift, direction = check_drift(sym, conviction)
        log_fire(sym, conviction, drift, True, order_type, lots, fire_price or current_price, s["sl"], s["tp"], success, result)
        
        if success:
            print(f"    ✅ FIRED: {result[:100]}")
            fired += 1
        else:
            print(f"    ❌ FAILED: {result[:100]}")
        
        # Only fire 1 trade per cycle to avoid over-exposure
        break
    
    print(f"\n{'='*70}")
    print(f"CYCLE COMPLETE: {fired} trade(s) fired")
    print(f"{'='*70}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--loop":
        print("AUTO-TRADER LOOP — Running every 15 minutes. Ctrl+C to stop.")
        while True:
            try:
                run_cycle()
            except Exception as e:
                print(f"ERROR: {e}")
                import traceback
                traceback.print_exc()
            
            print(f"\nNext cycle in 15 minutes...")
            time.sleep(900)  # 15 minutes
    else:
        run_cycle()

if __name__ == "__main__":
    main()
