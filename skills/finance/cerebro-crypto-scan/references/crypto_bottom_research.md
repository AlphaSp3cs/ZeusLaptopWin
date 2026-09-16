# Crypto "historically bottomed out" research + bull backtest

Class of request: "find crypto that has bottomed / is most undervalued, then
backtest a long bull buy." This is NOT the cryptoweekend momentum scan — it is a
drawdown/accumulation study. Recipe below was validated 2026-08-07.

## 1. Universe (CoinGecko, not yfinance)
`coins/markets` vs_currency=usd, order=market_cap_desc, per_page=250, pages 1-2,
`price_change_percentage=24h,7d,30d,1y`. Keep `total_volume >= 30e6` and
`market_cap >= 2e8`. Candidates = `ath_change_percentage <= -70` AND
`months_since_ath >= 12`. Sleep 3-4s between pages (rate limit).

### Exclude three non-crypto classes BEFORE filtering (added 2026-08-08)
Tag and drop by symbol set, or they pollute the leaderboard:
- **stablecoins** — USDT/USDC/DAI/USDE/FDUSD/PYUSD/USDS/FRAX/... (no drawdown)
- **gold tokens** — XAUT/PAXG/XAUM/KAU (gold's mean-reversion, not crypto)
- **wrapped / LST receipts** — WBTC/WETH/STETH/WSTETH/WEETH/CBBTC/RETH/JITOSOL/
  MSOL/BNSOL/TBTC/BTCB/... (no independent price; they mirror the host asset)

Scale check at top-500 (2026-08-08): 500 fetched -> 478 tradable -> 48 liquid
-> 34 candidates. Going 500 deep instead of 250 mostly adds illiquid noise the
volume/mcap floors then cut. Top-250 is a defensible default; go 500 only when
the user explicitly asks for full coverage.

## 2. MANDATORY price cross-check before any yfinance work
For each candidate, download `<BASE>-USD` 10y daily and compare the last close to
the CoinGecko `current_price`. Drop if `abs(ratio-1) > 0.15`.
Known bad feeds seen: UNI, APT, POL, TIA, ARB. TAO has too little history (<500
bars) for a 10y study. Skipping loudly is the correct behaviour — say which names
were excluded and why.

## 3. Base-quality score (separates BOTTOM from FALLING KNIFE)
Per surviving name compute, off the cycle low made AFTER the ATH:
  off_low = last/low - 1
  px > MA200, px > MA50
  ma200_slope90 = MA200[-1]/MA200[-90] - 1
  higher_low = min(last 90 closes) > low * 1.15
  months_off_low
score = 100 * (0.30*(off_low>0.20) + 0.20*(px>MA200) + 0.15*(px>MA50)
               + 0.15*(slope>0) + 0.10*higher_low + 0.10*(months_off_low>6))
A name scoring 0 (FIL, DOT, AVAX, LTC on 2026-08-07) printed its low within weeks
— explicitly put it on a DO-NOT-BUY list, however cheap it looks.

## 4. Backtest — expect the trend rule to FAIL the proof bar
Rule tested: long when close>MA200 and close>MA50 and MA200 90d slope>0; exit on
ATR(14)x3 trailing stop, close<MA200, or 3 closes<MA50; 15bp/side.
Bookkeeping per `trading-backtest-integrity`: enter at bar-k close, exits only
evaluated from bar k+1.
Result 2026-08-07 (NEAR / LINK / INJ / DASH): NONE passed the 3-TEST PROOF BAR.
NEAR and INJ had **zero OOS trades** — the 2024-26 bear never triggered the entry.
Permutation p-values all >> 0.05.
LESSON: in a deep-bear OOS window a trend-following rule produces n=0, which is
not a pass and not a fail — report it as no evidence, never as "GREEN". Add a
permutation test (shuffle daily returns ~200x, count sims beating the real total)
because a big IS PF on 15-30 trades is routinely indistinguishable from noise.

Re-run 2026-08-08 over 12 names scoring >=50: again ZERO GREEN. New failure
mode worth naming — **AMBER_NOT_SIGNIFICANT**: LINK (IS PF 3.07 / OOS 1.85) and
BCH (1.47 / 1.61) BOTH cleared the IS+OOS PF>=1 bar, and both died on the
permutation test (p=0.18, p=0.33). Without the permutation leg they would have
shipped as GREEN. Encode the verdict ladder explicitly:
  OOS n < 5              -> NO_EVIDENCE_OOS   (INJ, ONDO, VIRTUAL had n=0-3)
  IS or OOS PF < 1       -> RED
  PF bar OK, p >= 0.05   -> AMBER_NOT_SIGNIFICANT
  PF bar OK, p < 0.05    -> GREEN_PROVEN
DOGE is the canonical overfit exhibit: IS PF 6.36 / +2367%, OOS PF 0.70 / -41%.


## 5. What actually has a measurable signal: the drawdown base rate
Pool forward returns across ~24 real-price majors, bucketed by
`close/cummax(close)-1`, horizons 6/12/24 months. Measured medians and win rates:

  bucket    12m med   12m win   24m med   24m win
  <= -90%    +3.2%     51.9%     +35.2%    61.5%
  -90/-80    -1.6%     48.9%     +20.0%    59.2%
  -80/-70   -27.5%     31.6%     -36.1%    31.4%
  -70/-50   -26.2%     38.1%     -54.5%    33.7%
  -50/-25   -20.4%     39.8%     -43.9%    29.7%

Re-measured 2026-08-08 over 25 validated names (n ~4k-16k per cell). Same
SHAPE, materially stronger extreme — quote these as the current numbers:

  bucket    12m med   12m win   24m med   24m win
  <= -90%   +44.6%     65.3%    +108.9%    72.3%
  -90/-80   +11.0%     55.1%     +45.5%    66.2%
  -80/-70   -40.3%     28.4%     -28.2%    33.8%
  -70/-50   -56.8%     25.9%     -50.2%    33.9%
  -50/-25   -48.5%     34.7%     -57.8%    27.1%

Two independent runs agreeing on the shape is the real finding: the sign flip
sits at -90%, and the -80/-25 band is negative on every horizon in both runs.

Non-obvious and worth re-quoting: the -70%..-25% zone is where capital dies. Only
the <=-90% extreme has a positive median, and only on a 24-month horizon.
Caveat honestly: overlapping windows inflate n; and a single asset's <=-90% days
usually cluster in ONE bear episode, so per-name stats are suggestive, not proven.

Also test lump-sum vs weekly DCA from the first sustained <=-90% day. NEAR
(entry 2022-11-12): lump -27.8% @12m / +247.4% @24m; weekly DCA -16.5% / +301.8%.
DCA beat lump on both horizons and cut 12-month pain by ~11 points.

## 6. Output shape the user wants
Depth leaderboard -> base-quality score -> backtest table with explicit verdicts ->
base-rate table -> ONE named conclusion with vehicle, method (DCA vs lump),
horizon, invalidation level (a close under the cycle low), sizing note, and a
DO-NOT list. State plainly when nothing passed the proof bar — call it an
accumulation thesis, not a proven trade. Do not dress a failed backtest up.

## 7. Follow-on: the user will ask for an executable ladder
This request almost always continues into "build the DCA ladder with tranche
sizes and invalidation wired in, remind me when to buy". See
`crypto_dca_ladder_execution.md` for the validated ladder shape, the
weekly-close invalidation rule, and the Windows-toast reminder pattern (CLI has
no message channel — a `deliver='origin'` cron job CANNOT reach the terminal).

## Scripts used (live in C:\Users\victo, regenerate as needed)
v1: cg_bottom_universe.py, crypto_base_quality.py, crypto_bull_backtest.py,
crypto_dd_baserate.py -> CRYPTO_BOTTOM_RESEARCH_<date>.md
v2 (top-500 + class exclusions + permutation, 2026-08-08):
crypto_bottom_universe_v2.py, crypto_base_quality_v2.py,
crypto_bull_backtest_v2.py -> CRYPTO_BOTTOM_STUDY_<date>.md
Ladder: dca_ladder_check.py + ~/.hermes/scripts/dca_ladder_cron.sh
