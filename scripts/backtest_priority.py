import json, sqlite3, pathlib, statistics
from collections import defaultdict

DB = pathlib.Path(r"C:\Hermes\workflow\data\bars.db")

def calc_rsi(closes, period=14):
    if len(closes) < period + 1: return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0)); losses.append(max(-diff, 0))
    ag = sum(gains[-period:]) / period; al = sum(losses[-period:]) / period
    if al == 0: return 100
    return 100 - (100 / (1 + ag / al))

def calc_ema(closes, period):
    if len(closes) < period: return closes[-1] if closes else 0
    k = 2 / (period + 1); ema = sum(closes[:period]) / period
    for c in closes[period:]: ema = c * k + ema * (1 - k)
    return ema

def backtest_symbol(con, sym_db):
    cur = con.cursor()
    cur.execute("SELECT ts,open,high,low,close,volume FROM bars WHERE symbol=? AND tf='1d' ORDER BY ts LIMIT 2000", (sym_db,))
    rows = cur.fetchall()
    if len(rows) < 200: return None
    closes = [r[4] for r in rows]; volumes = [r[5] for r in rows]
    matches = []
    for i in range(100, len(closes) - 60):
        window = closes[:i+1]; rsi = calc_rsi(window)
        ema20 = calc_ema(window, 20); ema50 = calc_ema(window, 50)
        price = closes[i]; avg_vol = sum(volumes[max(0,i-20):i+1]) / 20
        vol_ratio = volumes[i] / avg_vol if avg_vol > 0 else 1
        score = 0
        if price > ema20: score += 1
        if price > ema50: score += 1
        if 30 <= rsi <= 50: score += 2
        elif 50 < rsi <= 65: score += 1
        if vol_ratio > 1.5: score += 1
        if i >= 2 and closes[i] > closes[i-1] > closes[i-2]: score += 1
        if score < 3: continue
        fwd_5 = (closes[min(i+5, len(closes)-1)] - price) / price if price > 0 else 0
        fwd_20 = (closes[min(i+20, len(closes)-1)] - price) / price if price > 0 else 0
        matches.append({"date": rows[i][0], "rsi": rsi, "score": score, "fwd_5": fwd_5, "fwd_20": fwd_20})
    if not matches: return None
    win_5 = sum(1 for m in matches if m["fwd_5"] > 0) / len(matches) * 100
    win_20 = sum(1 for m in matches if m["fwd_20"] > 0) / len(matches) * 100
    return {"n": len(matches), "win_5d": round(win_5,1), "win_20d": round(win_20,1), "avg_5d": round(statistics.mean([m["fwd_5"] for m in matches])*100,2), "avg_20d": round(statistics.mean([m["fwd_20"] for m in matches])*100,2)}

def main():
    con = sqlite3.connect(str(DB))
    # Top 10 priority symbols from today's scan + user's priority names
    priority = ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","DOGE-USD","FIL-USD","AVAX-USD","DOT-USD","XLM-USD","HBAR-USD","XMR-USD","DASH-USD","SHIB-USD","NEAR-USD","SUI-USD","LINK-USD","MATIC-USD","LTC-USD","UNI-USD","AAVE-USD","ATOM-USD","ETC-USD","ALGO-USD","ICP-USD","APT-USD","ARB-USD","OP-USD","INJ-USD","SEI-USD","TIA-USD","WIF-USD","BONK-USD","TON-USD","WLD-USD","STX-USD","RNDR-USD","THETA-USD","XTZ-USD","EOS-USD","MKR-USD","COMP-USD","CRV-USD","ZEC-USD","RVN-USD","XEM-USD","XDC-USD","PRL-USD","ORN-USD","YFI-USD","HNT-USD","FLM-USD","REN-USD","NKN-USD","ARPA-USD","FSLY","FOSL","GRIN-USD","XHS","ONE-USD","GOOGL","MSFT","V","KO","ACN","ADBE","MA","TGT","ROKU","TMO","ABBV","SAP","PLTR","EWH","KWEB","FXI","UNG","USO","OJ=F","ZC=F","ZW=F","CT=F","ZL=F","ZS=F","NG=F","SI=F","PA=F","HG=F","ES=F","NQ=F","YM=F","RTY=F"]
    
    results = []
    for sym in priority[:80]:
        # Try different symbol formats
        cur = con.cursor()
        sym_db = sym.replace("-USD", "").replace("=F", "").replace("-USD=F", "")
        cur.execute("SELECT COUNT(*) FROM bars WHERE symbol=? AND tf='1d'", (sym_db,))
        if cur.fetchone()[0] < 200:
            cur.execute("SELECT COUNT(*) FROM bars WHERE symbol=? AND tf='1d'", (sym,))
            if cur.fetchone()[0] >= 200:
                sym_db = sym
            else:
                continue
        r = backtest_symbol(con, sym_db)
        if r:
            r["symbol"] = sym
            results.append(r)
            print(f"{sym:<12} n={r['n']:>4} W5={r['win_5d']:>5.1f}% W20={r['win_20d']:>5.1f}% Avg5={r['avg_5d']:>+6.2f}% Avg20={r['avg_20d']:>+6.2f}%")
    
    con.close()
    results.sort(key=lambda x: -x["win_20d"])
    print(f"\n{'='*60}")
    print("TOP 20 BY 20-DAY WIN RATE:")
    for i,r in enumerate(results[:20]):
        print(f"{i+1:>2}. {r['symbol']:<12} W20%={r['win_20d']:>5.1f} Avg20={r['avg_20d']:>+6.2f}%")
    pathlib.Path(r"C:\Hermes\workflow\data\backtest_priority.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved to C:\\Hermes\\workflow\\data\\backtest_priority.json")

if __name__ == "__main__":
    main()
