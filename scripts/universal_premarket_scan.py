#!/usr/bin/env python3
"""
Universal Premarket Scanner - All Asset Classes
===============================================
Scans ETFs, stocks, bonds, futures, rates, forex, commodities, indices, crypto
for overbought/oversold setups and VWAP-based entries.

Output: universal_scan_results.json with all qualified trades
"""

import json
import os
import time
import urllib.request
import urllib.error
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from collections import OrderedDict
from pathlib import Path
import logging

HOME = Path.home()

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# =============================================================================
# ASSET CLASS DEFINITIONS
# =============================================================================

ASSET_UNIVERSE = {
    "FOREX_MAJORS": {
        "symbols": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "USDCAD=X", "AUDUSD=X", "NZDUSD=X"],
        "names": ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD"],
        "category": "forex"
    },
    "FOREX_CROSSES": {
        "symbols": ["EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "CHFJPY=X", "EURAUD=X", "GBPAUD=X"],
        "names": ["EUR/GBP", "EUR/JPY", "GBP/JPY", "AUD/JPY", "CHF/JPY", "EUR/AUD", "GBP/AUD"],
        "category": "forex"
    },
    "US_INDICES": {
        "symbols": ["^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX"],
        "names": ["S&P 500", "NASDAQ", "Dow Jones", "Russell 2000", "VIX"],
        "category": "indices"
    },
    "EU_INDICES": {
        "symbols": ["^GDAXI", "^FCHI", "^FTSE", "^IBEX", "^SSMI"],
        "names": ["DAX", "CAC 40", "FTSE 100", "IBEX 35", "SMI"],
        "category": "indices"
    },
    "ASIA_INDICES": {
        "symbols": ["^N225", "^HSI", "000001.SS", "^NSEI", "^AXJO"],
        "names": ["Nikkei 225", "Hang Seng", "SSE Composite", "Nifty 50", "ASX 200"],
        "category": "indices"
    },
    "LATAM_INDICES": {
        "symbols": ["^BVSP", "^MERV"],
        "names": ["IBOVESPA", "MERVAL"],
        "category": "indices"
    },
    "COMMODITIES_METALS": {
        "symbols": ["GC=F", "SI=F", "PL=F", "PA=F", "HG=F"],
        "names": ["Gold", "Silver", "Platinum", "Palladium", "Copper"],
        "category": "commodities"
    },
    "COMMODITIES_ENERGY": {
        "symbols": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
        "names": ["WTI Crude", "Brent Crude", "Natural Gas", "Heating Oil", "RBOB Gasoline"],
        "category": "commodities"
    },
    "COMMODITIES_AGRICULTURE": {
        "symbols": ["ZW=F", "ZC=F", "ZS=F", "CT=F", "SB=F", "KC=F"],
        "names": ["Wheat", "Corn", "Soybeans", "Cotton", "Sugar", "Coffee"],
        "category": "commodities"
    },
    "BONDS_US": {
        "symbols": ["^IRX", "^FVX", "^TNX", "^TYX"],
        "names": ["13-Week Bill", "5-Year Note", "10-Year Note", "30-Year Bond"],
        "category": "bonds"
    },
    "BONDS_EU": {
        "symbols": ["DE10Y=F", "GB10Y=F", "FR10Y=F", "IT10Y=F"],
        "names": ["Bund 10Y", "Gilt 10Y", "OAT 10Y", "BTP 10Y"],
        "category": "bonds"
    },
    "ETF_SECTORS": {
        "symbols": ["XLF", "XLE", "XLV", "XLI", "XLB", "XLP", "XLU", "XLY", "XLK", "XLRE", "XLC"],
        "names": ["Financials", "Energy", "Healthcare", "Industrials", "Materials", "Consumer Staples", "Utilities", "Consumer Disc", "Technology", "Real Estate", "Communication"],
        "category": "etfs"
    },
    "ETF_BONDS": {
        "symbols": ["TLT", "IEF", "SHY", "LQD", "HYG", "TIP", "SHV"],
        "names": ["20+Y Treasury", "7-10Y Treasury", "1-3Y Treasury", "Investment Grade", "High Yield", "TIPS", "Short Treasury"],
        "category": "etfs"
    },
    "ETF_COMMODITIES": {
        "symbols": ["GLD", "SLV", "USO", "UNG", "DBA", "WEAT", "CORN", "SOYB"],
        "names": ["Gold", "Silver", "Oil", "Natural Gas", "Agriculture", "Wheat", "Corn", "Soybeans"],
        "category": "etfs"
    },
    "ETF_FACTORS": {
        "symbols": ["USMV", "MTUM", "QUAL", "VLUE", "SMLF", "SPY", "QQQ", "IWM", "DIA"],
        "names": ["Min Vol", "Momentum", "Quality", "Value", "Small Cap", "S&P 500", "NASDAQ 100", "Russell 2000", "Dow Jones"],
        "category": "etfs"
    },
    "US_SMALL_CAP": {
        # US small-cap equities (~$300M–$3B market cap), Finviz-style watchlist.
        # This is the scanner's small-cap universe — same role as every other
        # class here. Make it tradeable in the daytime universal (hunt/scan)
        # scan; nightshift_scan.py classifies it correlation-only because the
        # US cash session is closed overnight (US small caps don't trade then).
        "symbols": [
            "BBW", "TZOO", "HROW", "NX", "CODI", "SAFE", "BFS", "MOV", "CRAI",
            "SCVL", "BOOT", "ZUMZ", "GES", "DLTH", "SPWH", "BKE", "CHS", "GCO",
            "VRA", "LOCO", "PLCE", "LXU", "UAN", "CDE", "MAG", "SILV", "GATO",
            "AVD", "CALM", "FDP", "VIA", "MTLS", "CENT", "RAVE", "ARR", "NYMT",
            "TWO", "CHMI", "HLIT", "SONO", "GME", "FARM", "UNFI", "FIVE",
        ],
        "names": [
            "Build-A-Bear", "Travelzoo", "Harrow Health", "Quanex", "Compass Diversified",
            "Safehold", "Saul Centers", "Movado", "CRA Intl", "Shoe Carnival", "Boot Barn",
            "Zumiez", "Guess", "Duluth Trading", "Sportsman's WH", "Buckle", "Chico's FAS",
            "Genesco", "Vera Bradley", "El Pollo Loco", "Children's Place", "LSB Industries",
            "CVR Partners", "Coeur Mining", "MAG Silver", "SilverCrest", "Gatos Silver",
            "American Vanguard", "Cal-Maine", "Fresh Del Monte", "Viad", "Materialise",
            "Central Garden", "Rave Restaurant", "ARMOUR Res REIT", "NY Mortgage",
            "Two Harbors", "Cherry Hill Mtg", "Harmonic", "Sonos", "GameStop", "Farmer Bros",
            "United Natural Foods", "Five Below",
        ],
        "category": "small_cap"
    },
    "US_MICRO_CAP": {
        # US micro-cap / penny equities (<$300M mkt cap, mostly sub-$5) — the
        # "AlphaSp3c MasterControl micro cap picks" watchlist. Same role as
        # every other universe group. Tradeable in the daytime universal
        # (hunt/scan) scan; nightshift_scan.py treats it correlation-only
        # (US cash session closed overnight). The scanner skips any ticker
        # that returns <30 daily bars (delisted / halted names).
        "symbols": [
            "ZOM", "ATER", "TOPS", "SCKT", "PHUN", "BNGO", "NAK", "SPI", "MMAT",
            "CTXR", "XSPA", "SENS", "OPTT", "GREE", "SRAX", "NTRB", "ONCS",
            "VIVE", "MYSZ", "SHLO", "HCMC", "SIRC", "MARK", "NXTD", "AUGX",
            "GLBS", "CCTL", "EDSA", "TLGT", "ALPP", "ABML", "UAMY", "NXGL",
            "ASNS", "PMCB", "SONN", "KTOV", "GTX", "PLSE", "RWLK", "VYGR",
            "BDR", "VSTS",
        ],
        "names": [
            "Zomedica", "Aterian", "Top Ships", "Socket Mobile", "Phunware",
            "Bionano", "Northern Dynasty", "SPI Energy", "Meta Materials",
            "Citius Pharma", "XpresSpa", "Senseonics", "Ocean Power Tech",
            "Greenidge", "SRAX", "Nutriband", "OncoSec", "Viveve", "My Size",
            "Shiloh Ind", "Healthier Choices", "Sinclair", "Remark", "NXT-ID",
            "Augmedix", "Globus Mar", "Canso", "Edesa Biotech", "Teligent",
            "Alpha Pro Tech", "Absorb", "UAMY", "Nexgel", "Ascendis", "PMC Bio",
            "Sonnet Bio", "Kitov", "Garrett", "Pulse", "ReWalk", "Voyager",
            "Blonder", "Vast Renewables",
        ],
        "category": "micro_cap"
    },
    "FUTURES_EQUITY": {
        "symbols": ["ES=F", "NQ=F", "YM=F", "RTY=F"],
        "names": ["E-mini S&P", "E-mini NASDAQ", "E-mini Dow", "E-mini Russell"],
        "category": "futures"
    },
    "FUTURES_COMMODITIES": {
        "symbols": ["GC=F", "SI=F", "CL=F", "NG=F", "ZC=F", "ZS=F", "ZW=F"],
        "names": ["Gold", "Silver", "WTI", "Nat Gas", "Corn", "Soybeans", "Wheat"],
        "category": "futures"
    },
    "FUTURES_RATES": {
        "symbols": ["ZB=F", "ZN=F", "ZF=F", "ZT=F"],
        "names": ["30Y Bond", "10Y Note", "5Y Note", "2Y Note"],
        "category": "futures"
    },
    "FUTURES_FX": {
        "symbols": ["6E=F", "6J=F", "6B=F", "6A=F", "6C=F"],
        "names": ["Euro FX", "JPY FX", "GBP FX", "AUD FX", "CAD FX"],
        "category": "futures"
    },
}

# Crypto via yfinance '-USD' pairs.
# Previously CoinGecko: ~50 sequential OHLC calls that the free tier 429s on,
# which silently collapsed the crypto universe to 4 assets (one a stablecoin).
# yfinance is already a dependency, batches in one call, and returns real
# volume, so crypto now flows through the same scan_asset_class() path as
# every other class.
# Validated 2026-08-07 against yfinance: 43 of 53 candidates returned real
# daily bars. Dropped the 10 it reports as delisted/renamed (UNI-USD/MATIC-USD->
# POL/SUI-USD/APT-USD/RNDR-USD/GRT-USD/STX-USD/PEPE-USD/IMX-USD/FTM-USD) plus the
# old mangled tickers (UNI7083-USD, SUI20947-USD). Crypto trades 24/7 so it
# populates in EVERY session; kept identical to crypto_universe.CRYPTO_YF_SYMBOLS.
# -----------------------------------------------------------------------------
# RESOLVED-UNIVERSE LOADER (full-sector coverage)
# universe_builder.py enumerates every asset our brokers list; universe_resolver.py
# validates which of those actually return bars. This loader merges that into the
# scan so a sector scan is never silently limited to the curated core list above.
# Rebuild with:  python3 universe_builder.py && python3 universe_resolver.py --all
# -----------------------------------------------------------------------------
_RESOLVED_PATH = Path.home() / "universe_resolved.json"


def _load_resolved():
    try:
        import json as _j
        return _j.loads(_RESOLVED_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [universe] WARNING: no resolved universe ({e}) -- "
              f"scanning the CURATED CORE ONLY, sector coverage is NOT complete. "
              f"Run: python3 universe_builder.py && python3 universe_resolver.py --all")
        return {}


def _resolved_crypto():
    """Full validated crypto list, falling back to the curated list."""
    syms = _load_resolved().get("CRYPTO", {}).get("symbols", [])
    return syms or CRYPTO_YF_SYMBOLS


CRYPTO_YF_SYMBOLS = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "DOGE-USD",
    "ADA-USD", "AVAX-USD", "TRX-USD", "LINK-USD", "DOT-USD", "LTC-USD",
    "BCH-USD", "NEAR-USD", "ICP-USD", "ETC-USD", "XLM-USD", "ATOM-USD",
    "FIL-USD", "HBAR-USD", "VET-USD", "INJ-USD", "AAVE-USD", "RUNE-USD",
    "ALGO-USD", "XMR-USD", "EGLD-USD", "THETA-USD", "AXS-USD", "SAND-USD",
    "MANA-USD", "CRV-USD", "MKR-USD", "AR-USD", "OP-USD", "TIA-USD",
    "SEI-USD", "WIF-USD", "FLOKI-USD", "DYDX-USD", "KAVA-USD", "ZEC-USD",
    "DASH-USD",
]

# -----------------------------------------------------------------------------
# STOCK SCAN HARD-GATE (standing rule)
# Equities must show a real liquidity event before they become trade candidates:
#   * relative volume >= VOL_RATIO_FLOOR vs the 50-DAY average  (not the 20d)
#   * longs must additionally be GAPPING UP (today's open > prior close)
# No price or market-cap floor — "any price, any market".
# All other filters (liquidity floors, R:R gates, news/regime context) still apply.
# -----------------------------------------------------------------------------
STOCK_CATEGORIES = {"small_cap", "micro_cap"}
VOL_RATIO_FLOOR = 4.0     # x4 relative volume vs 50d avg, minimum
GAP_UP_MIN_PCT = 1.0      # longs must gap up at least this much (%)

# Last-scan memory snapshot file (standing rule: remember the previous scan)
LAST_SCAN_SNAPSHOT = "universal_scan_last_snapshot.json"

# =============================================================================
# LAST-SCAN MEMORY (standing rule)
# Each scan persists a compact per-symbol snapshot; the NEXT scan attaches the
# prior reading + deltas to every asset AS IT POPULATES, so drift since the last
# scan is visible in the data, not just in a separate report.
# =============================================================================

def load_last_scan_snapshot():
    """Return the most recent scan snapshot dict, or None if none exists."""
    if not os.path.exists(LAST_SCAN_SNAPSHOT):
        return None
    try:
        with open(LAST_SCAN_SNAPSHOT) as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: could not read last-scan snapshot: {e}")
        return None


def save_last_scan_snapshot(all_results):
    """Persist a compact per-symbol snapshot of THIS scan so the next run can
    compare. Called at the end of main()."""
    snap = {"scan_timestamp": all_results.get("scan_timestamp"), "symbols": {}}
    for cat in all_results.get("categories", {}).values():
        for a in cat.get("assets", []):
            sym = (a.get("symbol") or "").upper()
            if not sym:
                continue
            snap["symbols"][sym] = {
                "price": a.get("price"),
                "rsi": a.get("rsi"),
                "vwap_distance_pct": a.get("vwap_distance_pct"),
                "vol_ratio_50": a.get("vol_ratio_50"),
                "gap_up_pct": a.get("gap_up_pct"),
            }
    try:
        with open(LAST_SCAN_SNAPSHOT, "w") as f:
            json.dump(snap, f, indent=2)
    except Exception as e:
        print(f"Warning: could not save last-scan snapshot: {e}")


# =============================================================================
# TECHNICAL INDICATORS
# =============================================================================

def calculate_rsi(prices, period=14):
    """Calculate Wilder's RSI"""
    if len(prices) < period + 1:
        return 50
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_atr(high, low, close, period=14):
    """Calculate ATR-14"""
    if len(close) < period + 1:
        return np.mean(high - low) if len(high) > 0 else 0
    
    tr = np.maximum(high[1:] - low[1:], 
                    np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
    return np.mean(tr[-period:])

def calculate_ema(prices, period, strict=False):
    """
    Calculate EMA.

    NOTE ON INSUFFICIENT DATA: historically this returned prices[-1] when
    len(prices) < period, which silently made `ema200 == price` for every
    asset on a 3mo (~68 bar) fetch. That turned every `price > ema200`
    trend test into a coin-flip on floating-point equality and handed out
    bogus trend bonuses. Pass strict=True to get None instead, so callers
    can guard explicitly rather than trusting a fabricated value.
    """
    if len(prices) < period:
        if strict:
            return None
        return prices[-1] if len(prices) > 0 else 0
    k = 2 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = price * k + ema * (1 - k)
    return ema

def calculate_vwap(high, low, close, volume):
    """Calculate VWAP for session.

    Volume-less feeds (yfinance FX '=X' pairs, most cash indices) report
    volume==0 for every bar. The old code returned close[-1], which made
    vwap == spot and vwap_distance_pct == 0.00 for all 14 FX pairs, so forex
    could never satisfy the scorer's VWAP-deviation test. Fall back to an
    unweighted mean of typical price (TWAP) so deviation is meaningful.
    """
    if len(close) == 0:
        return 0
    typical_price = (high + low + close) / 3
    if np.sum(volume) == 0:
        return float(np.mean(typical_price))
    return np.sum(typical_price * volume) / np.sum(volume)

def calculate_vwap_bands(high, low, close, volume, num_std=1):
    """Calculate VWAP with standard deviation bands"""
    vwap = calculate_vwap(high, low, close, volume)
    typical_price = (high + low + close) / 3
    # Volume-weighted standard deviation
    if np.sum(volume) > 0:
        variance = np.sum(volume * (typical_price - vwap) ** 2) / np.sum(volume)
        std = np.sqrt(variance)
    else:
        std = np.std(typical_price)
    return {
        "vwap": vwap,
        "upper_1": vwap + num_std * std,
        "lower_1": vwap - num_std * std,
        "upper_2": vwap + 2 * num_std * std,
        "lower_2": vwap - 2 * num_std * std
    }

def get_distance_from_vwap(price, vwap_data):
    """Get % distance from VWAP"""
    vwap = vwap_data["vwap"]
    if vwap == 0:
        return 0
    return (price - vwap) / vwap * 100

# =============================================================================
# DATA FETCHERS
# =============================================================================

def _yf_session():
    """A browser-impersonating session, cached.

    yfinance's plain-urllib requests get hard 429'd ('YFRateLimitError') once a
    scan grows past a few hundred symbols -- and a rate-limited fetch returns an
    EMPTY frame, which every downstream reader interprets as 'no setups' rather
    than 'the data never arrived'. curl_cffi impersonating Chrome restores
    throughput. Falls back to plain yfinance if curl_cffi is unavailable.
    """
    global _YF_SESSION
    if _YF_SESSION is not None:
        return _YF_SESSION
    try:
        from curl_cffi import requests as _cr
        _YF_SESSION = _cr.Session(impersonate="chrome")
    except Exception:
        _YF_SESSION = False
    return _YF_SESSION


_YF_SESSION = None


def fetch_yfinance_batch(symbols, period="3mo", interval="1d", chunk=200):
    """Fetch multiple symbols from yfinance, CHUNKED, with rate-limit retry.

    The universe went from ~200 curated names to ~11,000 broker-sourced ones.
    A single yf.download() of 11k tickers gets rate-limited and returns a
    mostly-empty frame -- which downstream reads as "no setups" rather than
    "the fetch failed". That is precisely the silent-coverage-loss failure
    mode this whole universe rebuild exists to prevent, so batch it, retry the
    429s, and loudly report what actually came back.
    """
    if not symbols:
        return None
    sess = _yf_session()
    kw = {"session": sess} if sess else {}
    frames, failed = [], []
    total = len(symbols)

    def _grab(part, tries=3):
        for t in range(tries):
            try:
                d = yf.download(part, period=period, interval=interval,
                                group_by="ticker", auto_adjust=True,
                                progress=False, threads=False, **kw)
                if d is not None and not d.empty:
                    return d
            except Exception as e:
                if t == tries - 1:
                    print(f"  chunk error: {e}")
            time.sleep(8 * (t + 1))
        return None

    for i in range(0, total, chunk):
        part = symbols[i:i + chunk]
        d = _grab(part)
        if d is not None:
            frames.append(d)
        else:
            failed.extend(part)
        if total > chunk:
            print(f"  fetched {min(i + chunk, total)}/{total}")
            time.sleep(2.0)

    if not frames:
        print("!! yfinance returned NOTHING for every chunk -- the fetch FAILED.")
        print("!! This is NOT an empty market. Do not trade off this run.")
        return None
    df = pd.concat(frames, axis=1) if len(frames) > 1 else frames[0]
    try:
        got = len({c[0] for c in df.columns})
        if got < total * 0.8:
            print(f"  !! COVERAGE WARNING: only {got}/{total} symbols returned "
                  f"data ({len(failed)} chunks lost to rate limiting) -- "
                  f"results are INCOMPLETE")
    except Exception:
        pass
    return df

def fetch_coingecko_crypto():
    """Fetch top crypto from CoinGecko"""
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=1&sparkline=false&price_change_percentage=24h,7d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"CoinGecko error: {e}")
        return []

def fetch_coingecko_ohlc(coin_id, days=30, retries=4):
    """Fetch OHLC from CoinGecko with 429-aware exponential backoff.

    The scan loops this over ~50 coins. With no pacing CoinGecko's free tier
    starts returning HTTP 429 after a handful of calls, which silently reduced
    the crypto universe to 4 assets (one of them a stablecoin). Back off and
    retry instead of dropping the coin.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days={days}"
    delay = 2.0
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                print(f"  429 rate-limited on {coin_id}, backing off {delay:.0f}s "
                      f"(attempt {attempt + 1}/{retries})")
                time.sleep(delay)
                delay *= 2
                continue
            print(f"CoinGecko OHLC error for {coin_id}: {e}")
            return []
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            print(f"CoinGecko OHLC error for {coin_id}: {e}")
            return []
    return []

def ohlc_to_daily(ohlc):
    """Convert hourly OHLC to daily bars"""
    days = OrderedDict()
    for t, o, h, l, c in ohlc:
        d = t // 86400000
        if d not in days:
            days[d] = [o, h, l, c]
        else:
            days[d][1] = max(days[d][1], h)
            days[d][2] = min(days[d][2], l)
            days[d][3] = c
    return list(days.values())

# =============================================================================
# MAIN SCANNER
# =============================================================================

def scan_asset_class(category_name, asset_data, df=None, prev_snapshot=None):
    """Scan a single asset class for setups"""
    results = {
        "category": asset_data["category"],
        "assets": [],
        "qualified_longs": [],
        "qualified_shorts": []
    }
    
    symbols = asset_data["symbols"]
    names = asset_data["names"]
    
    if df is not None:
        # Process yfinance batch data
        for i, (symbol, name) in enumerate(zip(symbols, names)):
            try:
                if len(symbols) > 1:
                    ticker_df = df[symbol].dropna() if symbol in df.columns.get_level_values(0) else pd.DataFrame()
                else:
                    ticker_df = df.dropna()
                
                if len(ticker_df) < 30:
                    continue
                
                closes = ticker_df["Close"].values
                highs = ticker_df["High"].values
                lows = ticker_df["Low"].values
                volumes = ticker_df["Volume"].values
                price = closes[-1]
                last_vol = volumes[-1]

                # Stale / defunct-equity guard (standing hygiene): yfinance occasionally
                # returns synthetic or flat series for delisted/halted/sub-penny names
                # (e.g. price 0.0001, RSI 100, zero volume). These pollute the scan and
                # must never reach qualification. Skip stocks that are sub-penny or show
                # no real trading on the most recent bar.
                if asset_data["category"] in STOCK_CATEGORIES:
                    if price <= 0.10:
                        print(f"  Skip {symbol}: stale/defunct equity (price {price})")
                        continue
                    if last_vol <= 0:
                        print(f"  Skip {symbol}: no volume on latest bar (stale)")
                        continue
                
                # Technical indicators
                rsi = calculate_rsi(closes)
                atr = calculate_atr(highs, lows, closes)
                ema20 = calculate_ema(closes, 20)
                ema50 = calculate_ema(closes, 50)
                ema200 = calculate_ema(closes, 200)
                vwap_data = calculate_vwap_bands(highs, lows, closes, volumes)
                vwap_dist = get_distance_from_vwap(price, vwap_data)
                
                # 24h change
                change_24h = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) > 1 else 0
                change_5d = (closes[-1] - closes[-6]) / closes[-6] * 100 if len(closes) > 5 else 0
                
                # Volume analysis
                avg_volume_20 = np.mean(volumes[-20:]) if len(volumes) >= 20 else volumes[-1]
                vol_ratio = volumes[-1] / avg_volume_20 if avg_volume_20 > 0 else 1
                avg_volume_50 = np.mean(volumes[-50:]) if len(volumes) >= 50 else np.mean(volumes)
                vol_ratio_50 = volumes[-1] / avg_volume_50 if avg_volume_50 > 0 else 1
                # Gap-up: today's open vs prior close (overnight/news gap)
                opens = ticker_df["Open"].values
                gap_up_pct = ((opens[-1] - closes[-2]) / closes[-2] * 100.0) if len(closes) > 1 else 0.0
                
                # Qualification
                asset_result = {
                    "symbol": symbol.replace("=X", "").replace("=F", ""),
                    "name": name,
                    "category": asset_data["category"],
                    "price": round(price, 5),
                    "change_24h": round(change_24h, 2),
                    "change_5d": round(change_5d, 2),
                    "rsi": round(rsi, 1),
                    "atr": round(atr, 5),
                    "ema20": round(ema20, 5),
                    "ema50": round(ema50, 5),
                    "ema200": round(ema200, 5),
                    "vwap": round(vwap_data["vwap"], 5),
                    "vwap_upper_1": round(vwap_data["upper_1"], 5),
                    "vwap_lower_1": round(vwap_data["lower_1"], 5),
                    "vwap_upper_2": round(vwap_data["upper_2"], 5),
                    "vwap_lower_2": round(vwap_data["lower_2"], 5),
                    "vwap_distance_pct": round(vwap_dist, 2),
                    "volume": int(volumes[-1]),
                    "avg_volume_20": int(avg_volume_20),
                    "vol_ratio": round(vol_ratio, 2),
                    "avg_volume_50": int(avg_volume_50),
                    "vol_ratio_50": round(vol_ratio_50, 2),
                    "gap_up_pct": round(gap_up_pct, 2),
                    "above_vwap": vwap_dist > 0,
                    "above_ema20": price > ema20,
                    "above_ema50": price > ema50,
                    "above_ema200": price > ema200,
                    "trend": "bullish" if price > ema20 > ema50 > ema200 else 
                            "bearish" if price < ema20 < ema50 < ema200 else "neutral"
                }

                results["assets"].append(asset_result)

                # Standing rule: attach last-scan reading + drift as assets populate.
                _sym_key = symbol.replace("=X", "").replace("=F", "")
                prev = (prev_snapshot or {}).get(_sym_key)
                if prev:
                    p_price = prev.get("price")
                    p_rsi = prev.get("rsi")
                    p_vwap = prev.get("vwap_distance_pct")
                    p_vol = prev.get("vol_ratio_50")
                    p_gap = prev.get("gap_up_pct")
                    asset_result["last_scan"] = {
                        "scan_timestamp": prev.get("scan_timestamp"),
                        "price": p_price, "rsi": p_rsi,
                        "vwap_distance_pct": p_vwap,
                        "vol_ratio_50": p_vol, "gap_up_pct": p_gap,
                    }
                    asset_result["price_chg_since_last"] = round(price - (p_price if p_price is not None else price), 5)
                    asset_result["price_chg_pct_since_last"] = (
                        round((price / p_price - 1) * 100, 2) if p_price else None)
                    asset_result["rsi_chg_since_last"] = round(rsi - (p_rsi if p_rsi is not None else rsi), 1)
                    asset_result["vwap_dist_chg_since_last"] = round(vwap_dist - (p_vwap if p_vwap is not None else vwap_dist), 2)
                    asset_result["vol_ratio_50_chg_since_last"] = round(vol_ratio_50 - (p_vol if p_vol is not None else vol_ratio_50), 2)
                    asset_result["gap_chg_since_last"] = round(gap_up_pct - (p_gap if p_gap is not None else gap_up_pct), 2)
                    asset_result["is_new_since_last"] = False
                else:
                    asset_result["last_scan"] = None
                    asset_result["price_chg_since_last"] = None
                    asset_result["price_chg_pct_since_last"] = None
                    asset_result["rsi_chg_since_last"] = None
                    asset_result["vwap_dist_chg_since_last"] = None
                    asset_result["vol_ratio_50_chg_since_last"] = None
                    asset_result["gap_chg_since_last"] = None
                    asset_result["is_new_since_last"] = True
                
                # Stock hard-gate (standing rule): equities need a real liquidity
                # event — >= VOL_RATIO_FLOOR x relative volume vs 50d avg, and
                # longs must be gapping up. No price/market-cap floor.
                is_stock = asset_data["category"] in STOCK_CATEGORIES
                vol_ok_stock = (not is_stock) or (vol_ratio_50 >= VOL_RATIO_FLOOR)
                gap_ok_long = (not is_stock) or (gap_up_pct >= GAP_UP_MIN_PCT)

                # LONG qualification
                long_score = 0
                long_reasons = []
                
                if rsi < 35:
                    long_score += 0.3
                    long_reasons.append(f"RSI oversold ({rsi:.1f})")
                elif rsi < 45:
                    long_score += 0.15
                    long_reasons.append(f"RSI low ({rsi:.1f})")
                
                if vwap_dist < -0.5:
                    long_score += 0.25
                    long_reasons.append(f"Below VWAP ({vwap_dist:.2f}%)")
                elif vwap_dist < 0.5:
                    long_score += 0.15
                    long_reasons.append(f"At VWAP ({vwap_dist:.2f}%)")
                
                if price > ema20 and price < ema20 * 1.02:
                    long_score += 0.2
                    long_reasons.append("Reclaiming EMA20")
                elif price > ema20:
                    long_score += 0.1
                    long_reasons.append("Above EMA20")
                
                if vol_ratio > 1.2:
                    long_score += 0.15
                    long_reasons.append(f"High volume ({vol_ratio:.1f}x)")
                if is_stock:
                    long_reasons.append(
                        f"Stock liquidity event: {vol_ratio_50:.1f}x 50d vol, gap {gap_up_pct:+.1f}%"
                    )
                
                if price > ema200:
                    long_score += 0.1
                    long_reasons.append("Above EMA200 (uptrend)")
                
                # Check R:R with ATR-based stop
                stop_dist = max(price * 0.02, 1.5 * atr)
                target_dist = 2.5 * stop_dist
                rr = target_dist / stop_dist if stop_dist > 0 else 0
                
                if rr >= 2.0 and long_score >= 0.5 and atr > 0 and vol_ok_stock and gap_ok_long:
                    asset_result["long_score"] = round(long_score, 2)
                    asset_result["long_reasons"] = long_reasons
                    asset_result["stop_loss"] = round(price - stop_dist, 5)
                    asset_result["take_profit_1"] = round(price + target_dist, 5)
                    asset_result["take_profit_2"] = round(price + 3.5 * stop_dist, 5)
                    asset_result["rr"] = round(rr, 2)
                    asset_result["stop_atr_mult"] = round(stop_dist / atr, 2) if atr > 0 else 0
                    results["qualified_longs"].append(asset_result)
                
                # SHORT qualification
                short_score = 0
                short_reasons = []
                
                if rsi > 65:
                    short_score += 0.3
                    short_reasons.append(f"RSI overbought ({rsi:.1f})")
                elif rsi > 55:
                    short_score += 0.15
                    short_reasons.append(f"RSI high ({rsi:.1f})")
                
                if vwap_dist > 0.5:
                    short_score += 0.25
                    short_reasons.append(f"Above VWAP ({vwap_dist:.2f}%)")
                elif vwap_dist > -0.5:
                    short_score += 0.15
                    short_reasons.append(f"At VWAP ({vwap_dist:.2f}%)")
                
                if price < ema20 and price > ema20 * 0.98:
                    short_score += 0.2
                    short_reasons.append("Rejecting EMA20")
                elif price < ema20:
                    short_score += 0.1
                    short_reasons.append("Below EMA20")
                
                if vol_ratio > 1.2:
                    short_score += 0.15
                    short_reasons.append(f"High volume ({vol_ratio:.1f}x)")
                if is_stock:
                    short_reasons.append(
                        f"Stock liquidity event: {vol_ratio_50:.1f}x 50d vol, gap {gap_up_pct:+.1f}%"
                    )
                
                if price < ema200:
                    short_score += 0.1
                    short_reasons.append("Below EMA200 (downtrend)")
                
                # Check R:R for short
                stop_dist_s = max(price * 0.02, 1.5 * atr)
                target_dist_s = 2.5 * stop_dist_s
                rr_s = target_dist_s / stop_dist_s if stop_dist_s > 0 else 0
                
                if rr_s >= 2.0 and short_score >= 0.5 and atr > 0 and vol_ok_stock:
                    asset_result["short_score"] = round(short_score, 2)
                    asset_result["short_reasons"] = short_reasons
                    asset_result["stop_loss_short"] = round(price + stop_dist_s, 5)
                    asset_result["take_profit_1_short"] = round(price - target_dist_s, 5)
                    asset_result["take_profit_2_short"] = round(price - 3.5 * stop_dist_s, 5)
                    asset_result["rr_short"] = round(rr_s, 2)
                    asset_result["stop_atr_mult_short"] = round(stop_dist_s / atr, 2) if atr > 0 else 0
                    results["qualified_shorts"].append(asset_result)
                    
            except Exception as e:
                print(f"Error processing {symbol}: {e}")
                continue
    
    return results

def scan_crypto():
    """Scan cryptocurrency from CoinGecko"""
    print("Fetching crypto data from CoinGecko...")
    crypto_data = fetch_coingecko_crypto()
    if not crypto_data:
        return {"category": "crypto", "assets": [], "qualified_longs": [], "qualified_shorts": []}
    
    results = {"category": "crypto", "assets": [], "qualified_longs": [], "qualified_shorts": []}

    # Stablecoins cannot produce a directional setup — they only consume
    # rate-limit budget and pad the asset count.
    STABLECOINS = {"USDT", "USDC", "DAI", "BUSD", "TUSD", "USDE", "FDUSD",
                   "PYUSD", "USDS", "USDD", "LUSD", "GUSD", "FRAX"}

    for coin in crypto_data:
        try:
            symbol = coin["symbol"].upper()
            if symbol in STABLECOINS:
                continue
            name = coin["name"]
            price = coin["current_price"]
            change_24h = coin.get("price_change_percentage_24h", 0)
            change_7d = coin.get("price_change_percentage_7d", 0)
            volume = coin.get("total_volume", 0)
            mcap = coin.get("market_cap", 0)
            coin_id = coin["id"]

            # Pace requests — CoinGecko's free tier 429s without this.
            time.sleep(1.5)

            # Fetch OHLC for technical indicators
            ohlc = fetch_coingecko_ohlc(coin_id, days=30)
            if not ohlc or len(ohlc) < 15:
                continue
            
            daily = ohlc_to_daily(ohlc)
            if len(daily) < 15:
                continue
            
            closes = np.array([d[3] for d in daily])
            highs = np.array([d[1] for d in daily])
            lows = np.array([d[2] for d in daily])
            # Volume not available in CoinGecko OHLC, use market data
            volumes = np.full(len(daily), volume / len(daily)) if volume > 0 else np.ones(len(daily))
            
            # Technical indicators
            rsi = calculate_rsi(closes)
            atr = calculate_atr(highs, lows, closes)
            ema20 = calculate_ema(closes, 20)
            ema50 = calculate_ema(closes, 50)
            ema200 = calculate_ema(closes, 200)
            vwap_data = calculate_vwap_bands(highs, lows, closes, volumes)
            vwap_dist = get_distance_from_vwap(price, vwap_data)
            
            # Volume ratio (approximate)
            vol_ratio = 1.0
            
            asset_result = {
                "symbol": symbol,
                "name": name,
                "category": "crypto",
                "price": round(price, 6),
                "change_24h": round(change_24h, 2),
                "change_7d": round(change_7d, 2),
                "rsi": round(rsi, 1),
                "atr": round(atr, 6),
                "ema20": round(ema20, 6),
                "ema50": round(ema50, 6),
                "ema200": round(ema200, 6),
                "vwap": round(vwap_data["vwap"], 6),
                "vwap_upper_1": round(vwap_data["upper_1"], 6),
                "vwap_lower_1": round(vwap_data["lower_1"], 6),
                "vwap_upper_2": round(vwap_data["upper_2"], 6),
                "vwap_lower_2": round(vwap_data["lower_2"], 6),
                "vwap_distance_pct": round(vwap_dist, 2),
                "volume": int(volume),
                "market_cap": int(mcap),
                "vol_ratio": round(vol_ratio, 2),
                "above_vwap": vwap_dist > 0,
                "above_ema20": price > ema20,
                "above_ema50": price > ema50,
                "above_ema200": price > ema200,
                "trend": "bullish" if price > ema20 > ema50 > ema200 else 
                        "bearish" if price < ema20 < ema50 < ema200 else "neutral"
            }
            
            results["assets"].append(asset_result)
            
            # LONG qualification (same logic as other assets)
            long_score = 0
            long_reasons = []
            
            if rsi < 35:
                long_score += 0.3
                long_reasons.append(f"RSI oversold ({rsi:.1f})")
            elif rsi < 45:
                long_score += 0.15
                long_reasons.append(f"RSI low ({rsi:.1f})")
            
            if vwap_dist < -0.5:
                long_score += 0.25
                long_reasons.append(f"Below VWAP ({vwap_dist:.2f}%)")
            elif vwap_dist < 0.5:
                long_score += 0.15
                long_reasons.append(f"At VWAP ({vwap_dist:.2f}%)")
            
            if price > ema20 and price < ema20 * 1.02:
                long_score += 0.2
                long_reasons.append("Reclaiming EMA20")
            elif price > ema20:
                long_score += 0.1
                long_reasons.append("Above EMA20")
            
            if vol_ratio > 1.2:
                long_score += 0.15
                long_reasons.append(f"High volume ({vol_ratio:.1f}x)")
            
            if price > ema200:
                long_score += 0.1
                long_reasons.append("Above EMA200 (uptrend)")
            
            stop_dist = max(price * 0.02, 1.5 * atr)
            target_dist = 2.5 * stop_dist
            rr = target_dist / stop_dist if stop_dist > 0 else 0
            
            if rr >= 2.0 and long_score >= 0.5 and atr > 0:
                asset_result["long_score"] = round(long_score, 2)
                asset_result["long_reasons"] = long_reasons
                asset_result["stop_loss"] = round(price - stop_dist, 6)
                asset_result["take_profit_1"] = round(price + target_dist, 6)
                asset_result["take_profit_2"] = round(price + 3.5 * stop_dist, 6)
                asset_result["rr"] = round(rr, 2)
                asset_result["stop_atr_mult"] = round(stop_dist / atr, 2) if atr > 0 else 0
                results["qualified_longs"].append(asset_result)
            
            # SHORT qualification
            short_score = 0
            short_reasons = []
            
            if rsi > 65:
                short_score += 0.3
                short_reasons.append(f"RSI overbought ({rsi:.1f})")
            elif rsi > 55:
                short_score += 0.15
                short_reasons.append(f"RSI high ({rsi:.1f})")
            
            if vwap_dist > 0.5:
                short_score += 0.25
                short_reasons.append(f"Above VWAP ({vwap_dist:.2f}%)")
            elif vwap_dist > -0.5:
                short_score += 0.15
                short_reasons.append(f"At VWAP ({vwap_dist:.2f}%)")
            
            if price < ema20 and price > ema20 * 0.98:
                short_score += 0.2
                short_reasons.append("Rejecting EMA20")
            elif price < ema20:
                short_score += 0.1
                short_reasons.append("Below EMA20")
            
            if vol_ratio > 1.2:
                short_score += 0.15
                short_reasons.append(f"High volume ({vol_ratio:.1f}x)")
            
            if price < ema200:
                short_score += 0.1
                short_reasons.append("Below EMA200 (downtrend)")
            
            stop_dist_s = max(price * 0.02, 1.5 * atr)
            target_dist_s = 2.5 * stop_dist_s
            rr_s = target_dist_s / stop_dist_s if stop_dist_s > 0 else 0
            
            if rr_s >= 2.0 and short_score >= 0.5 and atr > 0:
                asset_result["short_score"] = round(short_score, 2)
                asset_result["short_reasons"] = short_reasons
                asset_result["stop_loss_short"] = round(price + stop_dist_s, 6)
                asset_result["take_profit_1_short"] = round(price - target_dist_s, 6)
                asset_result["take_profit_2_short"] = round(price - 3.5 * stop_dist_s, 6)
                asset_result["rr_short"] = round(rr_s, 2)
                asset_result["stop_atr_mult_short"] = round(stop_dist_s / atr, 2) if atr > 0 else 0
                results["qualified_shorts"].append(asset_result)
                
        except Exception as e:
            print(f"Error processing crypto {coin.get('id', 'unknown')}: {e}")
            continue
    
    return results

def apply_sentiment_conviction(longs, shorts, sentiment_path):
    """Fold a FRESH sentiment reading into each candidate's conviction (by-law).

    lean = composite sign: FEAR/negative -> agrees with LONG (oversold fade),
    GREED/positive -> agrees with SHORT. A setup whose direction AGREES with the
    fresh lean gets a conviction boost (+0.15); one that DISAGREES gets a penalty
    (-0.15). The raw score (pre-sentiment) is preserved as `base_score` so the
    adjustment is auditable.

    Low coverage (<60%): we only FLAG `low_sentiment_coverage` and do NOT adjust
    conviction (never size off a thin reading). Missing file: no-op + flag.
    """
    rec = None
    if sentiment_path and Path(sentiment_path).exists():
        try:
            rec = json.loads(Path(sentiment_path).read_text(encoding="utf-8"))
        except Exception:
            rec = None
    if not rec:
        for t in longs + shorts:
            t.setdefault("sentiment_conviction", "NO-FRESH-READING")
        return

    lean = rec.get("lean", "NEUTRAL")
    composite = rec.get("composite", 0.0)
    confidence_ok = rec.get("confidence_ok", False)
    # magnitude of the lean drives how hard we weight it (cap at 0.15)
    mag = min(abs(composite), 1.0) * 0.15
    low_cov = not confidence_ok

    def adjust(trade, side):
        base = trade.get("long_score" if side == "LONG" else "short_score", 0.0) or 0.0
        trade["base_score"] = round(base, 2)
        if low_cov:
            trade["sentiment_conviction"] = "LOW-COVERAGE-FLAG"
            return  # do not fabricate conviction off thin data
        agrees = (side == "LONG" and lean in ("LONG", "NEUTRAL")) or \
                 (side == "SHORT" and lean in ("SHORT", "NEUTRAL"))
        # NEUTRAL lean gives a small boost to both (no disagreement)
        delta = mag if (agrees or lean == "NEUTRAL") else -mag
        if lean == "NEUTRAL":
            delta = mag * 0.4
        new = round(max(0.0, min(1.0, base + delta)), 2)
        key = "long_score" if side == "LONG" else "short_score"
        trade[key] = new
        trade["sentiment_conviction"] = f"{lean} lean, {'+' if delta>=0 else ''}{delta:.2f} -> {new}"

    for t in longs:
        adjust(t, "LONG")
    for t in shorts:
        adjust(t, "SHORT")


def convert_to_serializable(obj):
    """Convert numpy types to Python native types for JSON serialization"""
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_to_serializable(val) for key, val in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    return obj

def main():
    print("=" * 80)
    print("UNIVERSAL PREMARKET SCANNER - ALL ASSET CLASSES")
    print(f"Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 80)
    
    all_results = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "categories": {}
    }
    
    # Standing rule: remember the last scan and reuse it when assets populate.
    last_snap = load_last_scan_snapshot()
    prev_snapshot = (last_snap or {}).get("symbols", {})
    if last_snap:
        print(f"Last-scan memory: {len(prev_snapshot)} symbols from {last_snap.get('scan_timestamp')}")
    else:
        print("No last-scan memory found — establishing baseline.")
    
    # Collect all yfinance symbols
    all_yf_symbols = []
    symbol_to_category = {}
    symbol_to_name = {}
    
    for cat_name, cat_data in ASSET_UNIVERSE.items():
        for sym, name in zip(cat_data["symbols"], cat_data["names"]):
            all_yf_symbols.append(sym)
            symbol_to_category[sym] = cat_name
            symbol_to_name[sym] = name

    # --- FULL-SECTOR EXPANSION -------------------------------------------
    # The hardcoded ASSET_UNIVERSE above is a curated core, NOT the sector.
    # Merge in the broker-sourced, yfinance-validated universe so a scan of a
    # sector actually covers every asset our venues list, not ~40 favourites.
    _res = _load_resolved()
    for _sec, _cat in (("US_EQUITY", "US_EQUITY_FULL"),
                       ("ETF", "ETF_FULL"),
                       ("FX", "FX_FULL"),
                       ("COMMODITIES", "COMMODITIES_FULL"),
                       ("INDICES", "INDICES_FULL")):
        _syms = [s for s in _res.get(_sec, {}).get("symbols", [])
                 if s not in symbol_to_category]
        if not _syms:
            continue
        ASSET_UNIVERSE[_cat] = {
            "symbols": _syms,
            "names": _syms,
            "category": _sec.lower(),
        }
        for s in _syms:
            all_yf_symbols.append(s)
            symbol_to_category[s] = _cat
            symbol_to_name[s] = s
        print(f"  [universe] +{len(_syms)} {_sec} assets from resolved universe")

    print(f"\nFetching {len(all_yf_symbols)} symbols from yfinance...")
    df = fetch_yfinance_batch(all_yf_symbols, period="1y", interval="1d")
    
    if df is None:
        print("Failed to fetch yfinance data")
        return
    
    # Process each asset class
    for cat_name, cat_data in ASSET_UNIVERSE.items():
        print(f"\nScanning {cat_name} ({cat_data['category']})...")
        cat_results = scan_asset_class(cat_name, cat_data, df, prev_snapshot=prev_snapshot)
        all_results["categories"][cat_name] = cat_results
        print(f"  Assets scanned: {len(cat_results['assets'])}")
        print(f"  Qualified LONGs: {len(cat_results['qualified_longs'])}")
        print(f"  Qualified SHORTs: {len(cat_results['qualified_shorts'])}")
    
    # Scan crypto — routed through the standard yfinance path (see
    # CRYPTO_YF_SYMBOLS). The old CoinGecko scan_crypto() is retained below but
    # no longer called; its free-tier rate limit truncated the universe to 4.
    print(f"\nScanning CRYPTO...")
    _crypto_syms = _resolved_crypto()
    print(f"  [universe] crypto universe = {len(_crypto_syms)} assets")
    crypto_cat = {
        "symbols": _crypto_syms,
        "names": [s.replace("-USD", "").replace("7083", "").replace("20947", "")
                  for s in _crypto_syms],
        "category": "crypto",
    }
    crypto_df = fetch_yfinance_batch(_crypto_syms, period="1y", interval="1d")
    crypto_results = scan_asset_class("CRYPTO", crypto_cat, crypto_df, prev_snapshot=prev_snapshot)
    all_results["categories"]["CRYPTO"] = crypto_results
    print(f"  Assets scanned: {len(crypto_results['assets'])}")
    print(f"  Qualified LONGs: {len(crypto_results['qualified_longs'])}")
    print(f"  Qualified SHORTs: {len(crypto_results['qualified_shorts'])}")
    
    # Collect all qualified trades
    all_longs = []
    all_shorts = []
    
    for cat_name, cat_results in all_results["categories"].items():
        for trade in cat_results["qualified_longs"]:
            trade["asset_class"] = cat_results["category"]
            all_longs.append(trade)
        for trade in cat_results["qualified_shorts"]:
            trade["asset_class"] = cat_results["category"]
            all_shorts.append(trade)
    
    # Sort by score
    all_longs.sort(key=lambda x: x.get("long_score", 0), reverse=True)
    all_shorts.sort(key=lambda x: x.get("short_score", 0), reverse=True)

    # ---- fresh-sentiment -> conviction (by-law) ----------------------------
    # A long setup is CONFIRMED by fearful/bearish tape only if we are fading it
    # (mean-reversion into oversold); here the scanner already surfaces
    # oversold-longs, so a FEAR lean AGREES with a long (capitulation bottom) and
    # is boosted, while GREED agrees with a short. If coverage is too low we only
    # FLAG, never fabricate conviction. Adjusts the stored directional score so
    # the gate's conviction_tier inherits it.
    apply_sentiment_conviction(all_longs, all_shorts, HOME / "sentiment_latest.json")
    
    all_results["qualified_longs"] = all_longs[:50]
    all_results["qualified_shorts"] = all_shorts[:50]
    all_results["total_assets_scanned"] = sum(len(c["assets"]) for c in all_results["categories"].values())
    all_results["total_qualified_longs"] = len(all_longs)
    all_results["total_qualified_shorts"] = len(all_shorts)
    
    # Convert numpy types for JSON serialization
    all_results = convert_to_serializable(all_results)
    
    # Save results
    output_file = f"universal_scan_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Also save as latest
    with open("universal_scan_results_latest.json", "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Persist this scan as the new "last scan" so the next run can compare.
    save_last_scan_snapshot(all_results)
    
    print(f"\n{'='*80}")
    print(f"SCAN COMPLETE")
    print(f"{'='*80}")
    print(f"Total assets scanned: {all_results['total_assets_scanned']}")
    print(f"Total qualified LONGs: {all_results['total_qualified_longs']}")
    print(f"Total qualified SHORTs: {all_results['total_qualified_shorts']}")
    print(f"Results saved to: {output_file}")
    print(f"Results saved to: universal_scan_results_latest.json")
    
    # Print top setups
    print(f"\n{'='*80}")
    print("TOP 10 LONG SETUPS")
    print(f"{'='*80}")
    print(f"{'#':>3} {'SYMBOL':>10} {'NAME':<25} {'CAT':<12} {'PRICE':>10} {'RSI':>5} {'VWAP%':>7} {'SCORE':>5} {'SL':>10} {'TP1':>10} {'RR':>4}")
    print("-" * 110)
    for i, trade in enumerate(all_longs[:10], 1):
        print(f"{i:>3} {trade['symbol']:>10} {trade['name']:<25} {trade['asset_class']:<12} "
              f"${trade['price']:>9.4f} {trade['rsi']:>5.1f} {trade['vwap_distance_pct']:>+6.2f}% "
              f"{trade['long_score']:>5.2f} ${trade['stop_loss']:>9.4f} ${trade['take_profit_1']:>9.4f} {trade['rr']:>4.2f}")
    
    print(f"\n{'='*80}")
    print("TOP 10 SHORT SETUPS")
    print(f"{'='*80}")
    print(f"{'#':>3} {'SYMBOL':>10} {'NAME':<25} {'CAT':<12} {'PRICE':>10} {'RSI':>5} {'VWAP%':>7} {'SCORE':>5} {'SL':>10} {'TP1':>10} {'RR':>4}")
    print("-" * 110)
    for i, trade in enumerate(all_shorts[:10], 1):
        print(f"{i:>3} {trade['symbol']:>10} {trade['name']:<25} {trade['asset_class']:<12} "
              f"${trade['price']:>9.4f} {trade['rsi']:>5.1f} {trade['vwap_distance_pct']:>+6.2f}% "
              f"{trade['short_score']:>5.2f} ${trade['stop_loss_short']:>9.4f} ${trade['take_profit_1_short']:>9.4f} {trade['rr_short']:>4.2f}")

if __name__ == "__main__":
    main()