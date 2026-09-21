#!/usr/bin/env python3
"""BULLISH SETUP SCANNER — runs gate pipeline on comprehensive universe."""
import json, pathlib, sys, time
from datetime import datetime, timezone

HOME = pathlib.Path.home()
UNIVERSE_FILE = pathlib.Path(r"C:\Hermes\workflow\data\universe_comprehensive.json")
BARS_DIR = pathlib.Path(r"C:\Hermes\workflow\data")

# Import the gate
sys.path.insert(0, str(HOME))
sys.path.insert(0, r"C:\Hermes\workflow\scripts")

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_ema(closes, period):
    if len(closes) < period:
        return closes[-1] if closes else 0
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for c in closes[period:]:
        ema = c * k + ema * (1 - k)
    return ema

def calc_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return 0
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    if not trs:
        return 0
    atr = sum(trs[:period]) / period
    for t in trs[period:]:
        atr = (atr * (period - 1) + t) / period
    return atr

def calc_vwap(highs, lows, closes, volumes, period=20):
    """Calculate VWAP (Volume Weighted Average Price)."""
    if len(closes) < period or len(volumes) < period:
        return None
    typical = [(h + l + c) / 3 for h, l, c in zip(highs[-period:], lows[-period:], closes[-period:])]
    vol = volumes[-period:]
    vwap = sum(t * v for t, v in zip(typical, vol)) / sum(vol) if sum(vol) > 0 else 0
    return round(vwap, 4)

def check_ema_stack(closes):
    """Check full EMA stack alignment (institutional pattern)."""
    if len(closes) < 200:
        return 0, ""
    
    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    sma50 = sum(closes[-50:]) / 50
    sma200 = sum(closes[-200:]) / 200
    price = closes[-1]
    
    score = 0
    label = ""
    
    # Full EMA stack: price > EMA9 > EMA21 > SMA50 > SMA200
    if price > ema9 > ema21 > sma50 > sma200:
        score = 4
        label = "FULL_EMA_STACK"
    elif price > ema21 > sma50:
        score = 2
        label = "PARTIAL_STACK"
    elif price < ema21 and ema21 < sma50:
        score = -2
        label = "BEARISH_STACK"
    
    return score, label

def detect_golden_cross(closes):
    """Detect SMA50/SMA200 golden cross within last 15 bars."""
    if len(closes) < 215:
        return False, ""
    
    sma50_now = sum(closes[-50:]) / 50
    sma200_now = sum(closes[-200:]) / 200
    sma50_prev = sum(closes[-65:-15]) / 50
    sma200_prev = sum(closes[-215:-15]) / 200
    
    if sma50_now > sma200_now and sma50_prev < sma200_prev:
        return True, "GOLDEN_CROSS"
    return False, ""

def fetch_bars_yf(symbol, period="1y"):
    """Fetch OHLCV bars for an asset (1y for indicator accuracy)."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        df = t.history(period=period, interval="1d")
        if df.empty:
            return None
        return {
            "closes": df["Close"].tolist(),
            "highs": df["High"].tolist(),
            "lows": df["Low"].tolist(),
            "volumes": df["Volume"].tolist(),
        }
    except Exception:
        return None

def scan_asset(symbol, price, change_pct):
    """Scan a single asset for bullish setup with institutional indicators."""
    bars = fetch_bars_yf(symbol)
    if not bars or len(bars["closes"]) < 30:
        return None
    
    closes = bars["closes"]
    highs = bars["highs"]
    lows = bars["lows"]
    volumes = bars["volumes"]
    
    rsi = calc_rsi(closes)
    ema20 = calc_ema(closes, 20)
    ema50 = calc_ema(closes, 50)
    ema200 = calc_ema(closes, 200) if len(closes) >= 200 else None
    atr = calc_atr(highs, lows, closes)
    
    # VWAP (institutional)
    vwap20 = calc_vwap(highs, lows, closes, volumes, period=20)
    
    # EMA stack check
    ema_stack_score, ema_stack_label = check_ema_stack(closes)
    
    # Golden cross
    has_golden_cross, golden_label = detect_golden_cross(closes)
    
    # Volume ratio
    avg_vol_20 = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else volumes[-1] if volumes else 0
    vol_ratio = volumes[-1] / avg_vol_20 if avg_vol_20 > 0 else 1
    
    # Bullish conditions
    signals = []
    score = 0
    
    # Price above EMAs
    if price > ema20:
        signals.append("Above EMA20")
        score += 1
    if price > ema50:
        signals.append("Above EMA50")
        score += 1
    if ema200 and price > ema200:
        signals.append("Above EMA200")
        score += 1
    
    # RSI conditions
    if 30 <= rsi <= 50:
        signals.append(f"RSI={rsi:.0f} (oversold bounce)")
        score += 2
    elif 50 < rsi <= 65:
        signals.append(f"RSI={rsi:.0f} (bullish)")
        score += 1
    elif rsi > 70:
        signals.append(f"RSI={rsi:.0f} (overbought)")
        score -= 1
    
    # Volume
    if vol_ratio > 1.5:
        signals.append(f"Vol spike {vol_ratio:.1f}x")
        score += 1
    
    # Price action
    if len(closes) >= 3 and closes[-1] > closes[-2] > closes[-3]:
        signals.append("3-day uptrend")
        score += 1
    
    # VWAP confirmation
    if vwap20 and price > vwap20:
        signals.append(f"Above VWAP20 (${vwap20:.2f})")
        score += 1
    
    # EMA stack bonus
    if ema_stack_score > 0:
        signals.append(f"EMA Stack: {ema_stack_label}")
        score += ema_stack_score
    
    # Golden cross bonus
    if has_golden_cross:
        signals.append(golden_label)
        score += 3
    
    if score < 3:
        return None
    
    # Calculate entry/SL/TP
    sl = price - (atr * 1.5)
    tp1 = price + (atr * 1.5 * 1.5)
    tp2 = price + (atr * 1.5 * 2.5)
    rr = (tp1 - price) / (price - sl) if (price - sl) > 0 else 0
    
    return {
        "symbol": symbol,
        "price": price,
        "change_pct": change_pct,
        "rsi": round(rsi, 1),
        "atr": round(atr, 4),
        "ema20": round(ema20, 4),
        "ema50": round(ema50, 4),
        "ema200": round(ema200, 4) if ema200 else None,
        "vwap20": vwap20,
        "ema_stack": ema_stack_label,
        "golden_cross": has_golden_cross,
        "vol_ratio": round(vol_ratio, 2),
        "score": score,
        "signals": signals,
        "entry": round(price, 4),
        "stop_loss": round(sl, 4),
        "tp1": round(tp1, 4),
        "tp2": round(tp2, 4),
        "rr": round(rr, 2),
    }

def categorize(symbol):
    s = symbol.replace("-USD", "").replace("-USD=F", "").replace("=X", "").replace("=F", "")
def categorize(symbol):
    s = symbol.replace("-USD", "").replace("-USD=F", "").replace("=X", "").replace("=F", "")
    if s in ["EUR","GBP","USD","JPY","CHF","AUD","CAD","NZD","MXN","ZAR","BRL","CNY","KRW","INR","RUB","TRY","SEK","NOK","DKK","HKD","SGD","TWD","THB","PHP","MYR","IDR","HUF","PLN","CZK","ILS","AED","SAR"]:
        return "FX"
    if s in ["GC","SI","PL","PA","HG","GLD","SLV","SIVR","PPLT","PALL"]:
        return "METALS"
    if s in ["CL","BZ","NG","RB","HO","USO","UNG","XLE","OIH","TAN","FAN","PBW","QCLN","SMOG","ICLN"]:
        return "ENERGY"
    if s in ["ZC","ZW","ZS","KC","SB","CT","CC","LE","OJ","LBS","ZR","ZM","ZL","ZO","GF","HE","KE"]:
        return "AGRICULTURE"
    if s in ["BTC","ETH","SOL","BNB","XRP","ADA","DOGE","AVAX","LINK","MATIC","DOT","LTC","UNI","ATOM","ETC","XLM","ALGO","FIL","HBAR","ICP","APT","SUI","ARB","OP","NEAR","INJ","TIA","SEI","PYTH","WIF","BONK","PEPE","SHIB","TON","WLD","STX","IMX","RNDR","GRT","THETA","AXS","SAND","MANA","ENJ","GALA","FLOW","XTZ","EOS","AAVE","MKR","COMP","CRV","1INCH","DYDX","SNX","PERP","GMX","ZEC","DASH","XMR","RVN","BEAM","ZEN","KMD","BTG","BSV","BCH","XEC","FLUX","CKB","CFX","GLMR","MOVR","ROSE","ASTR","SDN","ACA"]:
        return "CRYPTO"
    if s in ["TNX","TYX","IRX","FVX","VIX","VIX3M","VIX6M","VVIX","MOVE","CL1","CL2","CL3","CL6","CL12"]:
        return "RATES"
    if s.startswith("^") or s in ["GSPC","DJI","IXIC","RUT","W5000","SP400","SP600","SPX","SP100","NDX","RUI","RUA","SKEW","STOXX50E","FTSE","GDAXI","FCHI","SSMI","AEX","IBEX","FTSEMIB","OMX","OMXC20","OBX","N225","HSI","HSCE","SSEC","SZSE","KS11","TWII","NSEI","BSESN","AXJO","NZ50","STI","JKSE","KLSE","PSE","SET","MXX","BVSP","MERV","IGPA"]:
        return "INDICES"
    # Bonds first (before ETF, since some overlap)
    if s in ["TLT","IEF","SHY","HYG","LQD","TIP","TIPX","SCHQ","SPTL","SPLB","SPSB","SPIB","SPMB","SPAB","SCHO","SCHR","SCHI","SCHZ","AGG","BND","VCIT","VCSH","VGIT","VGSH","VMBS","VTEB","BSV","BIV","BLV","BNDX","BWX","IGOV","IGBH","IGIB","IGSB","AGZ","MUB","TFI","PML","PMX","SCHJ","JNK","BKLN","EMB","JMBA","PFIX","SDAG","SPIP","STIP","SCHP","SPTS"]:
        return "BONDS"
    if s in ["SPYG","SPYV","SPYD","SPHB","SPHQ","SPHD","SPMO","SPUS","SPUU","SPVM","SPYB","SPYX","EFA","IEFA","VEA","VWO","IEMG","IXUS","VXUS","VSS","SCZ","SPDW","VPL","VGK","EWQ","EWU","EWA","EWC","EWH","EWJ","EWL","EWM","EWN","EWS","EWT","EWY","EWW","EWZ","FXI","MCHI","KWEB","KBA","KCE","KURE","XLK","XLF","XLV","XLE","XLI","XLY","XLP","XLB","XLRE","XLU","XLC","XAR","XBI","XRT","XHB","XME","XOP","XES","XSW","XSD","XTN","XTR","XPH","XPP","XNT","XWEB","XSO","ES","NQ","YM","RTY","ZB","ZN","ZF","ZT","ZQ","GE","ZM","ZL","HE","GF","KE","ZR"]:
        return "ETF"
    if s in ["AAPL","MSFT","AMZN","GOOGL","META","NVDA","TSLA","BRK-B","JPM","V","JNJ","WMT","PG","UNH","HD","MA","DIS","BAC","XOM","PFE","KO","PEP","COST","AVGO","CSCO","MCD","ABT","CRM","ACN","TMO","LIN","ADBE","NFLX","CVX","LLY","TXN","ORCL","PM","ABBV","SAP","NEE","UPS","MDT","BMY","HON","UNP","GE","CAT","BA","IBM","GS","MS","BLK","SCHW","AXP","INTC","AMD","QCOM","PLTR","SNOW","CRWD","NET","DDOG","MDB","ZS","OKTA","TTD","UBER","LYFT","ABNB","COIN","RBLX","PLUG","QS","NKLA","SOFI","HOOD","WISH","BYND","PTON","NIO","LI","XPEV","BABA","JD","PDD","BIDU","VIPS","TCEHY","NTES","BILI","HUYA","DOYU","IQ","API","DIDI","ROKU","TWLO","SNAP","PINS","SPOT","ZM","DOCU","MARA","RIOT","SQ","SHOP","SE","MELI","U","FVRR","DASH","ETSY","EBAY","W","RH","BBY","TGT","KR","DG","DLTR","ROST","FAST","GPC","LKQ","AN","ORLY","AZO","AAP","MKS","NSC","CSX","DAL","UAL","LUV","JBLU","ALK","HA","MESA","CPA","LMT","RTX","NOC","GD","HII","TDG","ESLT","CW","HEI","KBR","OC","FLR","PWR","MTZ","AGCO","DE","CNHI","PCAR","CMI","PH","DOV","ITW","ETN","EMR","IR","IEX","AME","FTV","OTIS","CARR","JBL","NWL","KMB","CL","ADM","BG","MOS","CF","FMC","ST","WFC","BAC","C","MS","GS","BLK","JPM","PNC","USB","TFC","SIVB","ZION","CMA","KEY","HBAN","FITB","RF","CFR","EWBC","PACW","OZRK","WAL","TFSL","WTFC"]:
        return "US_EQUITY"
    return "UNKNOWN"

def main():
    print("=" * 70)
    print("COMPREHENSIVE ALL-SECTOR BULLISH SETUP SCANNER")
    print("=" * 70)
    
    # Load universe
    blob = json.loads(UNIVERSE_FILE.read_text(encoding="utf-8"))
    assets = blob["assets"]
    print(f"Loaded {len(assets)} assets from comprehensive universe")
    
    # Scan each asset
    bullish = []
    scanned = 0
    
    for sym, data in assets.items():
        price = data.get("price", 0)
        change = data.get("change_pct", 0)
        
        if price <= 0:
            continue
        
        # Scan all assets (catch both momentum AND mean-reversion dips)
        # Removed: only scan assets with positive change
        # Negative change assets can be dip buys (RSI oversold)
        
        scanned += 1
        result = scan_asset(sym, price, change)
        if result:
            cat = categorize(sym)
            result["category"] = cat
            bullish.append(result)
        
        if scanned % 50 == 0:
            print(f"  Scanned {scanned} bullish candidates...")
    
    # Sort by score
    bullish.sort(key=lambda x: -x["score"])
    
    # Group by sector
    sectors = {}
    for b in bullish:
        cat = b["category"]
        sectors.setdefault(cat, []).append(b)
    
    print(f"\n{'=' * 70}")
    print(f"SCAN COMPLETE: {scanned} bullish candidates scanned, {len(bullish)} setups found")
    print(f"{'=' * 70}")
    
    for cat in sorted(sectors.keys()):
        setups = sectors[cat]
        print(f"\n### {cat} ({len(setups)} setups)")
        for s in setups[:10]:
            print(f"  {s['symbol']:<10} ${s['price']:>10,.2f}  +{s['change_pct']:.2f}%  RSI={s['rsi']:.0f}  Score={s['score']}  R:R={s['rr']}")
            print(f"    Signals: {', '.join(s['signals'])}")
            print(f"    Entry={s['entry']}  SL={s['stop_loss']}  TP1={s['tp1']}  TP2={s['tp2']}")
    
    # Save
    output = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_assets": len(assets),
        "bullish_candidates": scanned,
        "setups_found": len(bullish),
        "sectors": {cat: setups for cat, setups in sectors.items()},
    }
    pathlib.Path(r"C:\Hermes\workflow\data\comprehensive_setups.json").write_text(
        json.dumps(output, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nSaved to: C:\\Hermes\\workflow\\data\\comprehensive_setups.json")

if __name__ == "__main__":
    main()
