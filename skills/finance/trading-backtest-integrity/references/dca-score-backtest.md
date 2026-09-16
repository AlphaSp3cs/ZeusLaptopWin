# DCA / Score-Index Backtest Integrity

Specific integrity traps that ONLY appear when the strategy is **dollar-cost-averaging**
(buy a fixed $ each period) or when you **unify scores across asset classes**. The
FTMO single-position sim in the main SKILL.md does not cover these.

## 1. The DCA Sharpe-distortion bug (real, caught 2026-08-08)

**Symptom:** every basket — default, equal-weight, oracle — reports a Sharpe in a
tiny band (e.g. 3.9–4.3 across all of them). That uniformity is the tell.

**Cause:** a DCA portfolio's value path is `Σ shares·price` but you keep *adding
cash* every period. If you compute period returns as `value[t]/value[t-1]-1`, the
fresh contribution inflates the denominator every week, so the series looks
unrealistically smooth and the Sharpe is meaningless (and roughly the same for any
basket because all baskets receive the same cash inflow).

**Fix — split the two return concepts:**

- **Sharpe / volatility** → use **time-weighted returns (TWR)**, stripping the
  contribution each period:
  ```
  pre  = Σ shares[b]*price[b][t]          # before this week's cash
  post = pre + weekly_cash (after buying)  # post = Σ shares·price[t]
  r_twr = (post - weekly_cash) / pre - 1   # contribution removed
  ```
  Sharpe = mean(r_twr)/std(r_twr) * sqrt(periods_per_year).

- **Annualized return the investor actually earned** → use **money-weighted IRR**
  (bisection on the weekly rate `w` solving `Σ cash·(1+w)^(weeks-t) = terminal`),
  then annualize `(1+w)^52 - 1`. This correctly goes NEGATIVE when a DCA investor
  loses money (TWR/CAGR-of-TWR can read ~0% while the investor is down).

After the fix the Sharpe spread is honest: default ~0.25, equal-weight ~0.40,
oracle ~1.15. Use TWR for risk, IRR for return — never report one as the other.

## 2. Cross-class score unification (crypto vs dividend)

Two trackers had **non-comparable scales** (crypto "Score" 0.61–2.69 analyst scale;
dividend used yield/discount/RSI). To rank them on ONE 0–100 index:

1. Define per-class **sub-factors**, each mapped to 0–100:
   - crypto: momentum (24h, centered at 50), quality (analyst score normalized),
     catalyst (Clarity-Act beneficiary bonus), whale (recent accumulation flag).
   - dividend: yield (min(y/8%,1)*100), value (100 − % above 52w low),
     safety (100 if dividend-safe else 20), readiness (DCA READY 100 / ACCUM 90 / WATCH 45).
2. **Weight within class** (weights sum to 1 inside each class).
3. Rank globally on the blended 0–100 score.

Do NOT average raw source numbers across classes — the scales are incompatible.
Always normalize sub-factors to 0–100 first.

## 3. Honesty guardrails for a score-index backtester

- **ORACLE ceiling (lookahead):** each run, also backtest the basket of assets with
  the best *realized* full-period return. This is the best achievable with perfect
  hindsight — a research bound, not a signal. Report it next to the real result.
- **BEST-POSSIBLE weights = in-sample overfit ceiling.** If you random-search weight
  vectors to maximize Sharpe, label that basket "in-sample only; overfit risk." It
  tells you the ceiling, not what to trade.
- **Label the data mode** in every result row: `mode=REAL` (you passed real price
  CSV) vs `mode=SYNTHETIC` (GBM demo). Synthetic numbers prove the machinery runs;
  they are NOT findings.
- **Exclude un-priced candidates** from the price backtest even if scored/ranked
  (e.g. NEAR/HYPE appeared in the dividend file with no price). Score them, flag
  them, but don't let them enter a backtest with a missing series.
- **Don't score yield-trap vehicles** (weeklypay/option-income ETFs like MSTW, COIW,
  TSLW). They distort a quality/yield index; gate them behind a separate bull case.

## 4. CSV-precision pitfall (data fidelity)

When exporting/rounding a price matrix to feed the backtester, **do not round to few
decimals**. Low-priced assets (ARB 0.0796, DOGE 0.0709, DOT 0.817) lose all
information at 4-dp rounding and the resulting Sharpe diverges hard from the
full-precision run (0.25 vs −0.53 in testing). Export at **full float precision**
(`repr()`), and have the loader just `float()` each cell. Re-import and
diff-check one row against the in-memory series before trusting the run.
