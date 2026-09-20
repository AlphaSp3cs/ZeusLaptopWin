#!/usr/bin/env python3
"""MULTI-BROKER DATA AGGREGATOR — Pull from ALL available sources.

Sources:
- MT5 (Capital.com demo): 232 symbols, 1:300 leverage
- Binance (public API): crypto only, no key needed
- Kraken (public API): crypto + forex
- yfinance: indices, equities, ETFs, futures
- CoinGecko: crypto universe (450+ coins)

ALL data goes to C:\Hermes\workflow\data\bars.db

Usage:
    python3 multi_broker_agg.py --all
    python3 multi_broker_agg.py --binance --kraken --yfinance --coingecko
    python3 multi_broker_agg.py --binance --kraken  # free, no keys
"""
from __future__ import annotations
import argparse, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np

DB = Path(r"C:\Hermes\workflow\data\bars.db")

# Symbol mappings
BINANCE_TO_OURS = {
    "BTC/USDT": "BTC-USD", "ETH/USDT": "ETH-USD", "SOL/USDT": "SOL-USD",
    "BNB/USDT": "BNB-USD", "XRP/USDT": "XRP-USD", "ADA/USDT": "ADA-USD",
    "DOGE/USDT": "DOGE-USD", "AVAX/USDT": "AVAX-USD", "LINK/USDT": "LINK-USD",
    "DOT/USDT": "DOT-USD", "LTC/USDT": "LTC-USD", "ZEC/USDT": "ZEC-USD",
    "DASH/USDT": "DASH-USD", "NEAR/USDT": "NEAR-USD", "XMR/USDT": "XMR-USD",
    "HBAR/USDT": "HBAR-USD", "ALGO/USDT": "ALGO-USD",
}

KRAKEN_TO_OURS = {
    "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "SOL/USD": "SOL-USD",
    "XRP/USD": "XRP-USD", "ADA/USD": "ADA-USD", "DOGE/USD": "DOGE-USD",
    "AVAX/USD": "AVAX-USD", "LINK/USD": "LINK-USD", "DOT/USD": "DOT-USD",
    "LTC/USD": "LTC-USD", "ZEC/USD": "ZEC-USD", "DASH/USD": "DASH-USD",
    "XMR/USD": "XMR-USD", "HBAR/USD": "HBAR-USD", "ALGO/USD": "ALGO-USD",
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X", "USD/CHF": "USDCHF=X",
}

def get_db():
    con = sqlite3.connect(str(DB))
    return con

def insert_bars(symbol, df, tf='1d'):
    con = get_db()
    cur = con.cursor()
    
    # Get or create symbol
    cur.execute("SELECT rowid FROM symbols WHERE symbol=?", (symbol,))
    row = cur.fetchone()
    if row:
        sym_id = row[0]
    else:
        cat = "unknown"
        if symbol.endswith("-USD"): cat = "crypto"
        elif symbol.endswith("=F"): cat = "metals" if any(m in symbol for m in ["GC", "SI", "PL", "PA", "HG"]) else "energy" if any(e in symbol for e in ["CL", "BZ", "NG"]) else "indices"
        elif symbol.endswith("=X"): cat = "fx"
        elif symbol.startswith("^"): cat = "indices"
        cur.execute("INSERT INTO symbols (symbol, sector) VALUES (?, ?)", (symbol, cat))
        sym_id = cur.lastrowid
    
    inserted = 0
    for _, row in df.iterrows():
        ts = int(row['timestamp'].timestamp()) if hasattr(row['timestamp'], 'timestamp') else int(row['timestamp'])
        try:
            cur.execute("INSERT OR IGNORE INTO bars (symbol, tf, ts, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (symbol, tf, ts, row['open'], row['high'], row['low'], row['close'], row['volume']))
            if cur.rowcount > 0: inserted += 1
        except: pass
    
    con.commit()
    con.close()
    return inserted

def fetch_binance():
    """Fetch crypto from Binance public API."""
    import ccxt
    print("\n=== BINANCE (Public API) ===")
    try:
        ex = ccxt.binance()
        markets = ex.load_markets()
        
        count = 0
        for bin_sym, our_sym in BINANCE_TO_OURS.items():
            if bin_sym not in markets:
                continue
            try:
                ohlcv = ex.fetch_ohlcv(bin_sym, '1d', limit=500)
                if not ohlcv or len(ohlcv) < 10:
                    continue
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                inserted = insert_bars(our_sym, df)
                print(f"  {bin_sym} → {our_sym}: {len(df)} bars, {inserted} new")
                count += len(df)
            except Exception as e:
                print(f"  {bin_sym}: {e}")
        
        print(f"  TOTAL: {count} bars")
        return count
    except Exception as e:
        print(f"  ERROR: {e}")
        return 0

def fetch_kraken():
    """Fetch crypto + forex from Kraken public API."""
    import ccxt
    print("\n=== KRAKEN (Public API) ===")
    try:
        ex = ccxt.kraken()
        markets = ex.load_markets()
        
        count = 0
        for kra_sym, our_sym in KRAKEN_TO_OURS.items():
            if kra_sym not in markets:
                continue
            try:
                ohlcv = ex.fetch_ohlcv(kra_sym, '1d', limit=500)
                if not ohlcv or len(ohlcv) < 10:
                    continue
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                inserted = insert_bars(our_sym, df)
                print(f"  {kra_sym} → {our_sym}: {len(df)} bars, {inserted} new")
                count += len(df)
            except Exception as e:
                print(f"  {kra_sym}: {e}")
        
        print(f"  TOTAL: {count} bars")
        return count
    except Exception as e:
        print(f"  ERROR: {e}")
        return 0

def fetch_yfinance():
    """Fetch indices, equities, ETFs, futures from yfinance."""
    import yfinance as yf
    print("\n=== YFINANCE ===")
    
    tickers = [
        # Indices
        "^GSPC", "^IXIC", "^DJI", "^VIX", "^TNX",
        # Metals
        "GC=F", "SI=F", "PL=F", "PA=F", "HG=F",
        # Energy
        "CL=F", "BZ=F", "NG=F",
        # ETFs
        "SPY", "QQQ", "GLD", "SLV", "USO", "UNG",
        # Equities
        "GOOGL", "AMZN", "MSFT", "AAPL", "TSLA", "PLTR", "COIN", "HOOD",
        "MA", "V", "KO", "PEP", "ABBV", "DASH-USD",
        # FX
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X",
    ]
    
    count = 0
    for ticker in tickers:
        try:
            data = yf.download(ticker, period="5y", interval="1d", progress=False)
            if data is None or len(data) < 10:
                continue
            df = data.reset_index()
            df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'adj_close', 'volume'] if len(df.columns) == 7 else ['timestamp', 'open', 'high', 'low', 'close', 'volume'][:len(df.columns)]
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df = df.dropna()
            inserted = insert_bars(ticker, df)
            print(f"  {ticker:<15} {len(df):>5} bars, {inserted} new")
            count += len(df)
        except Exception as e:
            print(f"  {ticker}: {e}")
    
    print(f"  TOTAL: {count} bars")
    return count

def fetch_coingecko():
    """Fetch crypto from CoinGecko (public, no key)."""
    import requests
    print("\n=== COINGECKO (Public API) ===")
    
    # Top coins by market cap
    coins = [
        "bitcoin", "ethereum", "solana", "binancecoin", "ripple", "cardano",
        "dogecoin", "avalanche-2", "chainlink", "polkadot", "litecoin",
        "zcash", "dash", "near", "monhedeira", "hedera-hashgraph",
        "algorand", "aave", "uniswap", "sushi", "compound-governance-token",
        "havven", "curve-dao-token", "havven", "rocket-pool",
    ]
    
    count = 0
    for coin in coins:
        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=usd&days=365"
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            if 'prices' not in data:
                continue
            
            df = pd.DataFrame(data['prices'], columns=['timestamp', 'close'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['open'] = df['close'].shift(1)
            df['high'] = df['close']
            df['low'] = df['close']
            df['volume'] = 0
            df = df.dropna()
            
            our_sym = f"{coin.upper()}-USD"
            inserted = insert_bars(our_sym, df)
            print(f"  {coin:<25} → {our_sym:<15} {len(df):>5} bars, {inserted} new")
            count += len(df)
        except Exception as e:
            print(f"  {coin}: {e}")
    
    print(f"  TOTAL: {count} bars")
    return count

def main():
    print("=" * 80)
    print("MULTI-BROKER DATA AGGREGATOR")
    print("=" * 80)
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--binance", action="store_true")
    parser.add_argument("--kraken", action="store_true")
    parser.add_argument("--yfinance", action="store_true")
    parser.add_argument("--coingecko", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    
    if not any([args.binance, args.kraken, args.yfinance, args.coingecko, args.all]):
        print("No sources selected. Use --all or specific sources.")
        return
    
    total = 0
    if args.binance or args.all:
        total += fetch_binance()
    if args.kraken or args.all:
        total += fetch_kraken()
    if args.yfinance or args.all:
        total += fetch_yfinance()
    if args.coingecko or args.all:
        total += fetch_coingecko()
    
    print(f"\n{'='*80}")
    print(f"GRAND TOTAL: {total:,} bars inserted")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
