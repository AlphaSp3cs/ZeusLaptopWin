#!/usr/bin/env python3
"""
Standing all-sector OPEN SCAN cron runner (self-contained, no agent needed).

Re-runs the full universal pipeline (scan -> gate) at each session open, layers
blogwatcher RSS sentiment + danger-zone gauge (standing rule), and writes a dated
ALLSECTOR_OPEN_YYYYMMDD.md to the home dir. Designed to be the `script` of a
Hermes cronjob so it runs unattended and the x4-relative-volume + gap-up stock
hard-gate (universal_premarket_scan.STOCK_CATEGORIES) automatically catches any
high-volume gap-up equity event when one occurs.

Invoke from the home dir (C:\\Users\\victo):
    python3 standing_open_scan_cron.py
The running user must have yfinance + the pipeline scripts importable.

Exit code 0 = report written. Non-zero = scan or gate failed (stderr captured by
cron for the job log).

NOTE on Windows delivery: CLI/TUI cron jobs are local-only — the report writes to
ALLSECTOR_OPEN_YYYYMMDD.md and the job log; it does NOT push to the terminal. If
notification is wanted, the cronjob must set deliver='telegram'/'all' against a
connected gateway.
"""
import os, sys, json, subprocess
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
# This script may live in the skill's scripts/ dir; the pipeline scripts live in
# the home dir. Resolve HOME and add it to sys.path so imports work either way.
HOME = os.path.expanduser("~")
PIPELINE_DIR = HERE if os.path.exists(os.path.join(HERE, "run_universal_workflow.py")) else HOME
if PIPELINE_DIR not in sys.path:
    sys.path.insert(0, PIPELINE_DIR)

import universal_premarket_scan as ups   # noqa: E402
import enhanced_trade_gate as gate        # noqa: E402
import blogwatcher_integration as bw      # noqa: E402

GAUGE_JSON = os.path.join(HOME, ".hermes", "gauges", "danger_zone", "latest_gauge.json")


def _run(cmd):
    return subprocess.run(cmd, cwd=PIPELINE_DIR, capture_output=True, text=True)


def run():
    # 1) Scan + gate via the orchestrator (handles namespacing correctly).
    r1 = _run([sys.executable, "run_universal_workflow.py", "--scan-only"])
    r2 = _run([sys.executable, "run_universal_workflow.py", "--gate-only"])
    if r1.returncode != 0 or r2.returncode != 0:
        return (f"SCAN/GATE FAILED rc1={r1.returncode} rc2={r2.returncode}\n"
                f"{r1.stderr[-500]}\n{r2.stderr[-500]}")

    with open(os.path.join(PIPELINE_DIR, "universal_scan_results_latest.json")) as f:
        scan = json.load(f)
    with open(os.path.join(PIPELINE_DIR, "enhanced_setups_day_latest.json")) as f:
        day = json.load(f)

    # 2) News + gauge (standing rule).
    syms = set()
    for cat in scan.get("categories", {}).values():
        for a in cat.get("assets", []):
            syms.add(a.get("symbol", "").upper())
    syms.update(["BTC", "ETH", "SOL", "AVAX", "DOT", "LINK", "AAPL", "NVDA", "SPY", "QQQ", "GLD", "TLT"])
    try:
        cat = bw.fetch_live_catalysts(sorted(syms))
        rsr = cat.get("regime_shift_risk", "UNKNOWN")
        arts = cat.get("total_articles", 0)
        hits = {k: v for k, v in cat.get("symbol_news", {}).items() if v and v.get("headlines")}
    except Exception as e:
        rsr, arts, hits = "UNKNOWN", 0, {}
        cat = {"error": str(e)}
    g = json.load(open(GAUGE_JSON)) if os.path.exists(GAUGE_JSON) else None

    # 3) Build report.
    now = datetime.now(timezone.utc)
    date_stamp = now.strftime("%Y%m%d")
    run_label = now.strftime("%Y-%m-%d %H:%M UTC")
    out_path = os.path.join(PIPELINE_DIR, f"ALLSECTOR_OPEN_{date_stamp}.md")

    L = []
    L.append(f"# ALL-SECTOR OPEN SCAN — {run_label}\n")
    L.append(f"Gauge: {g.get('gauge_value') if g else 'n/a'} — {g.get('interpretation') if g else ''}  |  "
             f"Blogwatcher regime risk: {rsr} ({arts} articles)\n")
    L.append(f"Universe: {scan.get('total_assets_scanned')} assets | "
             f"qualified LONGs {scan.get('total_qualified_longs')} / SHORTs {scan.get('total_qualified_shorts')}\n")
    L.append("---\n")

    s = day["summary"]
    L.append(f"## DAY GATE — LONGs GO={s['go_longs']}/{s['total_longs']}  "
             f"SHORTs GO={s['go_shorts']}/{s['total_shorts']}\n")
    gos = [t for t in day["longs"] + day["shorts"] if t["validation"]["verdict"] == "GO"]
    gos.sort(key=lambda t: (t["category"], t["side"]))
    if gos:
        L.append("| Side | Symbol | Class | Name | Entry | Stop | T1 | R:R | Sz% | Rsk% | RSI | News |")
        L.append("|------|--------|-------|------|-------|------|----|-----|-----|------|-----|------|")
        for t in gos:
            m = t["validation"]["metrics"]
            e = m.get("real_entry") or t.get("entry_price")
            sl = t.get("stop_loss")
            t1 = m.get("real_t1") or t.get("take_profit_1")
            sym = t["symbol"].upper()
            news = f"{hits[sym].get('alignment')}/{hits[sym].get('impact')}" if sym in hits else ""
            L.append(f"| {t['side']} | {t['symbol']} | {t['category']} | {t.get('name','')} | "
                     f"{e} | {sl} | {t1} | {m.get('rr')} | {m.get('notional_pct')}% | "
                     f"{m.get('pct_risk')}% | {t.get('rsi')} | {news} |")
    else:
        L.append("No DAY GO setups.\n")

    # Stock hard-gate status (the point of this cron).
    L.append("\n## STOCK HARD-GATE (x4 50d vol + gap-up longs)\n")
    stocks = []
    for cat_name, cat in scan.get("categories", {}).items():
        if cat.get("category") in ups.STOCK_CATEGORIES:
            for a in cat.get("assets", []):
                stocks.append(a)
    if stocks:
        stocks.sort(key=lambda x: (x.get("vol_ratio_50", 0) or 0), reverse=True)
        L.append(f"{len(stocks)} equities scanned. Top by 50d vol ratio:")
        L.append("| Symbol | Name | vol50x | gap% | rsi | price |")
        L.append("|--------|------|--------|------|-----|-------|")
        for a in stocks[:8]:
            L.append(f"| {a.get('symbol')} | {a.get('name')} | {a.get('vol_ratio_50')} | "
                     f"{a.get('gap_up_pct')} | {a.get('rsi')} | {a.get('price')} |")
        maxv = max((a.get("vol_ratio_50", 0) or 0) for a in stocks)
        L.append(f"\nHighest 50d vol ratio today: {maxv:.2f}x (threshold {ups.VOL_RATIO_FLOOR}x). "
                 + ("No gap-up high-volume stock event." if maxv < ups.VOL_RATIO_FLOOR
                    else "GAP-UP STOCK EVENT PRESENT — review longs above."))
    else:
        L.append("No equities scanned.\n")

    L.append(f"\n*Standing rule applied: blogwatcher RSS + danger-zone gauge integrated. "
             f"Stock filter: >= {ups.VOL_RATIO_FLOOR}x 50d vol, longs gap-up >= {ups.GAP_UP_MIN_PCT}%.*")
    with open(out_path, "w") as f:
        f.write("\n".join(L))
    maxv = max((a.get("vol_ratio_50", 0) or 0) for a in stocks) if stocks else 0
    return f"OK -> {out_path} | gauge {g.get('gauge_value') if g else 'n/a'} rsr {rsr} | GO {len(gos)} | top-stock-vol {maxv:.2f}x"


if __name__ == "__main__":
    print(run())
