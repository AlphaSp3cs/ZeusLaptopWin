#!/usr/bin/env python3
"""Live backtest + yield ranking for a dividend ticker universe.
Usage: python3 backtest_universe.py <input.html|input.json>
Writes <stem>_backtest.json and <stem>_backtest.md next to the input.
"""
import re, json, sys, time, datetime as dt
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf

def parse_tickers(src, path):
    if path.suffix.lower() == ".json":
        d = json.loads(src)
        if isinstance(d, list): return d
        if "UNIVERSE" in d: return [x.get("ticker") for x in d["UNIVERSE"]]
        if "tickers" in d: return d["tickers"]
        return list(d.keys())
    return re.findall(r'ticker:"([A-Z0-9\.]+)"', src)

def safe(fn, tries=3):
    for i in range(tries):
        try: return fn()
        except Exception as e:
            if i == tries-1: return ("ERR", str(e))
            time.sleep(1.5*(i+1))

def fetch(tkr):
    t = yf.Ticker(tkr)
    hist = safe(lambda: t.history(period="3y", interval="1wk", auto_adjust=True))
    if isinstance(hist, tuple): return {"ticker": tkr, "error": hist[1]}
    if hist is None or len(hist) < 20: return {"ticker": tkr, "error": "insufficient history"}
    try: price = float(t.fast_info["last_price"])
    except Exception:
        try: price = float(hist["Close"].iloc[-1])
        except Exception: return {"ticker": tkr, "error": "no price"}
    divs = pd.Series(dtype=float)
    try:
        d = getattr(t, "dividends", None)
        if d is not None and len(d): divs = d.dropna()
        else:
            d2 = t.get_dividends()
            if d2 is not None and len(d2): divs = d2.dropna()
    except Exception: pass
    return {"ticker": tkr, "hist": hist, "price": price, "divs": divs}

def backtest(hist, divs):
    raw = hist["Close"].dropna(); divs = divs.sort_index()
    def din(s,e): return float(divs[(divs.index>=s)&(divs.index<=e)].sum())
    w = list(raw.index); tot=[]; inc=[]
    for i in range(0, len(w)-52):
        p0,p1 = raw.iloc[i], raw.iloc[i+52]
        if p0<=0: continue
        tot.append(p1/p0-1+din(w[i],w[i+52])/p0); inc.append(din(w[i],w[i+52])/p0)
    if not tot: return None
    a=np.array(tot)
    return {"median_1y_total":round(float(np.median(a))*100,2),
            "pct_positive":round(float((a>0).mean())*100,1),
            "median_1y_income":round(float(np.median(inc))*100,2),
            "n_windows":len(a)}

def hold3y(raw, divs):
    if len(raw)<150: return None
    start,end = raw.index[0], raw.index[-1]
    inc = float(divs[(divs.index>=start)&(divs.index<=end)].sum())
    pr = raw.iloc[-1]/raw.iloc[0]-1
    return {"price_ret_3y":round(pr*100,2),"income_3y":round(inc/raw.iloc[0]*100,2),
            "total_3y":round((pr+inc/raw.iloc[0])*100,2)}

def cyc(months):
    if not months: return "n/a"
    s=set(months)
    if len(s)>=11: return "MONTHLY"
    if s<={1,4,7,10}: return "JAJO"
    if s<={2,5,8,11}: return "FMAN"
    if s<={3,6,9,12}: return "MJSD"
    return "Qtr("+",".join(str(m) for m in months)+")"

def main():
    p = Path(sys.argv[1]); src = p.read_text(encoding="utf-8")
    UNIV = [t for t in dict.fromkeys(parse_tickers(src, p))]
    print(f"Parsed {len(UNIV)} instruments")
    out=[]
    for tkr in UNIV:
        d=fetch(tkr)
        if "error" in d: out.append({"ticker":tkr,"error":d["error"]}); print("  FAIL",tkr,d["error"]); continue
        divs=d["divs"]; tz=getattr(divs.index,"tz",None)
        now=pd.Timestamp.now(tz=tz) if tz else pd.Timestamp.now()
        ttm=float(divs[divs.index>=now-pd.Timedelta(days=365)].sum())
        ly=(ttm/d["price"]*100) if d["price"] else 0
        recent=divs[divs.index>=now-pd.Timedelta(days=730)]
        out.append({"ticker":tkr,"price":round(d["price"],2),"ttm_div":round(ttm,4),
                    "live_yield":round(ly,2),"pay_months":sorted({int(x.month) for x in recent.index}),
                    "n_exdiv_2y":int(len(recent)),"backtest":backtest(d["hist"],divs),
                    "hold3y":hold3y(d["hist"]["Close"].dropna(),divs)})
        print(f"  {tkr} {ly:.2f}%", flush=True); time.sleep(0.4)
    ok=[r for r in out if "error" not in r]; err=[r for r in out if "error" in r]
    ranked=sorted(ok,key=lambda r:r["live_yield"],reverse=True)
    p.with_name(p.stem+"_backtest.json").write_text(
        json.dumps({"generated":dt.datetime.now().isoformat(timespec="seconds"),
        "ranked_by_live_yield":ranked,"failed":err},indent=2,default=str),encoding="utf-8")
    # minimal MD
    md=[f"# {p.stem} — Live Backtest","" ,"| # | Tkr | $ | Yield | Cycle | 1Y Med | %Pos | 3Y |"]
    md.append("|---|----|---|------|------|------|----|----|")
    for i,r in enumerate(ranked,1):
        bt=r["backtest"];h3=r["hold3y"]
        md.append(f"| {i} | {r['ticker']} | ${r['price']} | {r['live_yield']}% | {cyc(r['pay_months'])} |"
                  f" {bt['median_1y_total'] if bt else '-'}% | {bt['pct_positive'] if bt else '-'}% |"
                  f" {h3['total_3y'] if h3 else '-'}% |")
    p.with_name(p.stem+"_backtest.md").write_text("\n".join(md),encoding="utf-8")
    print(f"\nOK={len(ok)} ERR={len(err)} -> {p.stem}_backtest.json/.md")

if __name__=="__main__": main()
