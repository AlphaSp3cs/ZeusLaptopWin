# Crypto bottom study — WIDE v2 recipe (validated 2026-08-08)

Supersedes the top-250 recipe in `crypto_bottom_research.md` for coverage. The
scoring formula, price cross-check and proof bar there still apply verbatim —
this file records what changed when the universe was widened to 500 and what
the second independent run measured.

## Universe widening: top 500, and THREE exclusion classes (not one)
`coins/markets` pages 1-2 at per_page=250 = 500 rows. The original recipe only
excluded gold tokens. That is not enough at 500 names — you must strip:

- **stablecoins** — USDT/USDC/DAI/USDE/FDUSD/PYUSD/USDS/RLUSD/FRAX/... A
  stablecoin can never be "down 90% from ATH", but depegged//retired ones can
  read as deep-drawdown candidates.
- **gold tokens** — XAUT/PAXG/XAUM/KAU. Gold's mean reversion, not crypto.
- **wrapped assets and liquid-staking receipts** — WBTC/WETH/STETH/WSTETH/
  WEETH/CBBTC/RETH/JITOSOL/MSOL/BNSOL/EZETH/RSETH/TBTC/BTCB/... These have NO
  independent price; they are a second copy of BTC/ETH/SOL. Including them
  double-counts the majors in the base-rate pool and pollutes the leaderboard.

Funnel measured 2026-08-08: 500 fetched -> 478 tradable -> 48 liquid
(vol>=$30M AND mcap>=$200M) -> 34 candidates (dd<=-70% AND >=12mo since ATH).
Note how brutal the liquidity floor is: 478 -> 48. Do not loosen it to pad the
list.

## The squatted-yfinance-feed list is STABLE across runs — always cross-check
Same four names failed the `abs(yf_last/cg_price - 1) > 0.15` check on both the
2026-08-07 and 2026-08-08 runs:
APT (yf $0.000131 vs real $0.579), UNI ($0.000163 vs $3.96),
POL ($0.0082 vs $0.0748), SUI ($0.0003 vs $0.671).
Also insufficient history: TRUMP and TAO (1 bar), PENGU (52 bars), PEPE (119
bars), GRAM (no post-ATH history). Require >=500 bars.
Without the cross-check these render as "-99.99% from ATH" — the most
attractive-looking rows in the entire table. The screen actively promotes its
own worst data.

## Second independent confirmation: the trend rule fails again
Re-run with a 60/40 IS/OOS split and a 200-run permutation test over the 12
names scoring >=50. **Zero GREEN_PROVEN, again.** Notable results:

- DOGE IS PF 6.36 / +2367% -> OOS PF 0.70 / -41%. The canonical overfit shape.
- LINK (IS 3.07 / OOS 1.85) and BCH (IS 1.47 / OOS 1.61) both clear the IS+OOS
  PF>=1 bar but have permutation p = 0.18 and 0.33. **This is exactly why the
  permutation test is mandatory** — without it these two would have been
  published as GREEN on a two-test bar. Big PF that clears IS and OOS can still
  be a random walk.
- INJ and ONDO returned n=0 OOS trades -> NO_EVIDENCE, not a pass.

Verdict ladder that worked:
```
if n_oos < 5:                              NO_EVIDENCE_OOS
elif IS.pf >= 1 and OOS.pf >= 1 and p<.05: GREEN_PROVEN
elif IS.pf >= 1 and OOS.pf >= 1:           AMBER_NOT_SIGNIFICANT
else:                                      RED
```

## Base rates re-measured on the wider pool (25 validated names)
| bucket | 12m med / win | 24m med / win |
|---|---|---|
| <= -90% | **+44.6% / 65.3%** | **+108.9% / 72.3%** |
| -90..-80% | +11.0% / 55.1% | +45.5% / 66.2% |
| -80..-70% | -40.3% / 28.4% | -28.2% / 33.8% |
| -70..-50% | -56.8% / 25.9% | -50.2% / 33.9% |
| -50..-25% | -48.5% / 34.7% | -57.8% / 27.1% |

Direction reproduces the top-250 run but the effect is LARGER on the wider,
de-duplicated pool (12m <=-90% median +44.6% here vs +3.2% before — removing
wrapped/LST duplicates of the majors matters).

**The headline finding, and it is counter-intuitive enough to lead with:** the
-70% to -25% band is where capital dies (12m medians -40% to -57%, win rates
26-35%). "It's down 50%, it's cheap" is measurably the worst trade in crypto.
The cliff is sharp and sits at -90%. The edge is not depth-picking, it is
**depth threshold + patience** (24 months).

## Combine the two layers — this is the only defensible output
Deep enough to be in the paying bucket AND holding a base:
`ath_dd <= -90` AND `base_score >= 50`. On 2026-08-08 exactly two names passed:
NEAR (-92.2%, score 75, low 5.8mo ago) and INJ (-91.5%, score 60, low 4.2mo).
ENA (-94.0%) and ADA (-93.5%) were deep enough but scored 45 with lows ~1.3
months old — "too early", watch not buy.

Score-0 names are the trap: FIL (-99.7%), DOT (-98.5%), FET, BONK, AVAX, SOL,
XRP all printed cycle lows within weeks (FET/BONK/XRP made new lows the day of
the run). SOL at -74.9% sits squarely in the band the base rates say kills you
— being a blue-chip does not exempt it.

## Report shape confirmed again
Bottom line first, in one counter-intuitive sentence. Then: data-integrity
drops -> base-quality leaderboard (with explicit score-0 falling-knife block)
-> backtest table with verdicts -> base-rate table -> two-layer conclusion with
DCA/lump, horizon, invalidation -> DO NOT BUY list -> artifacts.
State "zero GREEN" plainly and call it an accumulation thesis. The user
explicitly values this ("I'm not going to dress up a failed backtest").

## Scripts (C:\Users\victo, regenerate as needed)
`crypto_bottom_universe_v2.py` -> `crypto_base_quality_v2.py` ->
`crypto_bull_backtest_v2.py` (backtest + base rates in one pass; run it
backgrounded, it takes several minutes on 25 names x 200 permutations).
Report: `CRYPTO_BOTTOM_STUDY_<date>.md`.
