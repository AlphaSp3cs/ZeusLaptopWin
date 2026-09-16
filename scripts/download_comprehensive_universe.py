#!/usr/bin/env python3
"""COMPREHENSIVE UNIVERSE DOWNLOADER — all sectors from free sources."""
import json, os, time, pathlib, urllib.request, urllib.error, ssl
from datetime import datetime, timezone

HOME = pathlib.Path.home()
DB_DIR = pathlib.Path(r"C:\Hermes\workflow\data")
DB_DIR.mkdir(parents=True, exist_ok=True)
UNIVERSE_FILE = DB_DIR / "universe_comprehensive.json"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def yf_fetch(symbols, batch_size=50, delay=0.3):
    """Fetch 1mo daily bars from yfinance."""
    import yfinance as yf
    results = {}
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        try:
            data = yf.download(batch, period="1mo", interval="1d", 
                               group_by='ticker', progress=False, timeout=30)
            if data.empty:
                continue
            for sym in batch:
                try:
                    df = data[sym] if len(batch) > 1 else data
                    if df.empty or len(df) < 2:
                        continue
                    last = df.iloc[-1]
                    prev = df.iloc[-2]
                    results[sym] = {
                        "symbol": sym,
                        "price": float(last["Close"]),
                        "open": float(last["Open"]),
                        "high": float(last["High"]),
                        "low": float(last["Low"]),
                        "volume": int(last["Volume"]),
                        "prev_close": float(prev["Close"]),
                        "change_pct": float((last["Close"] - prev["Close"]) / prev["Close"] * 100) if prev["Close"] > 0 else 0,
                        "bars": len(df),
                        "source": "yfinance",
                    }
                except Exception as e:
                    pass
        except Exception as e:
            pass
        time.sleep(delay)
    return results

def binance_fetch():
    """Fetch all USDT spot pairs + futures from Binance (keyless)."""
    base = "https://api.binance.com"
    results = {}
    
    # Spot prices
    try:
        req = urllib.request.Request(f"{base}/api/v3/ticker/24hr", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            data = json.loads(r.read().decode())
        for t in data:
            if t["symbol"].endswith("USDT"):
                sym = t["symbol"].replace("USDT", "-USD")
                results[sym] = {
                    "symbol": sym,
                    "price": float(t["lastPrice"]),
                    "change_pct": float(t["priceChangePercent"]),
                    "volume": float(t["volume"]),
                    "quote_volume": float(t["quoteVolume"]),
                    "high": float(t["highPrice"]),
                    "low": float(t["lowPrice"]),
                    "source": "binance_spot",
                }
    except Exception as e:
        print(f"Binance spot: {e}")
    
    # Futures (perpetual) prices
    try:
        req = urllib.request.Request(f"{base}/fapi/v1/ticker/24hr", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            data = json.loads(r.read().decode())
        for t in data:
            if t["symbol"].endswith("USDT"):
                sym = t["symbol"].replace("USDT", "-USD=F")
                if sym not in results:
                    results[sym] = {
                        "symbol": sym,
                        "price": float(t["lastPrice"]),
                        "change_pct": float(t["priceChangePercent"]),
                        "volume": float(t["volume"]),
                        "quote_volume": float(t["quoteVolume"]),
                        "source": "binance_futures",
                    }
    except Exception as e:
        print(f"Binance futures: {e}")
    
    return results

def coingecko_fetch(top_n=200):
    """Fetch top-N crypto from CoinGecko."""
    results = {}
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={top_n}&page=1&sparkline=false&price_change_percentage=24h,7d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            data = json.loads(r.read().decode())
        for c in data:
            sym = c["symbol"].upper() + "-USD"
            results[sym] = {
                "symbol": sym,
                "name": c.get("name", ""),
                "price": c.get("current_price", 0),
                "change_pct": c.get("price_change_percentage_24h", 0) or 0,
                "change_7d": c.get("price_change_percentage_7d", 0) or 0,
                "market_cap": c.get("market_cap", 0),
                "volume": c.get("total_volume", 0),
                "source": "coingecko",
            }
    except Exception as e:
        print(f"CoinGecko: {e}")
    return results

def main():
    print("=" * 70)
    print("COMPREHENSIVE UNIVERSE DOWNLOADER")
    print("=" * 70)
    
    all_assets = {}
    
    # ---- 1. Yahoo Finance: stocks, ETFs, indices, forex, futures, bonds ----
    print("\n[1/4] Yahoo Finance — stocks, ETFs, indices, forex, futures, bonds")
    
    yf_groups = {
        "US_LARGE_CAP": ["AAPL","MSFT","AMZN","GOOGL","META","NVDA","TSLA","BRK-B","JPM","V","JNJ","WMT","PG","UNH","HD","MA","DIS","BAC","XOM","PFE","KO","PEP","COST","AVGO","CSCO","MCD","ABT","CRM","ACN","TMO","LIN","ADBE","NFLX","CVX","LLY","TXN","ORCL","PM","ABBV","SAP","NEE","UPS","MDT","BMY","HON","UNP","GE","CAT","BA","IBM","GS","MS","BLK","SCHW","AXP","INTC","AMD","QCOM","PLTR","SNOW","CRWD","NET","DDOG","MDB","ZS","OKTA","TTD","TWTR","UBER","LYFT","ABNB","COIN","RBLX","PLUG","QS","NKLA","SOFI","HOOD","WISH","BYND","PTON","NIO","LI","XPEV","BABA","JD","PDD","BIDU","VIPS","TCEHY","NTES","BILI","HUYA","DOYU","IQ","API","DIDI","VIPS","VIPS","VIPS"],
        "US_MID_CAP": ["ROKU","TWLO","SNAP","PINS","SPOT","ZM","DOCU","PTON","MARA","RIOT","SQ","SHOP","SE","MELI","SNOW","CRWD","DDOG","NET","ZS","OKTA","TTD","COIN","RBLX","HOOD","WISH","SOFI","PLUG","BLNK","QS","NKLA","GOEV","FSR","LCID","RIVN","FSLY","U","FVRR","TWTR","UBER","LYFT","ABNB","DASH","ETSY","EBAY","W","RH","BBY","TGT","WMT","COST","KR","DG","DLTR","ROST","FAST","GPC","LKQ","AN","ORLY","AZO","AAP","MKS","NSC","CSX","UNP","DAL","UAL","LUV","JBLU","ALK","HA","MESA","CPA","BA","LMT","RTX","NOC","GD","HII","TDG","ESLT","CW","HEI","KBR","OC","FLR","PWR","MTZ","AGCO","DE","CNHI","CAT","PCAR","CMI","PH","DOV","ITW","ETN","EMR","IR","IEX","AME","FTV","OTIS","CARR","OTIS","GE"],
        "US_SMALL_CAP": ["WISH","SOFI","PLUG","QS","NKLA","GOEV","FSR","RIVN","LCID","U","FVRR","DASH","ETSY","EBAY","W","RH","BURL","AEO","GES","ANF","EXPR","JWN","DXLG","CHS","GCO","CAL","BOOT","SGC","CTRN","TLYS","ZUM","GPRO","ION","HELE","BRLT","HEAR","VUZI","MJCO","EFOI","AMRK","FOSL","MOV","ELA","CRWS","GIL","HBI","VFC","COLM","DECK","SKX","ONON","SCHW","TFSL","WTFC","ZION","CMA","KEY","HBAN","FITB","RF","CFR","PBCT","SIVB","WAL","OZRK","EWBC","PACW","WFC","MS","GS","BLK"],
        "BONDS_RATES": ["^TNX","^TYX","^IRX","^FVX","^VXTYN","^VIX","^VIX3M","^VIX6M","^VIX9D","^VVIX","^MOVE","^CLS","^CLX","^CL1","^CL2","^CL3","^CL6","^CL12"],
        "BONDS_TREASURY": ["^TNX","^TYX","^IRX","^FVX","^VXTYN","^VIX","^VIX3M","^VIX6M","^VIX9D","^VVIX","^MOVE","^CLS","^CLX","^CL1","^CL2","^CL3","^CL6","^CL12"],
        "FX_MAJORS": ["EURUSD=X","GBPUSD=X","USDJPY=X","USDCHF=X","AUDUSD=X","USDCAD=X","NZDUSD=X","EURGBP=X","EURJPY=X","GBPJPY=X","EURCHF=X","EURAUD=X","EURCAD=X","EURNZD=X","GBPAUD=X","GBPCAD=X","GBPNZD=X","AUDCAD=X","AUDNZD=X","NZDCAD=X","AUDCHF=X","NZDCHF=X","CADCHF=X","CADJPY=X","CHFJPY=X"],
        "FX_EXOTICS": ["USDMXN=X","USDZAR=X","USDBRL=X","USDCNY=X","USDKRW=X","USDINR=X","USDRUB=X","USDTRY=X","USDSEK=X","USDNOK=X","USDDKK=X","USDHKD=X","USDSGD=X","USDTWD=X","USDTHB=X","USDPHP=X","USDMYR=X","USDIDR=X","USDHUF=X","USDPLN=X","USDCZK=X","USDILS=X","USDAED=X","USDSAR=X"],
        "INDICES_US": ["^GSPC","^DJI","^IXIC","^RUT","^VIX","^W5000","^SP400","^SP600","^SPX","^SP100","^NDX","^RUI","^RUA","^RUT","^VIX","^VVIX","^SKEW","^CLS","^CLX","^CL1","^CL2","^CL3","^CL6","^CL12"],
        "INDICES_EUROPE": ["^STOXX50E","^FTSE","^GDAXI","^FCHI","^SSMI","^AEX","^IBEX","^FTSEMIB","^OMX","^OMXC20","^OBX","^AEX","^SSMI","^FTSE","^GDAXI","^FCHI","^STOXX50E"],
        "INDICES_ASIA": ["^N225","^HSI","^HSCE","^SSEC","^SZSE","^KS11","^TWII","^NSEI","^BSESN","^AXJO","^NZ50","^STI","^JKSE","^KLSE","^PSE","^SET","^MXX","^BVSP","^MERV","^IGPA","^MERV"],
        "METALS": ["GC=F","SI=F","PL=F","PA=F","HG=F","GLD","SLV","SIVR","PPLT","PALL"],
        "ENERGY": ["CL=F","BZ=F","NG=F","RB=F","HO=F","USO","UNG","XLE","OIH","TAN","FAN","PBW","QCLN","SMOG","ICLN","TAN"],
        "AGRICULTURE": ["ZC=F","ZW=F","ZS=F","KC=F","SB=F","CT=F","CC=F","LE=F","OJ=F","LBS=F","ZC=F","ZR=F","ZM=F","ZL=F","ZO=F","GF=F","HE=F","LB=F"],
        "CRYPTO_YFI": ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","DOGE-USD","AVAX-USD","LINK-USD","MATIC-USD","DOT-USD","LTC-USD","UNI-USD","ATOM-USD","ETC-USD","XLM-USD","ALGO-USD","FIL-USD","HBAR-USD","ICP-USD","APT-USD","SUI-USD","ARB-USD","OP-USD","NEAR-USD","INJ-USD","TIA-USD","SEI-USD","PYTH-USD","WIF-USD","BONK-USD","PEPE-ORD-USD","SHIB-USD","TON-USD","WLD-USD","STX-USD","IMX-USD","RNDR-USD","GRT-USD","THETA-USD","AXS-USD","SAND-USD","MANA-USD","ENJ-USD","GALA-USD","FLOW-XT-USD","XTZ-USD","EOS-USD","AAVE-USD","MKR-USD","COMP-USD","CRV-USD","1INCH-USD","DYDX-USD","SNX-USD","PERP-USD","GMX-USD","VELA-USD","ARB-USD","OP-USD","METIS-USD","BOBA-USD","IMX-USD","LRC-USD","ZRX-USD","KNC-USD","BAL-USD","BNT-USD","ZEC-USD","DASH-USD","XMR-USD","XVG-USD","SC-USD","MAID-USD","SYS-USD","RVN-USD","BEAM-USD","GRIN-USD","ZEN-USD","KMD-USD","BTG-USD","BSV-USD","BCH-USD","XEC-USD","FLUX-USD","CKB-USD","CFX-USD","GLMR-USD","MOVR-USD","ASTR-ACA-ACA-USD","SDN-ACA-ACA-ACA-USD","ACA-ACA-ACA-ACA-ACA-ACA-USD","ROSE-ACA-ACA-ACA-USD","ASTR-ACA-ACA-USD","SDN-ACA-ACA-ACA-USD"],
        "ETF_SECTORS": ["XLK","XLF","XLV","XLE","XLI","XLY","XLP","XLB","XLRE","XLU","XLC","XAR","XBI","XRT","XHB","XME","XOP","XES","XSW","XSD","XNTK","XTN","XTR","XT","XHE","XHS","XPH","XPP","XL","XITK","XNT","XWEB","XSO","XRT","XLB","XME","XOP","XES","XAR","XBI","XRT","XHB","XSW","XSD"],
        "ETF_BONDS": ["TLT","IEF","SHY","HYG","LQD","TIP","TIPX","SCHQ","SPTL","SPLB","SPSB","SPIB","SPMB","SPAB","SCHO","SCHR","SCHI","SCHZ","AGG","BND","VCIT","VCSH","VGIT","VGSH","VMBS","VTEB","VWIT","BSV","BIV","BLV","BNDX","BWX","IGOV","IGBH","IGIB","IGSB","AGZ","AGT","MUB","TFI","PML","PMX","VTEB","VCIT","VCSH"],
        "ETF_COMMODITIES": ["GLD","SLV","USO","UNG","PDBC","DBA","DBC","GSG","USCI","DJP","RJI","RJA","JJE","JJM","JJU","JJO","JJG","JJM","JJE","JJU","JJO","JJG"],
        "ETF_INTL": ["EFA","IEFA","VEA","VWO","IEMG","IXUS","VXUS","FTIH","VSS","SCZ","SPDW","VPL","VGK","EWQ","EWU","EWA","EWC","EWH","EWJ","EWL","EWM","EWN","EWS","EWT","EWY","EWW","EWZ","FXI","MCHI","KWEB","KBA","KCE","KURE","KWEB"],
        "ETF_FACTORS": ["SPY","VOO","IVV","SPLG","SPTM","SPYG","SPYV","SPYD","SPHB","SPHQ","SPHD","SPMO","SPUS","SPUU","SPVM","SPYB","SPYX","SPYD","SPYG","SPYV"],
        "FUTURES": ["ES=F","NQ=F","YM=F","RTY=F","YM=F","CL=F","BZ=F","GC=F","SI=F","PL=F","PA=F","HG=F","ZC=F","ZW=F","ZS=F","KC=F","SB=F","CT=F","CC=F","LE=F","OJ=F","LBS=F","RB=F","HO=F","NG=F","ZB=F","ZN=F","ZF=F","ZT=F","ZQ=F","GE=F","ZB=F","ZM=F","ZL=F","HE=F","GF=F","KE=F","ZC=F","ZR=F"],
        "OPTIONS_INDICES": ["SPY","QQQ","IWM","DIA","GLD","TLT","HYG","EFA","EEM","IWM","QQQ","SPY","GDX","XLF","XLE","XOP","FXI","KWEB","EEM","VWO","VEA","AGG","BND","LQD","HYG","TIP","EMB","JNK","MBB","SHY","IEF","TLT","EDV","VGIT","VCIT","VCSH","BNDX","IGOV"],
    }
    
    # Flatten and dedupe
    yf_all = []
    seen_yf = set()
    for group, syms in yf_groups.items():
        for s in syms:
            if s not in seen_yf and len(s) >= 1:
                seen_yf.add(s)
                yf_all.append(s)
    
    print(f"  Total unique Yahoo Finance symbols: {len(yf_all)}")
    yf_results = yf_fetch(yf_all, batch_size=30, delay=0.25)
    print(f"  Fetched: {len(yf_results)}")
    all_assets.update(yf_results)
    
    # ---- 2. Binance: crypto spot + futures ----
    print("\n[2/4] Binance — crypto spot + futures")
    binance_results = binance_fetch()
    print(f"  Fetched: {len(binance_results)}")
    for sym, data in binance_results.items():
        if sym not in all_assets:
            all_assets[sym] = data
    
    # ---- 3. CoinGecko: crypto ----
    print("\n[3/4] CoinGecko — crypto markets")
    cg_results = coingecko_fetch(top_n=250)
    print(f"  Fetched: {len(cg_results)}")
    for sym, data in cg_results.items():
        if sym not in all_assets:
            all_assets[sym] = data
    
    # ---- 4. Free international indices ----
    print("\n[4/4] Additional indices from Yahoo Finance")
    
    # ---- Save ----
    print(f"\n{'=' * 70}")
    print(f"TOTAL ASSETS: {len(all_assets)}")
    print(f"{'=' * 70}")
    
    # Sector breakdown
    sectors = {}
    for sym, data in all_assets.items():
        cat = data.get("category", "unknown")
        sectors.setdefault(cat, []).append(sym)
    
    # Save to file
    out = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_assets": len(all_assets),
        "sources": ["yfinance", "binance", "coingecko"],
        "assets": all_assets,
        "sectors": sectors,
    }
    UNIVERSE_FILE.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"Saved to: {UNIVERSE_FILE}")
    
    # ---- Also update bars.db ----
    print("\nUpdating bars.db with comprehensive universe...")
    # Trigger bars refresh
    import subprocess
    subprocess.Popen([r"C:\Users\victo\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe",
                     r"C:\Hermes\workflow\scripts\bars_db.py", "--update"],
                    cwd=r"C:\Hermes\workflow\scripts")
    
    return all_assets

if __name__ == "__main__":
    main()
