---
name: sector-factor-strategy-audit
description: Audit fundamentals; research sector/factor strategies.
---

# Sector Factor & Strategy Audit

Use this skill whenever Victor asks to (a) "study the most profitable backtested
strategies for each sector," (b) "see if any of those feel gaps in our workflow,"
(c) "make sure our fundamentals are ultimate," or (d) integrate value/quality/
momentum/low-vol or sector-rotation logic into the scan or gate.

## Standing context (load every time)
- Investing goal = **long-horizon dividend compounding for monthly income** (DRIP,
  buy-and-hold, add on dips), NOT trading. Buy plans must be executable docs with
  explicit limit prices. A "fundamentals ultimate" mandate is non-negotiable.
- Every market scan MUST integrate `blogwatcher_integration.py` RSS sentiment
  (regime-shift risk belongs in every report). It only covers BTC/ETH/SOL, so for
  other assets say the per-symbol layer is unavailable rather than implying coverage.
- Victor requires **backtest validation before trade tickets**: a gate GO proves
  risk mechanics, not edge. PF < 1.0 = do not trade. Want positive/negative
  expectancy split, an explicit DO-NOT-TRADE list, and that kill list carried
  across runs and re-checked when the scanner re-emits a rejected symbol.
- Tooling: on this Windows host `search_files`/rg errors with "IO error: file not
  found" for `C:\Users\victo` paths even when files exist. **Use terminal
  `grep -niE` / `find` instead.** (Recursive grep also times out — scope to a subdir.)

## Workflow audit checklist (run these in order)
1. **Map the real pipeline.** `run_universal_workflow.py` = 5 phases:
   scan (`universal_premarket_scan.py`) → gate (`enhanced_trade_gate.py`) →
   quant report (`make_universal_report.py`) → MT5 exec/monitor
   (`mt5_dual_executor.py`). Confirm which phases actually execute.
2. **Check for fundamentals — the #1 gap.** Grep the scan/gate for
   `pe_ratio|dividend|payout|fcf|earnings.yield|ebit|book|roe|roic|gross.margin|
   debt.equity`. If only macro-event mentions return, the workflow is
   **technical-only** (RSI/ATR/VWAP/EMA/volume scoring) with zero fundamental
   gating. Record this as the headline gap.
3. **Verify blogwatcher RSS is wired in.** Grep `blogwatcher|rss|sentiment|macro`
   inside `universal_premarket_scan`/`enhanced_trade_gate`/`make_universal_report`.
   If nothing returns, the standing instruction is NOT being honored — flag it.
4. **Verify the backtest phase is connected.** The orchestrator docstring may claim
   a "BACKTEST VALIDATION" phase, but check whether the code actually calls
   `backtest_go_setups.py` (backtests current GO symbols over 10y with
   RSI/ATR/VWAP). If disconnected, either wire it or stop advertising it.
5. **Confirm the kill list / PF<1.0 enforcement** is persisted across runs and
   re-checked on re-emit. See `references/ourotaurus_architecture.md`.

## What "profitable per sector" actually means (research)
Backtested evidence, not opinion — condensed in `references/factor_sector_research.md`:
- **Short-term mean reversion** peaks at ~30-day (Rev_30D ≈ 8.8% ann, Sharpe 0.87;
  dies/negative past 40d). Useful as a tactical entry filter, not a core thesis.
- **Sector rotation by Fama-French 5-factor alpha**: long-only FF5 rotation Sharpe
  ≈ 4× buy-and-hold; with recession accounting ≈ 10×. Rotate into top-3–5 sectors
  by 6-month relative strength / FF5 alpha.
- **Factor consistency (Nifty 200 study)**: Quality = most consistent (top-2 ten
  times, never worst); Momentum strongest in bull (38.8% vs 25.9% index); Low-Vol
  best downside protection in bear (Quality −27% / LowVol −26% vs Momentum −42% /
  Value −49%). Income mandate → weight Quality + Low-Vol, use Momentum/Value as
  tactical overlays.
- **Quality-Value-Momentum (QVM)**: quality (FCF/debt, ROA, low accruals) +
  value (earnings yield / EBIT-EV top 20%) + momentum (3m&6m top 50%) beats each
  alone. Closest fit to Victor's "fundamentals ultimate" goal.

## Per-sector factor guidance
- **Defensive (Utilities, Staples, Healthcare)**: Quality + Low-Vol dominate;
  momentum weak. Fit the dividend/income mandate directly.
- **Cyclical (Tech, Industrials, Materials, Financials)**: Momentum + Value work
  best, especially post-recovery. Add a quality floor to avoid value traps.
- **Sector rotation layer** (currently absent): add FF5-alpha / 6m relative-
  strength ranking to rotate, not just pick within a fixed universe.

## Deliverable shape for this class of task
Produce a gap analysis that names: (1) the fundamental blind spot, (2) the RSS-
sentiment wiring gap, (3) the backtest-phase disconnect, (4) missing factor-
rotation layer, and (5) an actionable integration plan (which file, which field,
which gating rule). Keep it in plain terminal-readable prose, no markdown tables.

## "What companies make X / which is best to buy and hold" — research pattern
Victor periodically asks industry-mapping questions ("what companies make RAM and
which is best to buy and hold?"). This is a fundamentals-audit task, not a scan.
Reusable pattern:
1. MAP the players — pull market-share / oligopoly structure (web_search:
   "largest <industry> manufacturers 2026 market share"). Name the top 3-5 and
   their shares; note any not US-tradable (e.g. CXMT/ChangXin for DRAM).
2. PULL US-tradable tickers and key stats via yfinance: last price, PE,
   profit/operating margins, market cap. For ETFs use yield/ER/sector weights.
3. RANK against the ACTUAL mandate (see pitfall below), not generic "best."
4. FLAG the mandate conflict explicitly if the names don't fit (growth/cyclical
   with ~0% yield vs the dividend-compounding core).

### PITFALL — mandate conflict on "buy and hold" growth/cyclical names
Victor's standing mandate is LONG-HORIZON DIVIDEND COMPOUNDING FOR MONTHLY INCOME
(DRIP, buy-and-hold, add on dips) — NOT trading, NOT pure capital-gains bets.
When he asks "which is best to buy and hold" for a stock that is a cyclical or
AI-supercycle GROWTH name with ~0% dividend yield, the correct answer is NOT to
rank it like SCHD/VYM. You MUST:
- State the yield honestly (many AI/memory/semis pay <0.1% — they don't compound
  via dividends, only via price if the cycle holds, and they can cut 50% in a
  down-cycle).
- Recommend it only as a SATELLITE (a few % of book), explicitly NOT a replacement
  for the income core (SCHD/VYM/O/PEP/KO).
- Lead with the income-core names when the question is really "where do I compound."
Example applied: RAM/DRAM makers (Samsung ~38%, SK Hynix ~29%/~58% HBM, Micron
~22%) are an AI-supercycle play; Micron yields ~0.07%. Best of the three for
buy-and-hold growth = SK Hynix (HBM leader, cheapest fwd multiple) or Micron
(US-domiciled, HBM sold out through 2026) — but both are satellites, not core.
Domain detail in `references/industry_maps.md` (DRAM/RAM maker map + ranking).

### DATA-QUALITY CAVEAT — yfinance `dividendYield` is unreliable
The `info['dividendYield']` field frequently returns WRONG-SCALE values
(observed: Samsung 241%, WDC 11%, MU 6% — only MU was near-correct). Do NOT state
a yield from that field alone. Cross-check via web search / macrotrends /
dividendinvestor, or compute from the last 4 dividend payments x 4 / price.
State the verified number, not the raw field. Also `info` 404s for broad ETFs
(SCHD/VYM) — only yield/PE survive; use web sources for their fundamentals.

## Linked references
- `references/ourotaurus_architecture.md` — pipeline map, key files, confirmed gaps.
- `references/factor_sector_research.md` — condensed backtested factor/sector findings.
- `references/industry_maps.md` — reusable industry-player maps (e.g. DRAM/RAM
  makers, their shares, US-tradable tickers, and buy-and-hold ranking notes).
