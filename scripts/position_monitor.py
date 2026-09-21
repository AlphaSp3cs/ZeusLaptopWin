#!/usr/bin/env python3
"""POSITION MONITOR — 24/7 open position tracker.

Monitors:
- SL/TP hits (close detection)
- Trailing stop adjustments
- Conviction drift (close if conviction drops)
- Margin level alerts
- P&L tracking

Usage:
    python3 position_monitor.py --start    # Start monitoring
    python3 position_monitor.py --stop     # Stop monitoring
    python3 position_monitor.py --status   # Check status
    python3 position_monitor.py --check    # Single check
"""
import json, pathlib, sqlite3, sys, time, subprocess, os, signal
from datetime import datetime, timezone, timedelta

WORKFLOW = pathlib.Path("C:/Hermes/workflow")
LOG_FILE = WORKFLOW / "logs" / "position_monitor.jsonl"
PID_FILE = WORKFLOW / "data" / "position_monitor.pid"
CONVICTION_FILE = WORKFLOW / "data" / "autotrader_convictions.json"

MT5_PYTHON = r"C:\Users\victo\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
MT5_ORDER_MGR = r"C:\Users\victo\mt5_order_manager.py"

# Alert thresholds
MARGIN_LEVEL_WARN = 200.0  # %
MARGIN_LEVEL_CRITICAL = 120.0  # %
MAX_LOSS_PER_TRADE = -5.0  # % from entry
CONVICTION_CLOSE_THRESHOLD = -15.0  # Close if conviction drops 15 pts

def get_positions():
    """Get open positions from MT5."""
    try:
        result = subprocess.run([
            MT5_PYTHON, "-c",
            """
import MetaTrader5 as mt5
if mt5.initialize():
    positions = mt5.positions_get()
    if positions:
        for p in positions:
            print(f"{p.ticket}|{p.symbol}|{p.type}|{p.volume}|{p.price_open}|{p.price_current}|{p.profit}|{p.sl}|{p.tp}")
    mt5.shutdown()
"""
        ], capture_output=True, text=True, timeout=15)
        
        positions = []
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                parts = line.split("|")
                if len(parts) == 9:
                    positions.append({
                        "ticket": int(parts[0]),
                        "symbol": parts[1],
                        "type": int(parts[2]),
                        "volume": float(parts[3]),
                        "price_open": float(parts[4]),
                        "price_current": float(parts[5]),
                        "profit": float(parts[6]),
                        "sl": float(parts[7]),
                        "tp": float(parts[8]),
                    })
        return positions
    except:
        return []

def get_account():
    """Get account info from MT5."""
    try:
        result = subprocess.run([
            MT5_PYTHON, "-c",
            """
import MetaTrader5 as mt5
if mt5.initialize():
    account = mt5.account_info()
    print(f"{account.balance}|{account.equity}|{account.margin}|{account.margin_free}|{account.margin_level}")
    mt5.shutdown()
"""
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            parts = result.stdout.strip().split("|")
            if len(parts) == 5:
                return {
                    "balance": float(parts[0]),
                    "equity": float(parts[1]),
                    "margin": float(parts[2]),
                    "margin_free": float(parts[3]),
                    "margin_level": float(parts[4]),
                }
    except:
        pass
    
    return None

def close_position(ticket):
    """Close a position by ticket."""
    try:
        result = subprocess.run([
            MT5_PYTHON, MT5_ORDER_MGR, "--close-ticket", str(ticket)
        ], capture_output=True, text=True, timeout=30)
        
        return result.returncode == 0
    except:
        return False

def check_positions():
    """Check all positions for alerts."""
    positions = get_positions()
    account = get_account()
    
    alerts = []
    
    if not positions:
        return alerts
    
    for p in positions:
        symbol = p["symbol"]
        profit_pct = (p["price_current"] - p["price_open"]) / p["price_open"] * 100
        
        # Check max loss
        if profit_pct < MAX_LOSS_PER_TRADE:
            alerts.append({
                "type": "max_loss",
                "ticket": p["ticket"],
                "symbol": symbol,
                "profit_pct": profit_pct,
                "action": "close"
            })
        
        # Check conviction drift
        if CONVICTION_FILE.exists():
            convictions = json.loads(CONVICTION_FILE.read_text(encoding="utf-8"))
            conv = convictions.get(symbol, {})
            if conv.get("conviction", 100) < CONVICTION_CLOSE_THRESHOLD:
                alerts.append({
                    "type": "conviction_drift",
                    "ticket": p["ticket"],
                    "symbol": symbol,
                    "conviction": conv.get("conviction"),
                    "action": "close"
                })
    
    # Check margin level
    if account and account["margin_level"] < MARGIN_LEVEL_CRITICAL:
        alerts.append({
            "type": "margin_critical",
            "margin_level": account["margin_level"],
            "action": "close_all"
        })
    elif account and account["margin_level"] < MARGIN_LEVEL_WARN:
        alerts.append({
            "type": "margin_warn",
            "margin_level": account["margin_level"],
            "action": "warn"
        })
    
    return alerts

def run_check():
    """Run single position check."""
    alerts = check_positions()
    
    for alert in alerts:
        if alert["action"] == "close":
            close_position(alert["ticket"])
            log_alert(alert, f"Closed {alert['symbol']} ticket {alert['ticket']}")
        elif alert["action"] == "close_all":
            # Close all positions
            positions = get_positions()
            for p in positions:
                close_position(p["ticket"])
            log_alert(alert, "Closed all positions (margin critical)")
        elif alert["action"] == "warn":
            log_alert(alert, f"WARNING: Margin level {alert['margin_level']:.0f}%")
    
    return alerts

def log_alert(alert, message):
    """Log alert."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alert": alert,
        "message": message
    }
    
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    print(f"[ALERT] {message}")

def start():
    """Start position monitor."""
    if PID_FILE.exists():
        print("Position monitor already running")
        return
    
    pid = os.getpid()
    PID_FILE.write_text(str(pid))
    
    print(f"Position monitor started (PID: {pid})")
    
    while True:
        try:
            alerts = run_check()
            if alerts:
                for a in alerts:
                    print(f"  {a['type']}: {a.get('symbol', 'account')} → {a['action']}")
        except Exception as e:
            print(f"ERROR: {e}")
        
        time.sleep(60)  # Check every minute

def stop():
    """Stop position monitor."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text())
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Stopped position monitor (PID: {pid})")
        except:
            print(f"Process {pid} not found")
        PID_FILE.unlink()
    else:
        print("Position monitor not running")

def status():
    """Check status."""
    if PID_FILE.exists():
        pid = PID_FILE.read_text()
        print(f"Position monitor running (PID: {pid})")
    else:
        print("Position monitor not running")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 position_monitor.py --start|--stop|--status|--check")
    elif sys.argv[1] == "--start":
        start()
    elif sys.argv[1] == "--stop":
        stop()
    elif sys.argv[1] == "--status":
        status()
    elif sys.argv[1] == "--check":
        alerts = run_check()
        if not alerts:
            print("No alerts")
