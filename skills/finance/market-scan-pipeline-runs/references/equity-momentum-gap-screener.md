---
name: equity-momentum-gap-screener
description: gap_rvol_screener.py (new-config equity momentum layer) — filters, output, $2–20 band extraction, single-pass combined backtest recipe.
---

# Equity Momentum Gap / Relative-Volume Screener

`gap_rvol_screener.py` (home dir `C:\Users\victo`) is the **new-config equity
momentum screen** layered on top of `universal_premarket_scan`'s universe. It
finds everything gapping up with elevated relative volume, across ALL asset
classes, any price.

## What it does
- Reuses `universal_premarket_scan.ASSET_UNIVERSE` + `CRYPTO_YF_SYMBOLS` and
  `blogwatcher_integration.fetch_live_catalysts` (per-symbol news alignment +
  regime-shift risk).
- Default filters: `gap_up_pct >= 1.0%`, `vol_ratio >= 1.5×`, `vol_vs_prevday >=
  1.0×`, news=any.
- Run: `python3 gap_rvol_screener.py` (all classes + news).

## Output
- `gap_screener_results_latest.json` — top-level `{scan_type, scan_timestamp,
  filters, regime_shift_risk, candidate_count, candidates}`.
- `gap_screener_report.md`.
- Candidate keys of interest: `symbol, name, category, price, gap_up_pct,
  vol_ratio (20d), vol_ratio_50d, rsi, ema20/50/200, vwap, vwap_dist_pct,
  score`.
- **Category normalization:** screener emits `small_cap` / `micro_cap` (NOT the
  scan's `US_SMALL_CAP` / `US_MICRO_CAP`). Filter on `small_cap`/`micro_cap`.

## $2–20 USD band extraction (user's standing lead order)
```python
import json
d = json.load(open("gap_screener_results_latest.json"))
stocks = [c for c in d["candidates"]
          if c.get("category") in ("small_cap", "micro_cap")]
stocks.sort(key=lambda c: c.get("price", 0))
for c in stocks:
    p = c.get("price", 0)
    band = "2-20" if 2 <= p <= 20 else ("<$2" if p < 2 else ">$20")
    print(f"{c['symbol']:8s} ${p:8.4f} {band:5s} "
          f"gap={c.get('gap_up_pct')} rvol50={c.get('vol_ratio_50d')} "
          f"rsi={c.get('rsi')} score={c.get('score')}")
```
Caveat: under the STOCK SCAN HARD-GATE (≥4× 50d vol for longs), today's
candidates' `vol_ratio_50d` was ~0.02–0.23× — so they FAIL the gate and are
momentum watches, not tradeable. A zero-stock qualified result is intended.

## Single-pass combined backtest (user: "backtest them all in one")
Build ONE `go_setups_tmp.json` covering the gate GOs + every gap-screen stock,
then run `backtest_go_setups.py` once (it dedups by `(sym, side)` across the
`swing`/`day` arrays and uses `s.get("yf", s["sym"])` as the yfinance ticker —
suffix `=X`/`=F`/`-USD`/`^` as needed):
```json
{"swing": [], "day": [
  {"sym": "USDJPY", "side": "LONG", "yf": "USDJPY=X", "cat": "forex"},
  {"sym": "GLBS",   "side": "LONG", "yf": "GLBS",     "cat": "micro_cap"},
  {"sym": "GC",     "side": "SHORT","yf": "GC=F",     "cat": "commodities"}
]}
```
`backtest_go_setups.py` writes `backtest_go_results.json` (per-symbol PF, avgR,
win rate, max DD). PF≥1.0 is TEST 1 of the 3-test proof bar only — not
GREEN_PROVEN.
