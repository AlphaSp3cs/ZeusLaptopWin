#!/usr/bin/env python3
"""Inject a styled LIVE BACKTEST + OPEN POSITIONS section into an existing
report HTML (preserving the host's CSS) and optionally print a PDF via Chrome.

Usage:
  python3 inject_report.py --html OB.html --json backtest.json [--pdf out.pdf] [--open OPEN_MD]
Reads from <html>.bak.html if present (idempotent rebuild), else from --html.
"""
import json, shutil, subprocess, argparse, datetime as dt
from pathlib import Path
import pandas as pd

def cyc(months):
    if not months: return "n/a"
    s=set(months)
    if len(s)>=11: return "MONTHLY"
    if s<={1,4,7,10}: return "JAJO"
    if s<={2,5,8,11}: return "FMAN"
    if s<={3,6,9,12}: return "MJSD"
    return "Qtr("+",".join(map(str,months))+")"
PILL=lambda y:"y3" if y>=5 else ("y2" if y>=3 else "y1")

def yrow(r,rank=None,hl=False):
    bt=r["backtest"];h3=r["hold3y"]
    btm=f"{bt['median_1y_total']}%" if bt else "—"; btp=f"{bt['pct_positive']}%" if bt else "—"
    h3t=f"{h3['total_3y']}%" if h3 else "—"
    rk=f'<span class="bt-rank">{rank}</span>' if rank else ""
    return (f"<tr{' class=\"bt-hl\"' if hl else ''}><td>{rk} {r['ticker']}</td>"
            f"<td class='bt-num'>${r['price']}</td>"
            f"<td><span class='yield-pill {PILL(r['live_yield'])}'>{r['live_yield']}%</span></td>"
            f"<td class='bt-cyc'>{cyc(r['pay_months'])}</td>"
            f"<td class='bt-num bt-pos'>{btm}</td><td class='bt-num bt-pos'>{btp}</td>"
            f"<td class='bt-num'>{h3t}</td></tr>")

def build(data, gen):
    ranked=data["ranked_by_live_yield"]; failed=data.get("failed",[])
    best=[r for r in ranked if r["backtest"] and r["backtest"]["pct_positive"]>=90
          and r["backtest"]["median_1y_total"]>=20]
    full="\n".join(yrow(r) for r in ranked)
    bestrows="\n".join(yrow(r,i+1,True) for i,r in enumerate(best))
    # buy plan
    b={k:[] for k in ("MONTHLY","JAJO","FMAN","MJSD","OTHER")}
    for r in ranked:
        c=cyc(r["pay_months"]); b.setdefault(c if c in b else "OTHER",[]).append(r)
    co=["MONTHLY","JAJO","FMAN","MJSD","OTHER"]; ptr={c:0 for c in co}
    plan="";tier=0;add=True
    while add:
        add=False
        for c in co:
            lst=b.get(c,[])
            if ptr[c]<len(lst):
                r=lst[ptr[c]];ptr[c]+=1;tier+=1
                lim=round(r["price"]*0.985,2)
                wy=f"top-yield {c} payer; median 1Y swing {r['backtest']['median_1y_total']}%" if r["backtest"] else f"top-yield {c} payer"
                plan+=f"<tr><td class='bt-num'>{tier}</td><td>{r['ticker']}</td><td class='bt-num'>{r['live_yield']}%</td>"\
                      f"<td class='bt-num'>${r['price']}</td><td class='bt-num bt-limit'>${lim}</td><td class='bt-cyc'>{c}</td><td>{wy}</td></tr>"
                add=True
    drip="".join(f"<tr><td>{r['ticker']}</td><td class='bt-num'>{r['live_yield']}%</td>"+
                 "".join(f"<td class='bt-num'>${10000*(1+r['live_yield']/100)**yr:,.0f}</td>" for yr in (1,3,5,10))+"</tr>"
                 for r in ranked[:10])
    bestlist=", ".join(f"{r['ticker']} {r['live_yield']}%" for r in best[:6])
    top10=", ".join(f"{r['ticker']} ({r['live_yield']}%)" for r in ranked[:10])
    SECTION=f"""
<!-- LIVE BACKTEST -->
<div class="bt-banner">LIVE MARKET UPDATE &middot; {gen} &middot; via Yahoo Finance</div>
<div class="section-heading"><h2>Live Backtest &amp; Highest-Dividend Ranking</h2><span>re-priced live &middot; 3y rolling 1Y swing &middot; ranked by yield</span></div>
<div class="bt-callout"><div class="bt-callout-h">EXECUTIVE SUMMARY — income-swing sweet spot</div>
<p>{len(best)} names pass &ge;90% positive windows AND &ge;20% median swing. Top: {bestlist}&hellip;</p>
<p class="bt-callout-sub">Highest 10 payers: {top10}</p></div>
<div class="section-heading"><h2>The "Best Set"</h2></div>
<table class="dividend-table bt-tbl"><thead><tr><th>Ticker</th><th>Live $</th><th>Yield</th><th>Cycle</th><th>Median 1Y Swing</th><th>% Positive</th><th>3Y Total</th></tr></thead><tbody>{bestrows}</tbody></table>
<div class="section-heading"><h2>Full Universe</h2></div>
<table class="dividend-table bt-tbl"><thead><tr><th>Ticker</th><th>Live $</th><th>Yield</th><th>Cycle</th><th>Median 1Y Swing</th><th>% Positive</th><th>3Y Total</th></tr></thead><tbody>{full}</tbody></table>
<div class="section-heading"><h2>Executable Income Buy Plan</h2></div>
<table class="dividend-table bt-tbl"><thead><tr><th>Tier</th><th>Ticker</th><th>Yield</th><th>Live $</th><th>Entry Limit -1.5%</th><th>Cycle</th><th>Why</th></tr></thead><tbody>{plan}</tbody></table>
<div class="section-heading"><h2>DRIP Compounding</h2></div>
<table class="dividend-table bt-tbl"><thead><tr><th>Ticker</th><th>Yield</th><th>Yr1</th><th>Yr3</th><th>Yr5</th><th>Yr10</th></tr></thead><tbody>{drip}</tbody></table>
<div class="bt-note"><b>Method.</b> Live yields = TTM div &divide; last price. Backtest = weekly-entry 1Y hold, price+divs, no DRIP/tx.
3Y = realized, not forward. {"No fetch failures." if not failed else "Failed: "+", ".join(r['ticker'] for r in failed)}</div>
"""
    return SECTION

STYLE="""<style>
.bt-banner{background:#003366;color:#cfe0f5;font-family:Arial;font-size:.72rem;letter-spacing:.5px;padding:.5rem 3rem;text-transform:uppercase;}
.bt-callout{margin:1rem 3rem;padding:1.1rem 1.4rem;border-left:5px solid #c0392b;background:#fdf3f2;font-family:Arial;color:#1a2634;line-height:1.6;}
.bt-callout-h{font-weight:700;color:#001f3f;font-size:.95rem;text-transform:uppercase;}
.bt-callout-list,.bt-callout-sub{font-size:1.05rem;font-weight:700;color:#003366;}
.bt-tbl{margin:.4rem 3rem .6rem 3rem;width:auto;}.bt-tbl td,.bt-tbl th{padding:.5rem .9rem;}
.bt-num{text-align:right;font-family:'Courier New',monospace;font-weight:700;color:#003366;}
.bt-pos{color:#1a6e3c !important;}.bt-neg{color:#c0392b !important;}.bt-limit{color:#c0392b !important;}
.bt-cyc{text-align:center;font-size:.72rem;font-weight:700;color:#34495e;}
.bt-hl{background:#fff6e6 !important;}.bt-rank{display:inline-block;background:#003366;color:#fff;border-radius:2px;padding:.05rem .4rem;margin-right:.3rem;}
.bt-note{margin:1rem 3rem 1.5rem 3rem;font-family:Arial;font-size:.72rem;color:#6b7a90;line-height:1.6;border-top:1px solid #e2e8f0;padding-top:.8rem;}
@media print{.filter-row,.stats-bar,.masthead-top{display:none;} *{-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
</style>"""

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--html",required=True); ap.add_argument("--json",required=True)
    ap.add_argument("--pdf",default=""); ap.add_argument("--open",default="")
    a=ap.parse_args()
    html=Path(a.html); bak=html.with_suffix(".bak.html")
    src=bak.read_text(encoding="utf-8") if bak.exists() else html.read_text(encoding="utf-8")
    if not bak.exists(): shutil.copy(html,bak)
    data=json.loads(Path(a.json).read_text()); gen=dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    section=build(data,gen)
    open_sec=Path(a.open).read_text(encoding="utf-8") if a.open else ""
    marker='<footer class="pub-footer">'
    before,after=src.split(marker,1)
    updated=before+section+open_sec+STYLE+marker+after
    html.write_text(updated,encoding="utf-8")
    print("Injected ->",html)
    if a.pdf:
        chrome=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        subprocess.run([chrome,"--headless","--disable-gpu","--no-sandbox","--no-pdf-header-footer",
                        f"--print-to-pdf={a.pdf}",f"file:///{html.as_posix()}"],check=True)
        print("PDF ->",a.pdf)

if __name__=="__main__": main()
