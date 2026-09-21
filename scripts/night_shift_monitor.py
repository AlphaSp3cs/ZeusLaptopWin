#!/usr/bin/env python3
"""NIGHT SHIFT MONITOR — 10 PM to 4 AM EST.

Crypto and forex scan every 15 min.
Auto-fire high-conviction setups.

Usage:
    python3 night_shift_monitor.py --start    # Start monitoring
    python3 night_shift_monitor.py --stop     # Stop monitoring
    python3 night_shift_monitor.py --status   # Check status
"""
import json, pathlib, sqlite3, sys, time, subprocess, os, signal
from datetime import datetime, timezone, timedelta

WORKFLOW = pathlib.Path("C:/Hermes/workflow")
DB = WORKFLOW / "data" / "bars.db"
SCAN_FILE = WORKFLOW / "data" / "comprehensive_setups.json"
BT_FILE = WORKFLOW / "data" / "backtest_priority.json"
LOG_FILE = WORKFLOW / "logs" / "night_shift_fires.jsonl"
PID_FILE = WORKFLOW / "data" / "night_shift.pid"

MT5_PYTHON = r"C:\Users\victo\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
MT5_ORDER_MGR = r"C:\Users\victo\mt5_order_manager.py"

# Night shift hours (EST)
NIGHT_START = 22  # 10 PM
NIGHT_END = 4     # 4 AM

# Thresholds
MIN_CONVICTION = 60
MAX_SPREAD_PCT = 2.0

# MT5 symbols available 24/7
NIGHT_SYMBOLS = {
    "BTC-USD": "BTCUSD", "ETH-USD": "ETHUSD", "BNB-USD": "BNBUSD",
    "XRP-USD": "XRPUSD", "ADA-USD": "ADAUSD", "DOGE-USD": "DOGEUSD",
    "AVAX-USD": "AVAXUSD", "LINK-USD": "LINKUSD", "DOT-USD": "DOTUSD",
    "LTC-USD": "LTCUSD", "UNI-USD": "UNIUSD",
    "EURUSD=X": "EURUSD", "GBPUSD=X": "GBPUSD", "USDJPY=X": "USDJPY",
    "AUDUSD=X": "AUDUSD", "USDCAD=X": "USDCAD", "USDCHF=X": "USDCHF",
    "NZDUSD=X": "NZDUSD",
}

def is_night_shift():
    """Check if current time is within night shift hours."""
    now = datetime.now(timezone(timedelta(hours=-5)))  # EST
    hour = now.hour
    
    if NIGHT_START <= hour or hour < NIGHT_END:
        return True
    return False

def get_mt5_price(mt5_symbol):
    """Get current MT5 price."""
    try:
        result = subprocess.run([
            MT5_PYTHON, "-c",
            f"""
import MetaTrader5 as mt5
if mt5.initialize():
    mt5.symbol_select('{mt5_symbol}', True)
    tick = mt5.symbol_info_tick('{mt5_symbol}')
    if tick and tick.bid > 0:
        spread_pct = (tick.ask - tick.bid) / tick.bid * 100
        print(f"{{tick.bid}}|{{tick.ask}}|{{spread_pct:.2f}}")
    else:
        print("0|0|0")
    mt5.shutdown()
else:
    print("0|0|0")
"""
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("|")
            if len(parts) == 3:
                return {
                    "bid": float(parts[0]),
                    "ask": float(parts[1]),
                    "spread_pct": float(parts[2])
                }
    except:
        pass
    
    return {"bid": 0, "ask": 0, "spread_pct": 999}

def load_scan():
    """Load scan data."""
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
    if BT_FILE.exists():
        bt = json.loads(BT_FILE.read_text(encoding="utf-8"))
        return {r["symbol"]: r for r in bt}
    return {}

def compute_conviction(scan_score, backtest_data, rr, change_pct):
    """Compute composite conviction."""
    scan_component = min(scan_score / 6, 1.0) * 30
    wr_component = min(backtest_data.get("win_20d", 0) / 70, 1.0) * 25 if backtest_data else 5
    avg_component = min(backtest_data.get("avg_20d", 0) / 10, 1.0) * 15 if backtest_data else 3
    rr_component = min(rr / 3, 1.0) * 15
    momentum_component = min(abs(change_pct) / 10, 1.0) * 15
    return round(scan_component + wr_component + avg_component + rr_component + momentum_component, 1)

def run_cycle():
    """Run one night shift cycle."""
    if not is_night_shift():
        return False, "Not night shift hours"
    
    setups = load_scan()
    bt_lookup = load_backtest()
    
    if not setups:
        return False, "No scan data"
    
    # Score setups
    scored = []
    for s in setups:
        sym = s.get("symbol", "")
        if sym not in NIGHT_SYMBOLS:
            continue
        
        score = s.get("score", 0)
        bt_data = bt_lookup.get(sym, {})
        rr = s.get("rr", 0)
        change = s.get("change_pct", 0)
        conviction = compute_conviction(score, bt_data, rr, change)
        
        scored.append({
            "symbol": sym,
            "mt5": NIGHT_SYMBOLS[sym],
            "conviction": conviction,
            "score": score,
            "rr": rr,
            "rsi": s.get("rsi", 50),
            "entry": s.get("entry", 0),
            "sl": s.get("stop_loss", 0),
            "tp": s.get("tp1", 0),
        })
    
    scored.sort(key=lambda x: -x["conviction"])
    
    for s in scored[:10]:
        sym = s["symbol"]
        mt5_sym = s["mt5"]
        conviction = s["conviction"]
        
        if conviction < MIN_CONVICTION:
            continue
        
        # Check price
        price_data = get_mt5_price(mt5_sym)
        if price_data["bid"] <= 0:
            continue
        
        if price_data["spread_pct"] > MAX_SPREAD_PCT:
            continue
        
        # Fire limit order
        lots = 0.01
        success, result = fire_order(mt5_sym, "limit", lots, s["entry"], s["sl"], s["tp"])
        
        # Log
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": sym,
            "conviction": conviction,
            "order_type": "limit",
            "lots": lots,
            "price": s["entry"],
            "sl": s["sl"],
            "tp": s["tp"],
            "result": success,
            "reason": result
        }
        
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        if success:
            return True, f"Fired {sym} conviction={conviction}"
        
        return False, f"Failed {sym}: {result}"
    
    return False, "No setups met threshold"

def fire_order(mt5_symbol, order_type, lots, price, sl, tp):
    """Fire order."""
    try:
        cmd = [MT5_PYTHON, MT5_ORDER_MGR, f"--buy-{order_type}", mt5_symbol,
               "--price", str(price), "--lots", str(lots),
               "--sl", str(sl), "--tp", str(tp)]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and "SUCCESS" in result.stdout:
            return True, result.stdout.strip()
        return False, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def start():
    """Start night shift monitor."""
    if PID_FILE.exists():
        print("Night shift already running")
        return
    
    pid = os.getpid()
    PID_FILE.write_text(str(pid))
    
    print(f"Night shift monitor started (PID: {pid})")
    print(f"Hours: {NIGHT_START}:00 - {NIGHT_END}:00 EST")
    
    while True:
        try:
            if is_night_shift():
                success, msg = run_cycle()
                if success:
                    print(f"[{datetime.now()}] {msg}")
        except Exception as e:
            print(f"ERROR: {e}")
        
        time.sleep(300)  # 5 minutes

def stop():
    """Stop night shift monitor."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text())
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Stopped night shift monitor (PID: {pid})")
        except:
            print(f"Process {pid} not found")
        PID_FILE.unlink()
    else:
        print("Night shift monitor not running")

def status():
    """Check status."""
    if PID_FILE.exists():
        pid = PID_FILE.read_text()
        print(f"Night shift monitor running (PID: {pid})")
    else:
        print("Night shift monitor not running")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 night_shift_monitor.py --start|--stop|--status")
    elif sys.argv[1] == "--start":
        start()
    elif sys.argv[1] == "--stop":
        stop()
    elif sys.argv[1] == "--status":
        status()
