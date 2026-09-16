#!/usr/bin/env python3
"""POSITION TRACKER — unified portfolio/risk tracking across all asset classes."""
import json, pathlib
from datetime import datetime, timezone

DB_DIR = pathlib.Path(r"C:\Hermes\workflow\data")
POSITIONS_FILE = DB_DIR / "positions_log.json"

# FTMO-style risk limits
MAX_TOTAL_EXPOSURE_PCT = 25.0  # Max 25% of portfolio at risk
MAX_SINGLE_POSITION_PCT = 5.0  # Max 5% per position
MAX_LONG_EXPOSURE_PCT = 15.0   # Max 15% long
MAX_SHORT_EXPOSURE_PCT = 10.0  # Max 10% short
MIN_RR = 1.5                   # Minimum R:R to take a trade

def load_positions():
    """Load positions log."""
    if POSITIONS_FILE.exists():
        return json.loads(POSITIONS_FILE.read_text(encoding="utf-8"))
    return {"positions": [], "updated_at": None, "starting_equity": 100000.0}

def save_positions(data):
    """Save positions log."""
    POSITIONS_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

def open_position(symbol, side, entry, stop, target, size_pct, rr, conviction, notes=""):
    """Open a new position with risk checks."""
    data = load_positions()
    
    # Risk checks
    open_positions = [p for p in data["positions"] if p["status"] == "OPEN"]
    current_long = sum(p["size_pct"] for p in open_positions if p["side"] == "LONG")
    current_short = sum(p["size_pct"] for p in open_positions if p["side"] == "SHORT")
    current_total = current_long + current_short
    
    errors = []
    if size_pct > MAX_SINGLE_POSITION_PCT:
        errors.append(f"Position size {size_pct}% exceeds max {MAX_SINGLE_POSITION_PCT}%")
    if current_total + size_pct > MAX_TOTAL_EXPOSURE_PCT:
        errors.append(f"Total exposure {current_total + size_pct:.1f}% exceeds max {MAX_TOTAL_EXPOSURE_PCT}%")
    if side == "LONG" and current_long + size_pct > MAX_LONG_EXPOSURE_PCT:
        errors.append(f"Long exposure {current_long + size_pct:.1f}% exceeds max {MAX_LONG_EXPOSURE_PCT}%")
    if side == "SHORT" and current_short + size_pct > MAX_SHORT_EXPOSURE_PCT:
        errors.append(f"Short exposure {current_short + size_pct:.1f}% exceeds max {MAX_SHORT_EXPOSURE_PCT}%")
    if rr < MIN_RR:
        errors.append(f"R:R {rr} below minimum {MIN_RR}")
    
    if errors:
        return {"ok": False, "errors": errors}
    
    position = {
        "symbol": symbol,
        "side": side,
        "entry": entry,
        "stop": stop,
        "target": target,
        "size_pct": size_pct,
        "rr": rr,
        "conviction": conviction,
        "notes": notes,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "status": "OPEN",
        "pnl_pct": 0.0,
    }
    
    data["positions"].append(position)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_positions(data)
    
    return {"ok": True, "position": position}

def close_position(symbol, exit_price, notes=""):
    """Close a position and calculate P&L."""
    data = load_positions()
    
    for p in data["positions"]:
        if p["symbol"] == symbol and p["status"] == "OPEN":
            if p["side"] == "LONG":
                pnl = (exit_price - p["entry"]) / p["entry"] * 100
            else:
                pnl = (p["entry"] - exit_price) / p["entry"] * 100
            
            p["exit_price"] = exit_price
            p["pnl_pct"] = round(pnl, 2)
            p["status"] = "CLOSED"
            p["closed_at"] = datetime.now(timezone.utc).isoformat()
            p["notes"] = notes
            
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            save_positions(data)
            return {"ok": True, "pnl_pct": pnl}
    
    return {"ok": False, "error": f"No open position for {symbol}"}

def get_portfolio_summary():
    """Get comprehensive portfolio risk summary."""
    data = load_positions()
    open_pos = [p for p in data["positions"] if p["status"] == "OPEN"]
    closed_pos = [p for p in data["positions"] if p["status"] == "CLOSED"]
    
    long_exposure = sum(p["size_pct"] for p in open_pos if p["side"] == "LONG")
    short_exposure = sum(p["size_pct"] for p in open_pos if p["side"] == "SHORT")
    
    total_pnl = sum(p.get("pnl_pct", 0) * p["size_pct"] / 100 for p in closed_pos)
    winning_trades = sum(1 for p in closed_pos if p.get("pnl_pct", 0) > 0)
    losing_trades = sum(1 for p in closed_pos if p.get("pnl_pct", 0) <= 0)
    
    return {
        "total_positions": len(open_pos),
        "long_exposure_pct": round(long_exposure, 2),
        "short_exposure_pct": round(short_exposure, 2),
        "net_exposure_pct": round(long_exposure - short_exposure, 2),
        "gross_exposure_pct": round(long_exposure + short_exposure, 2),
        "closed_trades": len(closed_pos),
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": round(winning_trades / len(closed_pos) * 100, 1) if closed_pos else 0,
        "total_pnl_pct": round(total_pnl, 2),
        "can_open_long": long_exposure < MAX_LONG_EXPOSURE_PCT,
        "can_open_short": short_exposure < MAX_SHORT_EXPOSURE_PCT,
        "remaining_capacity": round(MAX_TOTAL_EXPOSURE_PCT - long_exposure - short_exposure, 2),
    }

def print_portfolio_report():
    """Print portfolio risk report."""
    summary = get_portfolio_summary()
    
    print("=" * 60)
    print("PORTFOLIO RISK REPORT")
    print("=" * 60)
    print(f"Open Positions: {summary['total_positions']}")
    print(f"Long Exposure:  {summary['long_exposure_pct']}% / {MAX_LONG_EXPOSURE_PCT}% max")
    print(f"Short Exposure: {summary['short_exposure_pct']}% / {MAX_SHORT_EXPOSURE_PCT}% max")
    print(f"Net Exposure:   {summary['net_exposure_pct']}%")
    print(f"Gross Exposure: {summary['gross_exposure_pct']}% / {MAX_TOTAL_EXPOSURE_PCT}% max")
    print(f"Remaining Cap:  {summary['remaining_capacity']}%")
    print(f"")
    print(f"Closed Trades:  {summary['closed_trades']}")
    print(f"Win Rate:       {summary['win_rate']}%")
    print(f"Total P&L:      {summary['total_pnl_pct']}%")
    print(f"")
    print(f"Can Open Long:  {'✓' if summary['can_open_long'] else '✗'}")
    print(f"Can Open Short: {'✓' if summary['can_open_short'] else '✗'}")
    print("=" * 60)

if __name__ == "__main__":
    print_portfolio_report()
