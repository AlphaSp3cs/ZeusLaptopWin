# Backtested Sector / Factor Strategy Research (condensed, 2026-08-05)

## 1. Short-term mean reversion (tactical entry filter)
Source: arXiv "Sector Rotation by Factor Model and Fundamental Analysis", 2002–2022.
| Horizon | Ann return | Sharpe |
| 5d  | −0.6% | −0.06 |
| 10d | +2.9% | +0.33 |
| 25d | +6.9% | +0.78 |
| 30d | +8.8% | +0.87 |  ← peak
| 40d | −3.1% | −0.34 |
| 45d | −6.9% | −0.84 |
Takeaway: 25–30d reversal is the sweet spot; anything >40d inverts. Use as a
contrarian entry timing filter on top of a fundamental long thesis, NOT a system.

## 2. Sector rotation by Fama-French 5-factor alpha
Source: City University London, "US Sector Rotation with Five-Factor FF Alphas".
- Long-only FF5 sector rotation Sharpe ≈ 4× buy-and-hold S&P 500.
- With recession-state accounting, Sharpe ≈ 10× buy-and-hold.
- Mechanism: rank sectors by FF5 alpha / 6-month relative strength, hold top 3–5.
- Literature table (1970s–2010s) consistently: rotation beats buy-and-hold;
  alpha-based rotation more stable than rate-of-change; regime switching adds edge.

## 3. Factor consistency by market cycle (Nifty 200, 2007–2025)
Source: Motilal Oswal AMC factor study.
| Cycle | Value | Quality | LowVol | Momentum | Index |
| Bull  | 30.4% | 24.1% | 24.0% | 38.8% | 25.9% |
| Bear  | −48.9%| −27.1%| −25.6%| −42.4%| −41.9%|
| Recov | 45.1% | 41.0% | 37.8% | 39.0% | 36.5% |
"Top-2 performers" counts: Quality 10 (worst: 0), Momentum 8 (worst 5),
Value 9 (worst 6), LowVol 6 (worst 4).
Takeaway: **Quality = most consistent, never worst.** LowVol = best bear defense.
Momentum = best bull, worst bear. For a dividend-income mandate, anchor on
Quality + LowVol, use Momentum/Value as tactical tilts.

## 4. Quality-Value-Momentum (QVM) composite
Source: quant-investing.com backtest (13y, Europe + North America).
- Quality screen: remove low FCF/debt, low ROA, high accruals.
- Value: top 20% by earnings yield / EBIT-to-EV.
- Momentum: top 50% by both 3-month and 6-month price index.
Takeaway: combo beats each alone — closest structural fit to "fundamentals
ultimate" for a long-horizon income investor.

## 5. Low-Volatility-Momentum (LOVM)
Source: alphaarchitect.com. Low-vol provides downside buffer; momentum provides
upside capture. Relevant as a defensive-sleeve construction method.

## Integration implications for OuroTaurus
- Add a **fundamental gating layer** to `universal_premarket_scan.py`: quality
  (FCF/debt, ROA, low accruals) + value (earnings yield/EBIT-EV) + dividend
  durability (payout ratio, 5y div growth) BEFORE technical scoring.
- Add a **sector-rotation ranking** (6m relative strength / FF5 alpha) so the
  scan universe tilts toward leading sectors instead of being static.
- Wire `backtest_go_setups.py` into the orchestrator as a real Phase 3 and enforce
  PF<1.0 = DO-NOT-TRADE, carrying the kill list across runs.
- Wire `blogwatcher_integration.py` RSS sentiment into scan/gate/report per the
  standing instruction (note coverage is BTC/ETH/SOL only — disclose the gap
  for other assets).
- For the dividend mandate specifically: weight Quality + LowVol factors; treat
  Momentum/Value as overlays, not core.
