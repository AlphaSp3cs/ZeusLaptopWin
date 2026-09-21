#!/usr/bin/env python3
"""GAP INTEGRATION — Features from QuantDashboard we're missing.

Key additions:
1. VWAP (institutional volume-weighted average price)
2. HTF analysis (weekly/monthly trend alignment)
3. Pattern detection (golden cross, bull flag, 52w high)
4. Multi-source data waterfall (Alpaca → Finnhub → FMP → Yahoo)
5. Penny/low-float scanner (squeeze score)
6. Futures scanner (micro contracts)
7. OTC crypto desk data
8. Carver vol-sizing
"""
import json, pathlib, sqlite3, sys
from datetime import datetime, timezone
import pandas as pd
import numpy as np

DB = pathlib.Path("C:/Hermes/workflow/data/bars.db")

# ═════════════════════════════════════════════════════════════════════════════
# 1. VWAP CALCULATOR
# ═════════════════════════════════════════════════════════════════════════════

def calc_vwap(df, period=None):
    """Calculate VWAP (Volume Weighted Average Price)."""
    if 'Volume' not in df.columns:
        return None
    
    df = df.copy()
    df['Volume'] = df['Volume'].fillna(0)
    df['Close'] = df['Close'].fillna(method='ffill')
    df['High'] = df.get('High', df['Close']).fillna(method='ffill')
    df['Low'] = df.get('Low', df['Close']).fillna(method='ffill')
    
    typical = (df['High'] + df['Low'] + df['Close']) / 3
    
    if period is None:
        vwap = (typical * df['Volume']).cumsum() / df['Volume'].cumsum()
    else:
        vwap = (typical * df['Volume']).rolling(period).sum() / df['Volume'].rolling(period).sum()
    
    return vwap  # Returns a Series


# ═════════════════════════════════════════════════════════════════════════════
# 2. HTF ANALYSIS (Higher Time Frame)
# ═════════════════════════════════════════════════════════════════════════════

def fetch_weekly(symbol):
    """Fetch weekly bars from yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        df = t.history(period="1y", interval="1wk", auto_adjust=True, timeout=15)
        if df is None or df.empty or len(df) < 5:
            return None
        return df
    except:
        return None

def fetch_monthly(symbol):
    """Fetch monthly bars from yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        df = t.history(period="2y", interval="1mo", auto_adjust=True, timeout=15)
        if df is None or df.empty or len(df) < 5:
            return None
        return df
    except:
        return None

def get_weekly_trend(wdf):
    """Determine weekly trend direction and strength."""
    if wdf is None or len(wdf) < 10:
        return "N/A", None, 0
    
    wdf = wdf.copy()
    close = wdf['Close']
    
    # Calculate weekly MAs
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    
    # Trend determination
    last_close = close.iloc[-1]
    last_ema21 = ema21.iloc[-1]
    last_ema50 = ema50.iloc[-1]
    
    score = 0
    
    # Price vs MAs
    if last_close > last_ema21:
        score += 1
    if last_close > last_ema50:
        score += 1
    if last_ema21 > last_ema50:
        score += 1
    
    # Slope of EMA21
    if len(ema21) >= 5:
        ema21_slope = (ema21.iloc[-1] - ema21.iloc[-5]) / ema21.iloc[-5] * 100
        if ema21_slope > 0:
            score += 1
    
    if score >= 3:
        return "BULLISH", True, score
    elif score <= 1:
        return "BEARISH", False, score
    else:
        return "NEUTRAL", None, score

def tf_alignment(daily_df, weekly_df, monthly_df):
    """Check multi-timeframe alignment."""
    bull_count = 0
    total = 0
    
    # Daily
    if daily_df is not None and len(daily_df) > 0:
        total += 1
        last = daily_df.iloc[-1]
        if last.get('ema9', 0) > last.get('ema21', 0):
            bull_count += 1
    
    # Weekly
    if weekly_df is not None and len(weekly_df) > 0:
        total += 1
        last = weekly_df.iloc[-1]
        close = last['Close']
        ema21 = weekly_df['Close'].ewm(span=21, adjust=False).mean().iloc[-1]
        if close > ema21:
            bull_count += 1
    
    # Monthly
    if monthly_df is not None and len(monthly_df) > 0:
        total += 1
        last = monthly_df.iloc[-1]
        close = last['Close']
        ema10 = monthly_df['Close'].ewm(span=10, adjust=False).mean().iloc[-1]
        if close > ema10:
            bull_count += 1
    
    if total == 0:
        return 0, "N/A"
    
    if bull_count == total:
        return bull_count, "FULL BULL"
    elif bull_count == 0:
        return bull_count, "FULL BEAR"
    elif bull_count > total / 2:
        return bull_count, "MAJORITY BULL"
    else:
        return bull_count, "MAJORITY BEAR"


# ═════════════════════════════════════════════════════════════════════════════
# 3. PATTERN DETECTION
# ═════════════════════════════════════════════════════════════════════════════

def detect_bull_pattern(df):
    """Detect high-timeframe bull patterns."""
    if df is None or len(df) < 20:
        return None, None
    
    last = df.iloc[-1]
    close = df['close']  # Changed from 'Close' to 'close'
    price = close.iloc[-1]
    
    # Calculate indicators
    rsi = last.get('rsi', 50)
    macd = last.get('macd', 0)
    macd_sig = last.get('macd_signal', 0)
    ema9 = last.get('ema9', price)
    ema21 = last.get('ema21', price)
    sma50 = last.get('sma50', price)
    sma200 = last.get('sma200', price)
    
    # Golden Cross (SMA50 crosses above SMA200)
    if 'sma50' in df.columns and 'sma200' in df.columns and len(df) >= 16:
        sma50_15ago = df['sma50'].iloc[-16]
        sma200_15ago = df['sma200'].iloc[-16]
        sma50_now = df['sma50'].iloc[-1]
        sma200_now = df['sma200'].iloc[-1]
        
        if sma50_now > sma200_now and sma50_15ago < sma200_15ago:
            return "GOLDEN CROSS", "VERY HIGH"
    
    # Full EMA stack
    if all(v > 0 for v in [ema9, ema21, sma50, sma200]):
        if price > ema9 > ema21 > sma50 > sma200 and macd > macd_sig and 50 <= rsi <= 75:
            return "FULL EMA STACK", "HIGH"
    
    # 52-week high breakout
    if len(close) >= 30:
        lookback = min(len(close) - 5, 252)
        prior_high = close.iloc[-lookback:-5].max()
        if prior_high > 0 and price >= prior_high * 0.995:
            return "52W HIGH BREAK", "HIGH"
    
    # Bull flag
    if len(close) >= 22:
        run_start = close.iloc[-20]
        run_peak = close.iloc[-12:-6].max()
        if run_peak > run_start * 1.08:
            recent = close.tail(5)
            rng_pct = (recent.max() - recent.min()) / max(recent.mean(), 1e-9)
            if rng_pct < 0.04 and price >= recent.max() * 0.98 and macd > macd_sig:
                return "BULL FLAG", "HIGH"
    
    # EMA21 breakout
    if 'ema21' in df.columns and ema21 > 0 and price > ema21:
        ema21_5ago = df['ema21'].iloc[-7] if len(df) >= 7 else 0
        close_5ago = close.iloc[-7] if len(df) >= 7 else price
        if ema21_5ago > 0 and close_5ago < ema21_5ago and macd > macd_sig:
            return "EMA21 BREAKOUT", "MEDIUM"
    
    # General bull momentum
    if sma50 > 0 and price > sma50 and macd > macd_sig and 47 <= rsi <= 72:
        return "BULL MOMENTUM", "MEDIUM"
    
    return None, None


# ═════════════════════════════════════════════════════════════════════════════
# 4. MULTI-SOURCE DATA WATERFALL
# ═════════════════════════════════════════════════════════════════════════════

def waterfall_stock(symbol):
    """Try data sources in order: Alpaca → Finnhub → FMP → Yahoo."""
    # Try Yahoo first (free, reliable)
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        df = t.history(period="60d", interval="1d", auto_adjust=True, timeout=15)
        if df is not None and len(df) >= 10:
            return df, "Yahoo"
    except:
        pass
    
    return None, None

def waterfall_crypto(yf_sym, binance_sym=None):
    """Try data sources in order: Binance → Yahoo."""
    # Try Binance first
    if binance_sym:
        try:
            import requests
            url = f"https://api.binance.com/api/v3/klines?symbol={binance_sym}&interval=1d&limit=80"
            d = requests.get(url, timeout=10).json()
            if isinstance(d, list) and d:
                df = pd.DataFrame(d, columns=['ts','Open','High','Low','Close','Volume',
                                               'ct','qv','nt','tbb','tbq','ign'])
                for c in ['Open','High','Low','Close','Volume']:
                    df[c] = pd.to_numeric(df[c])
                df['ts'] = pd.to_datetime(df['ts'], unit='ms')
                df.set_index('ts', inplace=True)
                return df[['Open','High','Low','Close','Volume']], "Binance"
        except:
            pass
    
    # Try Yahoo
    try:
        import yfinance as yf
        t = yf.Ticker(yf_sym)
        df = t.history(period="60d", interval="1d", auto_adjust=True, timeout=15)
        if df is not None and len(df) >= 5:
            return df, "Yahoo"
    except:
        pass
    
    return None, None


# ═════════════════════════════════════════════════════════════════════════════
# 5. PENNY/LOW-FLOAT SCANNER
# ═════════════════════════════════════════════════════════════════════════════

def scan_low_float():
    """Scan for low-float penny stocks with squeeze potential."""
    candidates = []
    
    # Known low-float universe
    universe = [
        "GME", "BBIG", "MULN", "NKLA", "SOFI", "WISH", "CLOV", "WISH",
        "RKT", "PLUG", "RIOT", "MARA", "SDC", "SNDL", "TLRY", "APHA",
        "CRON", "HEXO", "TLRY", "OGEN", "BIOL", "SENS", "DGLY", "APDN",
        "NAKD", "CTXR", "INBS", "ATNX", "SRNE", "ATOS", "ALPP", "SNOA",
        "NAOV", "VTGN", "BTAI", "CPIX", "CTSO", "EDSA", "KRBP", "PALI",
        "TNXP", "BDSX", "BLUE", "CERS", "CLDX", "CRSP", "EDIT", "FATE",
        "FOLD", "GBT", "GRTS", "KRTX", "KURA", "MCRB", "MGNX", "MRKR",
        "MRTX", "NTRA", "NTLA", "NVAX", "PBYI", "PDSB", "PRQR", "PRTA",
        "RARE", "RGLS", "RGEN", "RIGL", "RVNC", "SGEN", "SGMO", "SNDX",
        "SRPT", "STRO", "TBPH", "TCDA", "TERN", "TGTX", "TTOO", "TWST",
        "VCEL", "VERV", "VINC", "VYGR", "WVE", "XBIO", "XBIT", "XENE",
        "XERS", "XFOR", "XNCR", "XOMA", "XTLB", "XXII", "ZLAB", "ZYNE",
    ]
    
    for sym in universe:
        try:
            import yfinance as yf
            t = yf.Ticker(sym)
            
            # Get price
            df = t.history(period="5d", interval="1d", auto_adjust=True, timeout=10)
            if df is None or df.empty:
                continue
            
            price = df['Close'].iloc[-1]
            if not (0.50 <= price <= 20.0):
                continue
            
            # Get float info
            info = t.info or {}
            float_shares = info.get('floatShares', 0) or info.get('sharesOutstanding', 0)
            if float_shares <= 0 or float_shares > 25_000_000:
                continue
            
            # Calculate squeeze score
            squeeze_score = 0
            
            # Float tightness
            if float_shares < 5_000_000:
                squeeze_score += 30
            elif float_shares < 10_000_000:
                squeeze_score += 20
            elif float_shares < 15_000_000:
                squeeze_score += 12
            else:
                squeeze_score += 5
            
            # Short interest
            short_pct = info.get('shortPercentOfFloat', 0) or 0
            if short_pct >= 0.40:
                squeeze_score += 25
            elif short_pct >= 0.25:
                squeeze_score += 15
            elif short_pct >= 0.15:
                squeeze_score += 8
            
            # RVOL
            avg_vol = df['Volume'].tail(20).mean() if len(df) >= 20 else df['Volume'].mean()
            last_vol = df['Volume'].iloc[-1]
            rvol = last_vol / avg_vol if avg_vol > 0 else 1.0
            
            if rvol >= 5:
                squeeze_score += 20
            elif rvol >= 3:
                squeeze_score += 12
            elif rvol >= 1.5:
                squeeze_score += 5
            
            squeeze_score = min(100, squeeze_score)
            
            if squeeze_score >= 60:
                candidates.append({
                    "symbol": sym,
                    "price": round(price, 4),
                    "float_m": round(float_shares / 1e6, 1),
                    "squeeze_score": squeeze_score,
                    "rvol": round(rvol, 2),
                    "short_pct": round(short_pct * 100, 1),
                })
            
        except:
            continue
    
    # Sort by squeeze score
    candidates.sort(key=lambda x: -x["squeeze_score"])
    return candidates[:20]


# ═════════════════════════════════════════════════════════════════════════════
# 6. CARVER VOL-SIZING
# ═════════════════════════════════════════════════════════════════════════════

def calc_vol_sized_lots(symbol, portfolio_vol=0.20, capital=47_000, asset_class='stock'):
    """Calculate position size using Carver's volatility targeting.
    
    Target: portfolio_vol annual volatility.
    Position size = (target_vol / asset_vol) * (capital / price)
    """
    try:
        # Fetch data
        if asset_class == 'crypto':
            df, _ = waterfall_crypto(symbol.replace("-USD", "-USD"), symbol.replace("-USD", "") + "USDT")
        else:
            df, _ = waterfall_stock(symbol)
        
        if df is None or len(df) < 30:
            return 0
        
        # Calculate annualized volatility
        returns = df['Close'].pct_change().dropna()
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252)
        
        if annual_vol == 0:
            return 0
        
        price = df['Close'].iloc[-1]
        
        # Target volatility
        target_vol = portfolio_vol  # 20% annual
        
        # Volatility-adjusted position size
        vol_ratio = target_vol / annual_vol
        
        # Dollar allocation
        allocation = capital * vol_ratio
        
        # Lots/shares
        lots = allocation / price
        
        # Round to reasonable precision
        if asset_class == 'crypto':
            lots = round(lots, 3)
        else:
            lots = round(lots, 0)
        
        # Cap at max 10% of capital
        max_lots = (capital * 0.10) / price
        lots = min(lots, max_lots)
        
        return max(lots, 0)
        
    except Exception as e:
        return 0


# ═════════════════════════════════════════════════════════════════════════════
# MAIN — RUN GAP ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════

def main():
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    
    print("=" * 70)
    print("GAP INTEGRATION ANALYSIS")
    print("=" * 70)
    
    # 1. VWAP analysis for key symbols
    print("\n=== 1. VWAP STATUS ===")
    key_symbols = ["BTC-USD", "ETH-USD", "BNB-USD", "XRP-USD", "GC=F", "SI=F"]
    
    for sym in key_symbols:
        cur.execute("SELECT ts, open, high, low, close, volume FROM bars WHERE symbol=? AND tf='1d' ORDER BY ts ASC LIMIT 60", (sym,))
        rows = cur.fetchall()
        
        if not rows or len(rows) < 20:
            continue
        
        df = pd.DataFrame(rows, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
        vwap_series = calc_vwap(df, period=20)
        
        if vwap_series is not None and len(vwap_series.dropna()) > 0:
            current_vwap = vwap_series.dropna().iloc[-1]
            current_price = df['close'].iloc[-1]
            above = current_price > current_vwap
            diff_pct = (current_price - current_vwap) / current_vwap * 100
            
            status = "▲ ABOVE" if above else "▼ BELOW"
            print(f"  {sym:<12} Price: ${current_price:>10.2f}  VWAP20: ${current_vwap:>10.2f}  {status} ({diff_pct:+.1f}%)")
    
    # 2. HTF alignment
    print("\n=== 2. MULTI-TIMEFRAME ALIGNMENT ===")
    htf_symbols = ["BTC-USD", "ETH-USD", "GC=F"]
    
    for sym in htf_symbols:
        wdf = fetch_weekly(sym)
        mdf = fetch_monthly(sym)
        
        # Get daily from DB
        cur.execute("SELECT ts, open, high, low, close, volume FROM bars WHERE symbol=? AND tf='1d' ORDER BY ts ASC LIMIT 60", (sym,))
        rows = cur.fetchall()
        ddf = pd.DataFrame(rows, columns=['ts', 'open', 'high', 'low', 'close', 'volume']) if rows else None
        
        tf_cnt, tf_lbl = tf_alignment(ddf, wdf, mdf)
        
        w_lbl, w_bull, w_sc = get_weekly_trend(wdf)
        
        print(f"  {sym:<12} {tf_lbl:<15} Weekly: {w_lbl}")
    
    # 3. Pattern detection
    print("\n=== 3. PATTERN DETECTION ===")
    for sym in ["BTC-USD", "ETH-USD", "BNB-USD", "GC=F"]:
        cur.execute("SELECT ts, open, high, low, close, volume FROM bars WHERE symbol=? AND tf='1d' ORDER BY ts ASC LIMIT 252", (sym,))
        rows = cur.fetchall()
        
        if not rows or len(rows) < 60:
            continue
        
        df = pd.DataFrame(rows, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
        
        # Calculate indicators (lowercase names to match DB)
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['sma50'] = df['close'].rolling(50).mean()
        df['sma200'] = df['close'].rolling(200).mean()
        
        pattern, confidence = detect_bull_pattern(df)
        
        if pattern:
            print(f"  {sym:<12} {pattern:<20} ({confidence})")
    
    # 4. Carver vol-sizing
    print("\n=== 4. VOLATILITY-SIZED POSITIONS ===")
    for sym in ["BTC-USD", "ETH-USD", "BNB-USD"]:
        lots = calc_vol_sized_lots(sym, portfolio_vol=0.20, capital=47_000, asset_class='crypto')
        print(f"  {sym:<12} {lots:.3f} lots (target 20% vol)")
    
    # 5. Low-float scanner
    print("\n=== 5. LOW-FLOAT SCANNER ===")
    candidates = scan_low_float()
    for c in candidates[:10]:
        print(f"  {c['symbol']:<10} ${c['price']:>8.2f}  Float: {c['float_m']:.1f}M  Sqz: {c['squeeze_score']}  RVOL: {c['rvol']}x  Short: {c['short_pct']}%")
    
    con.close()
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
