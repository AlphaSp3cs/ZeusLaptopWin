#!/usr/bin/env python3
"""MT5 DATA BRIDGE — Fetch historical data from MT5 into our bars.db.

Fetches tick and bar data from our MT5 terminal (Capital.com demo).
Integrates with existing C:\Hermes\workflow\data\bars.db.

HONEST DISCLAIMER:
- MT5 demo data may differ from live pricing
- Use this as supplementary source, not primary
- Always cross-validate with yfinance/binance/coingecko

Usage:
    python3 mt5_bridge.py --fetch-forex
    python3 mt5_bridge.py --fetch-metals
    python3 mt5_bridge.py --fetch-crypto
    python3 mt5_bridge.py --fetch-all
    python3 mt5_bridge.py --update-db
"""
from __future__ import annotations
import argparse, sqlite3, sys, time
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

DB = Path(r"C:\Hermes\workflow\data\bars.db")

# MT5 symbol mappings (MT5 name → our symbol name)
SYMBOL_MAP = {
    # Forex
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    # Metals
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "XPTUSD": "PL=F",
    "XPDUSD": "PA=F",
    # Crypto
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "SOLUSD": "SOL-USD",
    "BNBUSD": "BNB-USD",
    "XRPUSD": "XRP-USD",
    "ADAUSD": "ADA-USD",
    "DOGEUSD": "DOGE-USD",
    "AVAXUSD": "AVAX-USD",
    "LINKUSD": "LINK-USD",
    "DOTUSD": "DOT-USD",
    "LTCUSD": "LTC-USD",
    "ZECUSD": "ZEC-USD",
    "DASHUSD": "DASH-USD",
    "NEARUSD": "NEAR-USD",
    "XMRUSD": "XMR-USD",
    # Indices
    "US500": "^GSPC",
    "US100": "^IXIC",
    "US30": "^DJI",
    "VIX": "^VIX",
    # Energy
    "USOIL": "CL=F",
    "UKOIL": "BZ=F",
    "NATGAS": "NG=F",
}

# Reverse map (our symbol → MT5 name)
REVERSE_MAP = {v: k for k, v in SYMBOL_MAP.items()}

def init_mt5():
    """Initialize MT5 connection."""
    if not mt5.initialize():
        print("ERROR: MT5 not running or not connected")
        return False
    return True

def fetch_mt5_data(mt5_symbol, timeframe=mt5.TIMEFRAME_D1, count=1000):
    """Fetch historical rates from MT5."""
    rates = mt5.copy_rates_from_pos(mt5_symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.rename(columns={
        'time': 'timestamp',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'tick_volume': 'volume',
    })
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    
    return df

def update_bars_db(symbol, df, tf='1d'):
    """Insert bars into our bars.db."""
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    
    # Get or create symbol ID
    cur.execute("SELECT rowid FROM symbols WHERE symbol=?", (symbol,))
    row = cur.fetchone()
    if row:
        sym_id = row[0]
    else:
        # Determine category
        category = "unknown"
        if symbol.endswith("-USD"):
            category = "crypto"
        elif symbol.endswith("=F"):
            category = "metals" if any(m in symbol for m in ["GC", "SI", "PL", "PA", "HG"]) else "energy" if any(e in symbol for e in ["CL", "BZ", "NG"]) else "indices"
        elif symbol.endswith("=X"):
            category = "fx"
        elif symbol.startswith("^"):
            category = "indices"
        
        cur.execute("INSERT INTO symbols (symbol, sector) VALUES (?, ?)", (symbol, category))
        sym_id = cur.lastrowid
    
    # Insert bars
    inserted = 0
    for _, row in df.iterrows():
        ts = int(row['timestamp'].timestamp())
        try:
            cur.execute("""
                INSERT OR IGNORE INTO bars (symbol, tf, ts, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, tf, ts, row['open'], row['high'], row['low'], row['close'], row['volume']))
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            pass
    
    con.commit()
    con.close()
    return inserted

def main():
    print("=" * 80)
    print("MT5 DATA BRIDGE")
    print("=" * 80)
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-forex", action="store_true")
    parser.add_argument("--fetch-metals", action="store_true")
    parser.add_argument("--fetch-crypto", action="store_true")
    parser.add_argument("--fetch-indices", action="store_true")
    parser.add_argument("--fetch-energy", action="store_true")
    parser.add_argument("--fetch-all", action="store_true")
    parser.add_argument("--update-db", action="store_true")
    parser.add_argument("--count", type=int, default=1000)
    args = parser.parse_args()
    
    if not init_mt5():
        return
    
    account = mt5.account_info()
    print(f"Account: {account.server} | Balance: {account.balance}")
    
    # Symbols to fetch
    categories = []
    if args.fetch_forex or args.fetch_all:
        categories.append(("Forex", ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]))
    if args.fetch_metals or args.fetch_all:
        categories.append(("Metals", ["XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD"]))
    if args.fetch_crypto or args.fetch_all:
        categories.append(("Crypto", ["BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD", "XRPUSD", "ADAUSD", "DOGEUSD", "AVAXUSD", "LINKUSD", "DOTUSD", "LTCUSD", "ZECUSD", "DASHUSD", "NEARUSD", "XMRUSD"]))
    if args.fetch_indices or args.fetch_all:
        categories.append(("Indices", ["US500", "US100", "US30", "VIX"]))
    if args.fetch_energy or args.fetch_all:
        categories.append(("Energy", ["USOIL", "UKOIL", "NATGAS"]))
    
    if not categories:
        print("No categories selected. Use --fetch-all or specific categories.")
        mt5.shutdown()
        return
    
    total_fetched = 0
    total_inserted = 0
    
    for cat_name, symbols in categories:
        print(f"\n--- {cat_name} ---")
        for sym in symbols:
            # Check if symbol exists in MT5
            info = mt5.symbol_info(sym)
            if info is None:
                print(f"  ⚠️ {sym}: Not available in MT5")
                continue
            
            # Fetch data
            df = fetch_mt5_data(sym, mt5.TIMEFRAME_D1, args.count)
            if df is None or df.empty:
                print(f"  ⚠️ {sym}: No data")
                continue
            
            our_symbol = SYMBOL_MAP.get(sym, sym)
            print(f"  ✅ {sym} → {our_symbol}: {len(df)} bars ({df['timestamp'].iloc[0].date()} to {df['timestamp'].iloc[-1].date()})")
            total_fetched += len(df)
            
            # Update DB
            if args.update_db:
                inserted = update_bars_db(our_symbol, df)
                print(f"     → {inserted} new bars inserted into bars.db")
                total_inserted += inserted
    
    mt5.shutdown()
    
    print(f"\n{'='*80}")
    print(f"FETCHED: {total_fetched} bars")
    if args.update_db:
        print(f"INSERTED: {total_inserted} new bars")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
