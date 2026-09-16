#!/usr/bin/env python3
"""backtest_income_swing.py - live backtest + highest-yield ranking for an income buy plan.

Given a ticker list (or an HTML file containing a UNIVERSE-style array), pulls LIVE
price/dividend data via yfinance, runs a weekly-entry rolling 1y long-swing backtest
(price + realized dividends, no DRIP/tx costs), decomposes trailing 3y price-vs-income
return, ranks by live yield (highest payer first), applies a quality screen, and emits a
cycle-diversified income buy plan (LIMIT orders, -1.5% dip entry).

Usage:
  python3 backtest_income_swing.py --tickers ARCC,MAIN,MO,O,EPD
  python3 backtest_income_swing.py --html "C:\\Users\\victo\\Desktop\\OB Dividends 2026.html"
  python3 backtest_income_swing.py --tickers A,B,C --out my_report

Output: <out>.md (plan) and <out>.json (raw live snapshot).

Tested on system Python 3.13 + yfinance 1.5.2. See SKILL.md pitfalls for the
yfinance 1.5.2 gotchas this script already handles (no `progress` kwarg, tz-aware
dividend index, `get_dividends()` fallback).
"""
import re, json, sys, time, argparse, datetime as dt
from pathlib import Path

import yfinance as yf
import pandas as pd
import numpy as np


def parse_html_tickers(path):
    txt = Path(path).read_text(encoding="utf-8", errors="ignore")
    raw = re.findall(r'ticker:"([A-Z0-9\.]+)"', txt)
    seen, out = set(), []
    for t in raw:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def safe(fn, tries=3, delay=1.5):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1:
                return ("ERR", str(e))
            time.sleep(delay * (i + 1))
    return ("ERR", "unknown")


def fetch(tkr):
    t = yf.Ticker(tkr)
    # yfinance 1.5.2: no `progress` / `actions` kwargs
    hist = safe(lambda: t.history(period="3y", interval="1wk", auto_adjust=True))
    if isinstance(hist, tuple):
        return {"ticker": tkr, "error": hist[1]}
    if hist is None or len(hist) < 20:
        return {"ticker": tkr, "error": "insufficient history"}
    price = None
    try:
        price = float(t.fast_info["last_price"])
    except Exception:
        try:
            price = float(hist["Close"].iloc[-1])
        except Exception:
            return {"ticker": tkr, "error": "no price"}
    # dividends: legacy attr first, then get_dividends() fallback
    divs = pd.Series(dtype=float)
    try:
        d = getattr(t, "dividends", None)
        if d is not None and len(d):
            divs = d.dropna()
        else:
            d2 = t.get_dividends()
            if d2 is not None and len(d2):
                divs = d2.dropna()
    except Exception:
        pass
    return {"ticker": tkr, "hist": hist, "price": price, "divs": divs}


def backtest(hist, divs):
    raw = hist["Close"].dropna()
    div_series = divs.sort_index()
    weeks = list(raw.index)
    n = len(weeks)
    tot_w, inc_w = [], []
    for i in range(0, n - 52):
        s, e = weeks[i], weeks[i + 52]
        p0, p1 = raw.iloc[i], raw.iloc[i + 52]
        if p0 <= 0:
            continue
        inc = float(div_series[(div_series.index >= s) & (div_series.index <= e)].sum())
        tot_w.append(p1 / p0 - 1.0 + inc / p0)
        inc_w.append(inc / p0)
    if not tot_w:
        return None
    arr = np.array(tot_w)
    return {
        "median_1y_total": round(float(np.median(arr)) * 100, 2),
        "mean_1y_total": round(float(np.mean(arr)) * 100, 2),
        "pct_positive": round(float((arr > 0).mean()) * 100, 1),
        "median_1y_income": round(float(np.median(inc_w)) * 100, 2),
        "n_windows": len(arr),
    }


def hold3y(raw, divs):
    if len(raw) < 150:
        return None
    p0, p1 = raw.iloc[0], raw.iloc[-1]
    if p0 <= 0:
        return None
    s, e = raw.index[0], raw.index[-1]
    inc = float(divs[(divs.index >= s) & (divs.index <= e)].sum())
    pr = p1 / p0 - 1
    return {
        "price_ret_3y": round(pr * 100, 2),
        "income_3y": round(inc / p0 * 100, 2),
        "total_3y": round((pr + inc / p0) * 100, 2),
    }


def cyc(months):
    if not months:
        return "n/a"
    s = set(months)
    if s <= {1, 4, 7, 10}:
        return "JAJO"
    if s <= {2, 5, 8, 11}:
        return "FMAN"
    if s <= {3, 6, 9, 12}:
        return "MJSD"
    if len(s) >= 11:
        return "MONTHLY"
    return "Qtr(" + ",".join(map(str, months)) + ")"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", help="comma-separated list, e.g. ARCC,MAIN,MO")
    ap.add_argument("--html", help="path to HTML report with a UNIVERSE array")
    ap.add_argument("--out", default="income_backtest", help="output base name")
    args = ap.parse_args()

    if args.html:
        UNI = parse_html_tickers(args.html)
    elif args.tickers:
        UNI = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        ap.error("need --tickers or --html")
    print(f"Parsed {len(UNI)} instruments", flush=True)

    results = []
    for tkr in UNI:
        print("  fetching", tkr, flush=True)
        d = fetch(tkr)
        if "error" in d:
            results.append({"ticker": tkr, "error": d["error"]})
            continue
        price = d["price"]
        divs = d["divs"]
        # tz-aware cutoff: dividend index carries America/New_York
        tz = getattr(divs.index, "tz", None)
        now = pd.Timestamp.now(tz=tz) if tz else pd.Timestamp.now()
        cutoff = now - pd.Timedelta(days=365)
        ttm = float(divs[divs.index >= cutoff].sum()) if len(divs) else 0.0
        yld = (ttm / price * 100) if price else 0.0
        recent = divs[divs.index >= (now - pd.Timedelta(days=730))]
        pmonths = sorted({int(x.month) for x in recent.index})
        bt = backtest(d["hist"], divs)
        h3 = hold3y(d["hist"]["Close"].dropna(), divs)
        results.append({
            "ticker": tkr,
            "price": round(price, 2) if price else None,
            "ttm_div": round(ttm, 4),
            "live_yield": round(yld, 2),
            "pay_months": pmonths,
            "n_exdiv_2y": int(len(recent)),
            "backtest": bt,
            "hold3y": h3,
        })
        time.sleep(0.4)

    ok = [r for r in results if "error" not in r]
    err = [r for r in results if "error" in r]
    ranked = sorted(ok, key=lambda r: r["live_yield"], reverse=True)

    out_json = Path(args.out + ".json")
    out_json.write_text(json.dumps({
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "count": len(ok),
        "ranked_by_live_yield": ranked,
        "failed": err,
    }, indent=2, default=str), encoding="utf-8")

    L = []
    L.append(f"# Income Swing Backtest - {dt.datetime.now():%Y-%m-%d} (LIVE)")
    L.append("")
    L.append(f"Universe {len(UNI)} -> priced {len(ok)}, failed {len(err)}")
    L.append("")
    L.append("## Ranked by live yield (highest payer first)")
    L.append("")
    L.append("| # | Ticker | Price | TTM Div | Yield | Cycle | 1Y Med TotRet | %Pos | 3Y Total |")
    L.append("|---|--------|-------|---------|-------|-------|---------------|------|----------|")
    for i, r in enumerate(ranked, 1):
        bt = r["backtest"]; h3 = r["hold3y"]
        bm = f"{bt['median_1y_total']}%" if bt else "n/a"
        bp = f"{bt['pct_positive']}%" if bt else "n/a"
        h3t = f"{h3['total_3y']}%" if h3 else "n/a"
        L.append(f"| {i} | {r['ticker']} | ${r['price']} | ${r['ttm_div']} | **{r['live_yield']}%** | {cyc(r['pay_months'])} | {bm} | {bp} | {h3t} |")
    L.append("")
    L.append("## Highest-yield + swing-quality screen (>=90% positive, >=20% median)")
    L.append("")
    L.append("| Ticker | Yield | Med 1Y | %Pos | Cycle |")
    L.append("|--------|-------|--------|------|-------|")
    for r in ranked:
        bt = r["backtest"]
        if bt and bt["pct_positive"] >= 90 and bt["median_1y_total"] >= 20:
            L.append(f"| {r['ticker']} | {r['live_yield']}% | {bt['median_1y_total']}% | {bt['pct_positive']}% | {cyc(r['pay_months'])} |")
    L.append("")
    L.append("## Cycle-diversified buy plan (LIMIT, step +$0.50 x3)")
    L.append("")
    buckets = {"MONTHLY": [], "JAJO": [], "FMAN": [], "MJSD": [], "OTHER": []}
    for r in ranked:
        c = cyc(r["pay_months"])
        if c in buckets:
            buckets[c].append(r)
        else:
            buckets["OTHER"].append(r)
    order = ["MONTHLY", "JAJO", "FMAN", "MJSD", "OTHER"]
    ptr = {c: 0 for c in order}
    tier = 0
    more = True
    L.append("| Tier | Ticker | Yield | Live$ | Entry Limit (-1.5%) | Cycle |")
    L.append("|------|--------|-------|-------|---------------------|-------|")
    while more:
        more = False
        for c in order:
            lst = buckets.get(c, [])
            if ptr[c] < len(lst):
                r = lst[ptr[c]]
                ptr[c] += 1
                tier += 1
                lim = round(r["price"] * 0.985, 2)
                L.append(f"| {tier} | {r['ticker']} | {r['live_yield']}% | ${r['price']} | ${lim} | {c} |")
                more = True
    L.append("")
    L.append("## Caveats")
    L.append("- Live yields = TTM dividends / last price via yfinance.")
    L.append("- Backtest = weekly-entry 1y hold, price + realized divs, no DRIP/tx costs.")
    L.append("- 3Y total = price return + sum of divs over trailing 3y / start price (realized, not forward).")
    L.append(f"- Failed fetches ({len(err)}): " + (", ".join(r["ticker"] for r in err) or "none"))
    L.append("")
    Path(args.out + ".md").write_text("\n".join(L), encoding="utf-8")
    print("WROTE", args.out + ".json", "and", args.out + ".md")


if __name__ == "__main__":
    main()
