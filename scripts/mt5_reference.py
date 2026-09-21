#!/usr/bin/env python3
"""Quick MT5 Symbol Reference — All 232 symbols categorized."""
import json

# Load the full index
with open('C:/Hermes/workflow/data/mt5_symbols_index.json', 'r') as f:
    index = json.load(f)

# Create a flat lookup: scan_symbol -> MT5_name
SCAN_TO_MT5 = {
    # Crypto
    "BTC-USD": "BTCUSD",
    "ETH-USD": "ETHUSD",
    "SOL-USD": "SOLUSD",
    "BNB-USD": "BNBUSD",
    "XRP-USD": "XRPUSD",
    "ADA-USD": "ADAUSD",
    "DOGE-USD": "DOGEUSD",
    "AVAX-USD": "AVAXUSD",
    "LINK-USD": "LINKUSD",
    "DOT-USD": "DOTUSD",
    "LTC-USD": "LTCUSD",
    # Metals
    "GC=F": "XAUUSD",
    "SI=F": "XAGUSD",
    "PL=F": "XPTUSD",
    "PA=F": "XPDUSD",
    # Energy
    "NG=F": "NATGAS",
    # Indices
    "^GSPC": "US500",
    "^IXIC": "US100",
    "^DJI": "US30",
    "^FTSE": "UK100",
    "^N225": "JP225",
    # Forex
    "EURUSD=X": "EURUSD",
    "GBPUSD=X": "GBPUSD",
    "USDJPY=X": "USDJPY",
    "AUDUSD=X": "AUDUSD",
    "USDCAD=X": "USDCAD",
    "USDCHF=X": "USDCHF",
    "NZDUSD=X": "NZDUSD",
    # Stocks (available on MT5)
    "AAPL": "AAPL",
    "AMZN": "AMZN",
    "GOOGL": "GOOGL",
    "MSFT": "MSFT",
    "PLTR": "PLTR",
    "COIN": "COIN",
    "HOOD": "HOOD",
    "AMD": "AMD",
    "AVGO": "AVGO",
    "INTC": "INTC",
    "TSLA": "TSLA",
    "META": "META",
    "NVDA": "NVDA",
    "MA": "MA",
    "V": "V",
    "KO": "KO",
    "PEP": "PEP",
    "ABBV": "ABBV",
    "PFE": "PFE",
    "JPM": "JPM",
    "BAC": "BAC",
}

# Reverse lookup: MT5_name -> scan_symbol
MT5_TO_SCAN = {v: k for k, v in SCAN_TO_MT5.items()}

# All MT5 symbols by category
MT5_CATEGORIES = {
    "crypto": ["BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD", "XRPUSD", "ADAUSD", 
               "DOGEUSD", "AVAXUSD", "LINKUSD", "DOTUSD", "LTCUSD", "BTCEUR", "ETHEUR", "XRPEUR"],
    "indices": ["US500", "US100", "US30", "UK100", "JP225", "AU200", "VIX"],
    "metals": ["XAUUSD", "XAGUSD", "XPDUSD", "XPTUSD"],
    "energy": ["GASOIL", "HOIL", "NATGAS"],
    "forex": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
              "EURGBP", "EURAUD", "EURCHF", "EURJPY", "EURCAD", "EURNZD",
              "GBPCHF", "GBPJPY", "AUDNZD", "AUDCAD", "AUDCHF", "AUDJPY",
              "CADCHF", "CHFJPY", "NZDJPY"],
    "stocks": ["AAPL", "AMD", "AMZN", "ARM", "AVGO", "BA", "BABA", "CLSK", "COIN",
               "DJT", "GME", "GOOG", "GOOGL", "INTC", "IONQ", "MARA", "META",
               "MSFT", "NVDA", "PLTR", "HOOD", "TSLA", "MA", "V", "KO", "PEP",
               "ABBV", "PFE", "JPM", "BAC", "NFLX", "CRM", "ORCL", "ADBE",
               "CSCO", "QCOM", "TXN", "IBM", "GE", "CAT", "BA", "UPS", "NEE",
               "LIN", "MDT", "TMO", "ABT", "DHR", "BMY", "AMGN", "GILD",
               "RTX", "LMT", "NOC", "GD", "HII", "KTOS", "AXON", "LPX", "APTV", "GNRC", "MRCY", "CW", "TGI", "AYI", "CARR", "NDSN", "WTS", "ST", "WWD", "ESLT", "BDC", "APTV", "OEC", "ENS", "CBAT", "MYRG", "ROG", "COHR", "IIVI", "VIAV", "LFUS", "NXPI", "MPWR", "SWKS", "QRVO", "RMBS", "POWL", "MTSI", "DIOD", "FCS", "DORM", "WIRE", "AVDX", "PLXS", "SGH", "TTMI", "BHE", "KE", "SANM", "ROG", "COHR", "IIVI", "VIAV", "LFUS", "NXPI", "MPWR", "SWKS", "QRVO", "RMBS", "POWL", "MTSI", "DIOD", "FCS", "DORM", "WIRE", "AVDX", "PLXS", "SGH", "TTMI", "BHE", "KE", "SANM"],
}

def scan_to_mt5(scan_symbol):
    """Convert scan symbol to MT5 name."""
    return SCAN_TO_MT5.get(scan_symbol, None)

def mt5_to_scan(mt5_name):
    """Convert MT5 name to scan symbol."""
    return MT5_TO_SCAN.get(mt5_name, None)

def is_mt5_available(scan_symbol):
    """Check if a symbol is available on MT5."""
    return scan_symbol in SCAN_TO_MT5

def get_mt5_symbols(category=None):
    """Get all MT5 symbols by category."""
    if category:
        return MT5_CATEGORIES.get(category, [])
    return [s for cat in MT5_CATEGORIES.values() for s in cat]

if __name__ == "__main__":
    print(f"Total MT5 symbols: {len(SCAN_TO_MT5)} mapped, {sum(len(v) for v in MT5_CATEGORIES.values())} total")
    print(f"\nCategories:")
    for cat, items in MT5_CATEGORIES.items():
        print(f"  {cat:<15} {len(items):>3} symbols")
