#!/usr/bin/env python3
"""Save backtest-ready signals from scan results — only what's needed for historical validation."""
import json, pathlib, sqlite3
from datetime import datetime, timezone
from collections import defaultdict

DB_DIR = pathlib.Path(r"C:\Hermes\workflow\data")
SIGNALS_DB = DB_DIR / "backtest_signals.db"
SETUPS_FILE = DB_DIR / "comprehensive_setups.json"
BACKTEST_FILE = DB_DIR / "backtest_results.jsonl"

def init_signals_db():
    """Initialize persistent signals database."""
    con = sqlite3.connect(str(SIGNALS_DB))
    con.executescript("""
        CREATE TABLE IF NOT EXISTS scan_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            category TEXT,
            signal_type TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stop_price REAL NOT NULL,
            target_1 REAL NOT NULL,
            target_2 REAL,
            rr_ratio REAL NOT NULL,
            score INTEGER,
            rsi REAL,
            vol_ratio REAL,
            price_vs_ema20 TEXT,  -- 'above' / 'below'
            price_vs_ema50 TEXT,  -- 'above' / 'below'
            price_vs_ema200 TEXT, -- 'above' / 'below' / 'na'
            three_day_uptrend INTEGER, -- 0/1
            atr_14 REAL,
            conviction TEXT,       -- 'HIGH' / 'SOLID' / 'MARGINAL'
            scan_source TEXT,      -- 'nightshift' / 'premarket' / 'allsector'
            UNIQUE(scan_timestamp, symbol, direction)
        );
        
        CREATE TABLE IF NOT EXISTS backtest_validation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER NOT NULL,
            validation_date TEXT NOT NULL,
            result TEXT CHECK(result IN ('WIN', 'LOSS', 'BREAKEVEN', 'PENDING')),
            pnl_pct REAL,
            max_drawdown REAL,
            max_gain REAL,
            holding_days INTEGER,
            exit_price REAL,
            exit_reason TEXT,  -- 'target' / 'stop' / 'timeout' / 'manual'
            bars_held INTEGER,
            FOREIGN KEY (signal_id) REFERENCES scan_signals(id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_signal_symbol ON scan_signals(symbol);
        CREATE INDEX IF NOT EXISTS idx_signal_timestamp ON scan_signals(scan_timestamp);
        CREATE INDEX IF NOT EXISTS idx_signal_direction ON scan_signals(direction);
        CREATE INDEX IF NOT EXISTS idx_validation_result ON backtest_validation(result);
    """)
    con.commit()
    return con

def save_backtest_signals(scan_timestamp, scan_source="nightshift"):
    """Save scan results in backtest-ready format."""
    if not SETUPS_FILE.exists():
        print("No scan results found.")
        return 0
    
    setups = json.loads(SETUPS_FILE.read_text(encoding="utf-8"))
    con = init_signals_db()
    cur = con.cursor()
    
    saved = 0
    
    for cat, items in setups.get("sectors", {}).items():
        for s in items:
            sym = s["symbol"]
            price = s.get("price", 0)
            if price <= 0:
                continue
            
            # Determine direction — use change_pct from universe, fall back to score/RSI
            change = s.get("change_pct", s.get("change", 0))
            # If change is 0 or missing, infer from technical setup (score >= 4 with RSI < 60 = bullish)
            if change > 0:
                direction = "LONG"
            elif change < 0:
                direction = "SHORT"
            else:
                # change == 0: use technical bias
                score = s.get("score", 0)
                rsi = s.get("rsi", 50)
                if score >= 4 and rsi < 65:
                    direction = "LONG"
                elif score >= 4 and rsi >= 65:
                    direction = "SHORT"
                else:
                    direction = "LONG"  # Default to LONG for high-score setups
            
            # Signal type based on scan characteristics
            score = s.get("score", 0)
            rsi = s.get("rsi", 50)
            vol_ratio = s.get("vol_ratio", 1.0)
            
            if score >= 5 and rsi < 60 and vol_ratio > 1.5:
                signal_type = "STRONG_BULLISH"
            elif score >= 4 and rsi < 65:
                signal_type = "BULLISH"
            elif score >= 3:
                signal_type = "MARGINAL_BULLISH"
            else:
                signal_type = "WEAK"
            
            # Calculate entry/stop/target based on signal type
            atr = price * 0.03  # Estimate ATR as 3% of price if not available
            
            if direction == "LONG":
                stop = round(price - (atr * 1.5), 4)
                target_1 = round(price + (atr * 1.5 * 2.0), 4)
                target_2 = round(price + (atr * 1.5 * 3.0), 4)
            else:
                stop = round(price + (atr * 1.5), 4)
                target_1 = round(price - (atr * 1.5 * 2.0), 4)
                target_2 = round(price - (atr * 1.5 * 3.0), 4)
            
            rr = round(abs(target_1 - price) / abs(price - stop), 2) if (price - stop) != 0 else 0
            
            # Conviction based on score
            if score >= 5:
                conviction = "HIGH"
            elif score >= 4:
                conviction = "SOLID"
            else:
                conviction = "MARGINAL"
            
            # Price vs EMAs (estimated from RSI)
            price_vs_ema20 = "above" if rsi > 50 else "below"
            price_vs_ema50 = "above" if rsi > 55 else "below"
            price_vs_ema200 = "above" if rsi > 60 else "below" if rsi < 40 else "na"
            
            # 3-day uptrend (estimated from change)
            three_day = 1 if change > 0 else 0
            
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO scan_signals 
                    (scan_timestamp, symbol, direction, category, signal_type,
                     entry_price, stop_price, target_1, target_2, rr_ratio,
                     score, rsi, vol_ratio, price_vs_ema20, price_vs_ema50,
                     price_vs_ema200, three_day_uptrend, atr_14, conviction, scan_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scan_timestamp, sym, direction, cat, signal_type,
                    price, stop, target_1, target_2, rr,
                    score, rsi, vol_ratio, price_vs_ema20, price_vs_ema50,
                    price_vs_ema200, three_day, atr, conviction, scan_source
                ))
                saved += 1
            except sqlite3.IntegrityError:
                pass  # Duplicate signal, skip
    
    con.commit()
    con.close()
    return saved

def get_signals_for_backtest(symbol=None, direction=None, conviction=None, limit=50):
    """Query signals that are ready for backtest validation."""
    con = sqlite3.connect(str(SIGNALS_DB))
    cur = con.cursor()
    
    query = """
        SELECT s.id, s.scan_timestamp, s.symbol, s.direction, s.signal_type,
               s.entry_price, s.stop_price, s.target_1, s.target_2, s.rr_ratio,
               s.score, s.rsi, s.conviction,
               v.result, v.pnl_pct, v.holding_days, v.exit_reason
        FROM scan_signals s
        LEFT JOIN backtest_validation v ON s.id = v.signal_id
        WHERE v.id IS NULL OR v.result = 'PENDING'
    """
    params = []
    if symbol:
        query += " AND s.symbol = ?"
        params.append(symbol)
    if direction:
        query += " AND s.direction = ?"
        params.append(direction)
    if conviction:
        query += " AND s.conviction = ?"
        params.append(conviction)
    
    query += " ORDER BY s.scan_timestamp DESC LIMIT ?"
    params.append(limit)
    
    cur.execute(query, params)
    return cur.fetchall()

def get_validation_summary():
    """Get summary of backtest validation results."""
    con = sqlite3.connect(str(SIGNALS_DB))
    cur = con.cursor()
    
    cur.execute("""
        SELECT s.symbol, s.conviction, s.direction,
               COUNT(*) as total,
               SUM(CASE WHEN v.result = 'WIN' THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN v.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
               AVG(v.pnl_pct) as avg_pnl,
               AVG(v.holding_days) as avg_hold
        FROM scan_signals s
        JOIN backtest_validation v ON s.id = v.signal_id
        WHERE v.result IN ('WIN', 'LOSS', 'BREAKEVEN')
        GROUP BY s.symbol, s.conviction, s.direction
        ORDER BY avg_pnl DESC
    """)
    
    return cur.fetchall()

if __name__ == "__main__":
    scan_ts = datetime.now(timezone.utc).isoformat()
    
    # Save current scan
    saved = save_backtest_signals(scan_ts, "nightshift")
    print(f"✓ Saved {saved} backtest-ready signals from scan")
    
    # Print pending validations
    pending = get_signals_for_backtest(limit=20)
    print(f"\nPending backtest validations: {len(pending)}")
    for p in pending[:10]:
        print(f"  {p[2]:<12} {p[3]:<6} {p[4]:<20} Entry={p[5]:>10.2f} SL={p[6]:>10.2f} TP={p[7]:>10.2f} RR={p[8]} Score={p[10]} Conv={p[12]}")
    
    # Print validation summary if available
    summary = get_validation_summary()
    if summary:
        print(f"\n### VALIDATION SUMMARY")
        print(f"{'Symbol':<12} {'Conv':<8} {'Dir':<6} {'Total':>6} {'Wins':>5} {'Loss':>5} {'AvgPnL':>8} {'AvgHold':>7}")
        for row in summary[:20]:
            win_rate = row[4] / row[3] * 100 if row[3] > 0 else 0
            print(f"{row[0]:<12} {row[1]:<8} {row[2]:<6} {row[3]:>6} {row[4]:>5} {row[5]:>5} {row[7]:>+7.2f}% {row[8]:>6.1f}d")
