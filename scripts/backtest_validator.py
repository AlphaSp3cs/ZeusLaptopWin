#!/usr/bin/env python3
"""BACKTEST VALIDATOR — tests ONLY signals from scan_signals.db against REAL historical bars.db."""
import sqlite3, pathlib
from datetime import datetime, timezone
from collections import defaultdict

SIGNALS_DB = pathlib.Path(r"C:\Hermes\workflow\data\backtest_signals.db")
BARS_DB = pathlib.Path(r"C:\Hermes\workflow\data\bars.db")

def load_bars(symbol, tf='1d'):
    """Load historical bars from bars.db."""
    con = sqlite3.connect(str(BARS_DB))
    cur = con.cursor()
    # Map symbol format for bars.db
    sym_db = symbol.replace("-USD", "").replace("=X", "").replace("=F", "")
    cur.execute("""
        SELECT ts, open, high, low, close, volume 
        FROM bars 
        WHERE symbol=? AND tf=? 
        ORDER BY ts
    """, (sym_db, tf))
    rows = cur.fetchall()
    con.close()
    
    if not rows:
        return None
    
    return {
        'ts': [r[0] for r in rows],
        'open': [r[1] for r in rows],
        'high': [r[2] for r in rows],
        'low': [r[3] for r in rows],
        'close': [r[4] for r in rows],
        'volume': [r[5] for r in rows],
    }

def backtest_signal(signal_id, symbol, direction, entry_price, stop_price, target_1, target_2, max_hold=20):
    """Backtest a single signal against historical data."""
    bars = load_bars(symbol)
    if not bars:
        return None
    
    # Find bars after entry price was reached
    entry_idx = None
    for i, c in enumerate(bars['close']):
        if direction == "LONG" and c >= entry_price * 0.99:  # Within 1% of entry
            entry_idx = i
            break
        elif direction == "SHORT" and c <= entry_price * 1.01:
            entry_idx = i
            break
    
    if entry_idx is None or entry_idx >= len(bars['close']) - 1:
        return None
    
    # Simulate trade
    entry = bars['close'][entry_idx]
    exit_price = None
    exit_reason = None
    bars_held = 0
    max_gain = 0
    max_dd = 0
    
    for i in range(entry_idx + 1, min(entry_idx + max_hold + 1, len(bars['close']))):
        bars_held = i - entry_idx
        current = bars['close'][i]
        
        if direction == "LONG":
            pnl_pct = (current - entry) / entry * 100
            max_gain = max(max_gain, pnl_pct)
            max_dd = min(max_dd, pnl_pct)
            
            if current <= stop_price:
                exit_price = stop_price
                exit_reason = "stop"
                break
            elif current >= target_1:
                exit_price = target_1
                exit_reason = "target"
                break
        else:
            pnl_pct = (entry - current) / entry * 100
            max_gain = max(max_gain, pnl_pct)
            max_dd = min(max_dd, pnl_pct)
            
            if current >= stop_price:
                exit_price = stop_price
                exit_reason = "stop"
                break
            elif current <= target_1:
                exit_price = target_1
                exit_reason = "target"
                break
    
    if exit_price is None:
        # Timeout
        exit_price = bars['close'][min(entry_idx + max_hold, len(bars['close']) - 1)]
        exit_reason = "timeout"
    
    pnl = (exit_price - entry) / entry * 100 if direction == "LONG" else (entry - exit_price) / entry * 100
    
    return {
        'signal_id': signal_id,
        'symbol': symbol,
        'direction': direction,
        'entry': entry,
        'exit': exit_price,
        'stop': stop_price,
        'target': target_1,
        'pnl_pct': round(pnl, 2),
        'max_gain': round(max_gain, 2),
        'max_drawdown': round(max_dd, 2),
        'bars_held': bars_held,
        'exit_reason': exit_reason,
        'result': 'WIN' if pnl > 0 else 'LOSS' if pnl < 0 else 'BREAKEVEN'
    }

def run_all_validations():
    """Run backtest validation on all pending signals."""
    con = sqlite3.connect(str(SIGNALS_DB))
    cur = con.cursor()
    
    # Get pending signals
    cur.execute("""
        SELECT id, symbol, direction, entry_price, stop_price, target_1, target_2, score, conviction
        FROM scan_signals
        WHERE id NOT IN (SELECT signal_id FROM backtest_validation WHERE result != 'PENDING')
        ORDER BY score DESC, conviction ASC
        LIMIT 100
    """)
    
    pending = cur.fetchall()
    print(f"Pending signals to validate: {len(pending)}")
    
    results = []
    for sig in pending:
        sid, sym, direction, entry, stop, tp1, tp2, score, conviction = sig
        result = backtest_signal(sid, sym, direction, entry, stop, tp1, tp2)
        if result:
            results.append(result)
            
            # Store result
            cur.execute("""
                INSERT INTO backtest_validation 
                (signal_id, validation_date, result, pnl_pct, max_drawdown, max_gain, 
                 holding_days, exit_price, exit_reason, bars_held)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sid, datetime.now(timezone.utc).isoformat(),
                result['result'], result['pnl_pct'], result['max_drawdown'],
                result['max_gain'], result['bars_held'], result['exit'],
                result['exit_reason'], result['bars_held']
            ))
    
    con.commit()
    con.close()
    return results

def print_validation_report(results):
    """Print validation report."""
    if not results:
        print("No validation results.")
        return
    
    print("\n" + "=" * 80)
    print("BACKTEST VALIDATION REPORT")
    print("=" * 80)
    
    wins = sum(1 for r in results if r['result'] == 'WIN')
    losses = sum(1 for r in results if r['result'] == 'LOSS')
    be = sum(1 for r in results if r['result'] == 'BREAKEVEN')
    
    print(f"\nTotal: {len(results)} | Wins: {wins} | Losses: {losses} | B/E: {be}")
    print(f"Win Rate: {wins/(len(results))*100:.1f}%")
    
    # By symbol
    by_symbol = defaultdict(list)
    for r in results:
        by_symbol[r['symbol']].append(r)
    
    print(f"\n{'Symbol':<12} {'Dir':<6} {'#':>4} {'WR':>6} {'AvgPnL':>8} {'AvgHold':>8} {'Stop%':>7} {'Target%':>8}")
    for sym, rs in sorted(by_symbol.items(), key=lambda x: -len(x[1])):
        wr = sum(1 for r in rs if r['result'] == 'WIN') / len(rs) * 100
        avg_pnl = sum(r['pnl_pct'] for r in rs) / len(rs)
        avg_hold = sum(r['bars_held'] for r in rs) / len(rs)
        stops = sum(1 for r in rs if r['exit_reason'] == 'stop') / len(rs) * 100
        targets = sum(1 for r in rs if r['exit_reason'] == 'target') / len(rs) * 100
        print(f"{sym:<12} {rs[0]['direction']:<6} {len(rs):>4} {wr:>5.0f}% {avg_pnl:>+7.2f}% {avg_hold:>7.1f}d {stops:>6.0f}% {targets:>7.0f}%")
    
    # By exit reason
    print(f"\n### EXIT ANALYSIS")
    stop_exits = sum(1 for r in results if r['exit_reason'] == 'stop')
    target_exits = sum(1 for r in results if r['exit_reason'] == 'target')
    timeout_exits = sum(1 for r in results if r['exit_reason'] == 'timeout')
    print(f"Stopped out: {stop_exits} ({stop_exits/len(results)*100:.0f}%)")
    print(f"Target hit: {target_exits} ({target_exits/len(results)*100:.0f}%)")
    print(f"Timed out: {timeout_exits} ({timeout_exits/len(results)*100:.0f}%)")
    
    # Best/worst
    results.sort(key=lambda x: x['pnl_pct'], reverse=True)
    print(f"\n### BEST TRADES")
    for r in results[:5]:
        print(f"  {r['symbol']:<12} {r['direction']:<6} PnL={r['pnl_pct']:>+7.2f}% Held={r['bars_held']}d {r['exit_reason']}")
    
    print(f"\n### WORST TRADES")
    for r in results[-5:]:
        print(f"  {r['symbol']:<12} {r['direction']:<6} PnL={r['pnl_pct']:>+7.2f}% Held={r['bars_held']}d {r['exit_reason']}")

if __name__ == "__main__":
    results = run_all_validations()
    print_validation_report(results)
