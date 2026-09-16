#!/usr/bin/env python3
"""CRYPTO BACKTEST FEEDBACK DB — persistent memory for backtest results."""
import json, pathlib, sqlite3
from datetime import datetime, timezone

DB = pathlib.Path(r"C:\Hermes\workflow\data\crypto_feedback.db")

def init_db():
    """Initialize feedback database."""
    con = sqlite3.connect(str(DB))
    con.executescript("""
        CREATE TABLE IF NOT EXISTS backtest_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            strategy TEXT,
            entry_price REAL,
            stop_price REAL,
            target_price REAL,
            hold_days INTEGER DEFAULT 0,
            result TEXT CHECK(result IN ('WIN', 'LOSS', 'BREAKEVEN', 'PENDING')),
            pnl_pct REAL,
            evidence TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS skip_concentrate (
            symbol TEXT PRIMARY KEY,
            action TEXT CHECK(action IN ('SKIP', 'CONCENTRATE')),
            reason TEXT,
            win_rate REAL,
            avg_return REAL,
            n_trades INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now'))
        );
        
        CREATE INDEX IF NOT EXISTS idx_symbol ON backtest_feedback(symbol);
        CREATE INDEX IF NOT EXISTS idx_result ON backtest_feedback(result);
    """)
    con.commit()
    return con

def update_skip_from_feedback(con, symbol):
    """Update skip/concentrate based on backtest history."""
    cur = con.cursor()
    cur.execute("""
        SELECT result, COUNT(*) as cnt,
               AVG(pnl_pct) as avg_pnl
        FROM backtest_feedback
        WHERE symbol = ? AND result IN ('WIN', 'LOSS', 'BREAKEVEN')
        GROUP BY result
    """, (symbol,))
    
    rows = cur.fetchall()
    if not rows:
        return
    
    total = sum(r[1] for r in rows)
    wins = sum(r[1] for r in rows if r[0] == 'WIN')
    avg_pnl = sum(r[2] * r[1] for r in rows) / total if total > 0 else 0
    win_rate = wins / total if total > 0 else 0
    
    if total >= 10:  # Minimum sample size
        if win_rate >= 0.55 and avg_pnl > 0:
            action = 'CONCENTRATE'
            reason = f"WR {win_rate:.0%}, avg {avg_pnl:+.2f}% over {total} trades"
        elif win_rate < 0.45 or avg_pnl < 0:
            action = 'SKIP'
            reason = f"WR {win_rate:.0%}, avg {avg_pnl:+.2f}% over {total} trades"
        else:
            return  # No strong signal
        
        con.execute("""
            INSERT OR REPLACE INTO skip_concentrate 
            (symbol, action, reason, win_rate, avg_return, n_trades, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (symbol, action, reason, win_rate, avg_pnl, total))
        con.commit()

def get_feedback_summary(con, symbol):
    """Get feedback summary for a symbol."""
    cur = con.cursor()
    cur.execute("""
        SELECT result, COUNT(*) as cnt, AVG(pnl_pct) as avg_pnl
        FROM backtest_feedback
        WHERE symbol = ?
        GROUP BY result
    """, (symbol,))
    
    return {row[0]: {"count": row[1], "avg_pnl": round(row[2] or 0, 2)} for row in cur.fetchall()}

if __name__ == "__main__":
    con = init_db()
    print(f"✓ Initialized crypto feedback DB: {DB}")
    con.close()
