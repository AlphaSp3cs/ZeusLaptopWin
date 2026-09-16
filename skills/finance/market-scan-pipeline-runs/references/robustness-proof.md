# Robustness proof — "prove profitable all we can"

The user's standing rule is no longer "backtest PF >= 1.0 then trade." It is
**"prove profitable all we can"** — a setup must survive three independent
stress tests before it is GREEN-LIGHTED. This reference documents the harness
and the finding that defined the bar (2026-08-05).

## Why one PF number is not enough

A 10y aggregate PF >= 1.0 can be produced by a **few large winners dragging a
near-breakeven strategy positive**. The per-trade average R is what tells you
whether the edge is real. The first full proof run (below) showed exactly this:
every passing candidate had PF>1.0 but a per-trade R statistically
indistinguishable from zero.

## The three tests (GREEN requires ALL three)

1. **10-YEAR WINDOW** — backtest on `10y` daily bars (not 3y). Regimes cycle
   longer than 3y. The harness uses `yf.download(sym, period="10y", ...)`.
2. **WALK-FORWARD out-of-sample** — split the 10y series 60/40 (calendar cut);
   PF >= 1.0 on the UNSEEN test half. Catches in-sample artifacts.
3. **PARAMETER GRID + SIGNIFICANCE** — sweep RSI band (long: 35/38/40/42/45,
   short: 55/58/60/62/65) × ATR mult (1.5/2.0/2.5/3.0) × R:R (1.5/2.0/2.5) =
   60 combos; require >=50% pass PF>=1.0. Then a one-sample t-test on per-trade
   R: p < 0.05 to be a real edge, not noise.

Harness: `scripts/robustness_proof.py` (function `validate(sym, side)` -> dict
with `verdict: "GREEN_PROVEN" | "NOT_PROVEN"`, `failed: [which tests]`, and the
numbers for each). Run per symbol: `python3 robustness_proof.py "USDJPY=X:long"`.

## The defining finding (2026-08-05)

All 5 candidates that passed the 10y-PF>=1.0 screen were run through the proof.
**Zero passed.**

| SYMBOL  | SIDE  | IS_PF | OOS_PF | GRID  | t     | p      | RESULT        |
|---------|-------|-------|--------|-------|-------|--------|---------------|
| GBPJPY  | LONG  | 1.29  | 2.66   | 60/60 | 1.64  | 0.105  | NOT_PROVEN(T3)|
| USDJPY  | LONG  | 1.54  | 1.10   | 60/60 | 1.17  | 0.245  | NOT_PROVEN(T3)|
| BNB-USD | LONG  | 1.33  | 1.44   | 60/60 | 1.27  | 0.210  | NOT_PROVEN(T3)|
| CHFJPY  | LONG  | 1.31  | 1.24   | 60/60 | 0.80  | 0.425  | NOT_PROVEN(T3)|
| ^FCHI   | SHORT | 1.29  | 0.98*  | 40/60 | 0.79  | 0.429  | NOT_PROVEN(T1+T3)|

* ^FCHI OOS PF fell below 1.0 — edge did not hold on unseen data.

Read: the 10y PF is real in aggregate but the per-trade expectancy is
noise-level (all p > 0.10). Under the "prove profitable all we can" mandate the
correct deliverable was **no position** — the earlier 5-entry GO list was
RESCINDED in the same report.

## How to act on a NOT_PROVEN result

Do NOT manufacture a trade to fill the list. Instead:
- State the rescission plainly with the failed-test numbers.
- Offer refinement paths that could surface a real edge:
  1. **Edge refinement** — trail-to-breakeven + let winners run, so the few big
     winners compound and average R firms up (may lift significance).
  2. **Tighter entry** — RSI<30 AND -3% VWAP, cutting scratch trades to boost
     per-trade expectancy.
  3. **Regime filter** — only take offensive longs when gauge < 60 (the run
     above was at 82.5 EXTREME DANGER — worst backdrop for longs).
  4. **Broader universe** — scan more symbols; a genuine edge may live elsewhere
     that survives the full proof.
- Persist the evidence: copy the harness JSON log to `D:\Hermes\` as the durable
  record, and update `D:\Hermes\VICTOR_LAWS.txt` (the user's permanent ruleset)
  so the three-test bar is remembered across sessions.

## Pitfalls

- A `[]` or all-NOT_PROVEN proof is a FINDING, not a tool failure. Do not
  "fix" it by loosening the proof. The proof exists to say no.
- The proof reuses the scanner's entry rule verbatim (RSI/VWAP/ATR/2R). If you
  change the rule, change it in BOTH the scanner and the harness or the proof
  validates a different strategy than you trade.
- `scipy` is required for the t-test (`stats.ttest_1samp`); it is present on the
  system python3. If `ModuleNotFoundError: scipy`, install it rather than
  dropping the significance test.
