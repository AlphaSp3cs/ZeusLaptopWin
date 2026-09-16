#!/usr/bin/env python3
"""COMPREHENSIVE SCANNER v2 — with trader-ready output, staleness alert, position log, feedback DB."""
import json, pathlib, sqlite3, time, statistics
from datetime import datetime, timezone
from collections import defaultdict

HOME = pathlib.Path.home()
DB_DIR = pathlib.Path(r"C:\Hermes\workflow\data")
DB_DIR.mkdir(parents=True, exist_ok=True)
UNIVERSE_FILE = DB_DIR / "universe_comprehensive.json"
NEWS_FILE = DB_DIR / "news_headlines.json"
POSITIONS_FILE = DB_DIR / "positions_log.json"
FEEDBACK_DB = DB_DIR / "crypto_feedback.db"

# === TRADER-READY OUTPUT FORMAT ===
def calc_rr(entry, stop, tp):
    risk = abs(entry - stop)
    reward = abs(tp - entry)
    return round(reward / risk, 2) if risk > 0 else 0

def generate_trade_levels(side, entry, atr, rr_target=2.0):
    """Generate entry/stop/target with specified R:R."""
    if side == "LONG":
        stop = round(entry - (atr * 1.5), 4)
        tp = round(entry + (atr * 1.5 * rr_target), 4)
    else:
        stop = round(entry + (atr * 1.5), 4)
        tp = round(entry - (atr * 1.5 * rr_target), 4)
    rr = calc_rr(entry, stop, tp)
    return {"entry": entry, "stop": stop, "tp": tp, "rr": rr}

# === STALENESS ALERT ===
def check_news_staleness():
    """Check if OuroTaurus/news tape is stale (>12h)."""
    if not NEWS_FILE.exists():
        return "WARNING: News file missing — no tape signal available."
    
    try:
        news = json.loads(NEWS_FILE.read_text(encoding="utf-8"))
        ts_str = news.get("scan_timestamp", "")
        if ts_str:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age_h > 12:
                return f"⚠️  WARNING: News tape STALE — last updated {age_h:.1f}h ago. Tape signal degraded."
            else:
                return f"✓ News tape fresh — last updated {age_h:.1f}h ago."
    except Exception:
        pass
    return "⚠️  WARNING: News tape timestamp unreadable — assume stale."

# === CRYPTO BACKTEST FEEDBACK DB ===
def init_feedback_db():
    """Initialize crypto backtest feedback DB (mirrors forex pattern)."""
    con = sqlite3.connect(str(FEEDBACK_DB))
    con.execute("""
        CREATE TABLE IF NOT EXISTS backtest_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            strategy TEXT,
            entry_price REAL,
            stop_price REAL,
            target_price REAL,
            hold_days INTEGER,
            result TEXT CHECK(result IN ('WIN', 'LOSS', 'BREAKEVEN', 'PENDING')),
            pnl_pct REAL,
            evidence TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS skip_concentrate (
            symbol TEXT PRIMARY KEY,
            action TEXT CHECK(action IN ('SKIP', 'CONCENTRATE')),
            reason TEXT,
            win_rate REAL,
            avg_return REAL,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    con.commit()
    return con

def log_backtest_result(con, symbol, direction, strategy, entry, stop, target, result, pnl_pct, notes=""):
    """Log a backtest result to the feedback DB."""
    hold_days = 0  # Will be updated when position is closed
    con.execute("""
        INSERT INTO backtest_feedback (symbol, direction, strategy, entry_price, stop_price, target_price, hold_days, result, pnl_pct, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (symbol, direction, strategy, entry, stop, target, hold_days, result, pnl_pct, notes))
    con.commit()

def get_skip_concentrate(con):
    """Get skip/concentrate lists from feedback."""
    cur = con.cursor()
    cur.execute("SELECT symbol, action, reason FROM skip_concentrate")
    return {row[0]: {"action": row[1], "reason": row[2]} for row in cur.fetchall()}

def update_skip_concentrate(con, symbol, action, reason="", win_rate=None, avg_return=None):
    """Update skip/concentrate recommendation."""
    con.execute("""
        INSERT OR REPLACE INTO skip_concentrate (symbol, action, reason, win_rate, avg_return, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
    """, (symbol, action, reason, win_rate, avg_return))
    con.commit()

# === POSITION / RISK TRACKING ===
def load_positions():
    """Load active positions."""
    if POSITIONS_FILE.exists():
        return json.loads(POSITIONS_FILE.read_text(encoding="utf-8"))
    return {"positions": [], "total_exposure_pct": 0.0, "updated_at": None}

def save_positions(positions_data):
    """Save positions log."""
    POSITIONS_FILE.write_text(json.dumps(positions_data, indent=2, default=str), encoding="utf-8")

def add_position(symbol, side, entry, stop, target, size_pct, rr, conviction):
    """Add a position to the log."""
    positions = load_positions()
    positions["positions"].append({
        "symbol": symbol,
        "side": side,
        "entry": entry,
        "stop": stop,
        "target": target,
        "size_pct": size_pct,
        "rr": rr,
        "conviction": conviction,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "status": "OPEN",
    })
    # Recalculate total exposure
    total = sum(p["size_pct"] for p in positions["positions"] if p["status"] == "OPEN")
    positions["total_exposure_pct"] = round(total, 2)
    positions["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_positions(positions)
    return positions

def get_portfolio_summary():
    """Get portfolio risk summary."""
    positions = load_positions()
    open_pos = [p for p in positions["positions"] if p["status"] == "OPEN"]
    long_exposure = sum(p["size_pct"] for p in open_pos if p["side"] == "LONG")
    short_exposure = sum(p["size_pct"] for p in open_pos if p["side"] == "SHORT")
    net_exposure = long_exposure - short_exposure
    return {
        "total_positions": len(open_pos),
        "long_exposure_pct": round(long_exposure, 2),
        "short_exposure_pct": round(short_exposure, 2),
        "net_exposure_pct": round(net_exposure, 2),
        "gross_exposure_pct": round(long_exposure + short_exposure, 2),
    }

# === CRASH EXCLUSION SET ===
CRASH_EXCLUDED = {
    "LUNC", "TERRA", "USTC", "IRON", "TITAN", "SQUID", "SAFE", "MOON",
    "ASTRO", "MARS", "ELON", "DOGE2", "SHIB2", "BASED", "MEME",
    "MOON", "SAFE", "ASTRO", "MARS", "ELON", "DOGE2", "SHIB2",
}

def is_crash_excluded(symbol):
    """Check if symbol is crash-excluded."""
    sym = symbol.replace("-USD", "").replace("-USDT", "").upper()
    return sym in CRASH_EXCLUDED

# === MAIN SCAN FUNCTION ===
def run_comprehensive_scan():
    """Run comprehensive all-sector scan with trader-ready output."""
    print("=" * 80)
    print("COMPREHENSIVE ALL-SECTOR SCAN v2")
    print("=" * 80)
    
    # Staleness alert
    staleness = check_news_staleness()
    print(f"\n{staleness}")
    
    # Portfolio summary
    portfolio = get_portfolio_summary()
    print(f"\n📊 PORTFOLIO: {portfolio['total_positions']} open | Long: {portfolio['long_exposure_pct']}% | Short: {portfolio['short_exposure_pct']}% | Net: {portfolio['net_exposure_pct']}%")
    
    # Initialize feedback DB
    fb_con = init_feedback_db()
    skip_conc = get_skip_concentrate(fb_con)
    
    # Load universe and setups
    if not UNIVERSE_FILE.exists():
        print("ERROR: Universe file missing. Run download_comprehensive_universe.py first.")
        return
    
    blob = json.loads(UNIVERSE_FILE.read_text(encoding="utf-8"))
    assets = blob["assets"]
    print(f"\nLoaded {len(assets)} assets")
    
    # Load existing setups
    setups_file = DB_DIR / "comprehensive_setups.json"
    if setups_file.exists():
        setups_blob = json.loads(setups_file.read_text(encoding="utf-8"))
        setups_by_sector = setups_blob.get("sectors", {})
    else:
        setups_by_sector = {}
    
    # Collect all setups
    all_setups = []
    for cat, items in setups_by_sector.items():
        for s in items:
            s["category"] = cat
            all_setups.append(s)
    
    # Filter out crash-excluded
    tradable = [s for s in all_setups if not is_crash_excluded(s["symbol"])]
    excluded = [s for s in all_setups if is_crash_excluded(s["symbol"])]
    
    # Sort by score then change
    tradable.sort(key=lambda x: (-x.get("score", 0), -x.get("change", 0)))
    
    # Group by sector
    by_sector = defaultdict(list)
    for s in tradable:
        by_sector[s["category"]].append(s)
    
    # Print tradable setups with trade levels
    print(f"\n{'=' * 80}")
    print("TRADER-READY SETUPS")
    print(f"{'=' * 80}")
    
    for cat in ["US_EQUITY", "ETF", "CRYPTO", "METALS", "ENERGY", "AGRICULTURE", "FX", "INDICES", "UNKNOWN"]:
        items = by_sector.get(cat, [])
        if not items:
            continue
        print(f"\n### {cat} ({len(items)} setups)")
        for s in items[:15]:
            sym = s["symbol"]
            price = s.get("price", 0)
            change = s.get("change", 0)
            rsi = s.get("rsi", 0)
            score = s.get("score", 0)
            
            # Determine direction from change
            side = "LONG" if change > 0 else "SHORT"
            
            # Generate trade levels
            atr = price * 0.03  # Default 3% ATR estimate if not available
            levels = generate_trade_levels(side, price, atr, rr_target=2.0)
            
            # Skip/concentrate marker
            sc = skip_conc.get(sym, {})
            sc_marker = ""
            if sc.get("action") == "SKIP":
                sc_marker = " [SKIP - low WR]"
            elif sc.get("action") == "CONCENTRATE":
                sc_marker = " [CONCENTRATE - high WR]"
            
            print(f"  {sym:<12} ${price:>10,.2f}  {change:>+6.2f}%  RSI={rsi:>4.0f}  Score={score}  RR={levels['rr']}")
            print(f"    {side}: Entry {levels['entry']} | SL {levels['stop']} ({abs(levels['stop']/levels['entry']-1)*100:.1f}%) | TP {levels['tp']} ({abs(levels['tp']/levels['entry']-1)*100:.1f}%){sc_marker}")
    
    # Crash-excluded section
    if excluded:
        print(f"\n{'=' * 80}")
        print(f"⚠️  EXCLUDED — DO NOT TRADE ({len(excluded)} crash-prone assets)")
        print(f"{'=' * 80}")
        for s in excluded[:10]:
            print(f"  {s['symbol']:<12} ${s.get('price', 0):>10,.2f}  {s.get('change', 0):>+6.2f}%  [CRASH EXCLUDED]")
    
    # Skip/concentrate summary
    if skip_conc:
        print(f"\n{'=' * 80}")
        print("SKIP/CONCENTRATE RECOMMENDATIONS (from feedback DB)")
        print(f"{'=' * 80}")
        for sym, info in list(skip_conc.items())[:10]:
            print(f"  {sym:<12} {info['action']:<12} {info.get('reason', '')}")
    
    fb_con.close()
    print(f"\n✓ Feedback DB: {FEEDBACK_DB}")
    print(f"✓ Positions log: {POSITIONS_FILE}")
    print(f"\nScan complete: {len(tradable)} tradable, {len(excluded)} excluded")

if __name__ == "__main__":
    run_comprehensive_scan()
