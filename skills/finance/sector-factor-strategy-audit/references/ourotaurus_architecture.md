# OuroTaurus Universal Workflow — Architecture & Confirmed Gaps

## Pipeline (run_universal_workflow.py)
1. **PHASE 1 UNIVERSAL SCAN** — `universal_premarket_scan.py` (858 lines).
   Feeds `universal_scan_results_YYYYMMDD_HHMMSS.json` + `_latest` symlink.
   Scans ETFs, stocks, bonds, futures, rates, forex, commodities, indices, crypto.
2. **PHASE 2 ENHANCED TRADE GATE** — `enhanced_trade_gate.py` (777 lines).
   `process_all_setups(scan_data, profile, account_equity=100000)` for swing+day.
   Writes `enhanced_setups_swing_latest.json` / `_day_latest.json`.
   Has SECTOR_PROFILES (per-asset ATR mult, rr_floor, risk_pct, concentration_cap)
   + LIQUIDITY_FLOORS. Merges broker + net-R:R back into scan payload.
3. **PHASE 3 QUANT REPORT** — `make_universal_report.py` (493 lines).
   Reads `universal_scan_results_latest.json` → Desktop + OneDrive txt.
4. **PHASE 4 MT5 DUAL EXECUTION** — `mt5_dual_executor.py` (765 lines).
   FTMO left + Capital.com right. Gracefully no-ops if MT5 not installed.
5. **PHASE 5 POSITION MONITORING** — same executor, trailing/breakeven stubs.

## Scan scoring (confirmed technical-only)
`scan_asset_class` scores longs/shorts on: RSI(<35 / <45 oversold), VWAP distance,
EMA20 reclaim/reject, EMA200 trend, volume ratio. Qualification gate:
`rr >= 2.0 AND score >= 0.5 AND atr > 0`. Stop = max(price*0.02, 1.5*ATR);
TP1 = 2.5×stop, TP2 = 3.5×stop. Crypto uses same path via `scan_crypto`.
**No P/E, dividend, FCF, earnings yield, ROE, book value, debt/equity anywhere.**

## Gate sector profiles (excerpt)
Energy/Metals/Index/ETF/Stock: rr_floor 2.0 (swing)/1.5 (day), atr_stop_mult
1.5 (swing)/1.0 (day), risk_pct 0.01/0.005, concentration_cap 0.10–0.25.
US micro-cap: atr_stop_mult 2.5 swing, concentration_cap 0.03 (tightest).
All risk-management, zero fundamental gating.

## Confirmed gaps (audit, 2026-08-05)
1. **Fundamental blind spot (HEADLINE).** Entire pipeline is RSI/ATR/VWAP/EMA/
   volume. Victor's "fundamentals must be ultimate" mandate is unmet — no
   quality/value/dividend/fcf screen exists. Contradicts dividend-income goal.
2. **Blogwatcher RSS not wired in.** Grep for blogwatcher|rss|sentiment|macro in
   scan/gate/report returned nothing. Standing instruction honored in name only.
3. **Backtest phase disconnected.** Orchestrator docstring claims "PHASE 3 BACKTEST
   VALIDATION → backtest_report.json" but main() never calls `backtest_go_setups.py`.
   `backtest_go_setups.py` DOES exist and works (RSI/ATR/VWAP, 10y window, computes
   win_rate/expectancy/profit_factor → `backtest_go_results.json`); it's just orphaned.
4. **No factor-rotation layer.** Scan is universe-static; no FF5-alpha or 6m
   relative-strength sector rotation. Gate is per-asset risk only.
5. **No persistent kill list / PF<1.0 enforcement across runs.** Need to verify a
   carried DO-NOT-TRADE list that re-checks re-emitted symbols (Victor requirement).

## Key file paths (Windows)
C:\Users\victo\universal_premarket_scan.py
C:\Users\victo\enhanced_trade_gate.py
C:\Users\victo\make_universal_report.py
C:\Users\victo\mt5_dual_executor.py
C:\Users\victo\backtest_go_setups.py
C:\Users\victo\blogwatcher_integration.py
C:\Users\victo\run_universal_workflow.py
C:\Users\victo\.hermes\workflow-gap-analysis.md  (STALE — July 10, crypto/Kraken scope)
