---
name: trading-backtest-integrity
description: Use before trusting any backtest. Catches fake-pass bugs.
---

# Trading Backtest Integrity

The most dangerous output an AI trading agent produces is a backtest that *looks* great.
In this workspace a first FTMO 25K sim reported **100% pass** — it was 100% bug: a
same-bar look-ahead and phantom P&L. After the fix the same system scored **0%**. The lesson
below is worth more than any strategy.

## When to load this skill
- User asks to "backtest", "validate a strategy", "pass the FTMO/prop challenge", "find the best
  swing/long trades", or "check why trades were wrong".
- **DCA / recurring-buy backtest** (fixed $ each period) — or a **score-index / unified ranking
  across crypto + dividend (or any mixed classes)**. These hit traps the single-position sim below
  does not: see `references/dca-score-backtest.md` (DCA Sharpe distortion, cross-class score
  normalization, oracle/overfit labeling, CSV-precision fidelity).
- Before reporting ANY backtest number as a result. Verify bookkeeping first.

## The two bugs that fake a win (check BOTH every time)

1. **Same-bar look-ahead.** Entering and exiting on the same bar using that bar's high/low = peeking
   at the future. Fix: a position opens at bar-k close; it can only be stopped/targeted from bar k+1.
   Symptom: equity explodes past target on day 1 (e.g. $25k → $45k in a 30-day window). That's the tell.
2. **Phantom P&L (no debit at entry).** If equity is `cash + Σ shares·price` but you never debited
   `cash` when you opened the position, a stop-out *adds* cash. Symptom: a losing stop shows a profit.
   Fix: on entry `cash -= shares·entry`; equity = `cash + Σ shares·mark`; realized P&L only hits cash on exit.

Golden rule: **a backtest that makes money too easily is broken, not skilled.** A 100% pass rate on a
30-day +8% challenge is not a finding — it's a bug. Verify the P&L math before believing any number.

## Honest bookkeeping skeleton (per-bar)
```
cash = START
for k in range(s, e):
    # 1) EXITS on positions opened BEFORE bar k, using bar k's L/H
    #    stop -> cash += shares*stop ; target -> cash += shares*target ; timeout -> cash += shares*close
    # 2) daily-loss check: equity = cash + Σ shares*close[k]
    #      breach if equity < prev_equity*0.95  -> close all, halt
    #    total-loss check: equity < START*0.90   -> close all, halt
    # 3) target hit: equity >= START*1.08 -> PASS
    # 4) ENTRIES: scan at bar k, open at close[k], risked from k+1
    #      size shares = (risk_pct*equity)/(entry-stop);  cash -= shares*entry
    # 5) prev_equity = equity
```
FTMO Phase-1 numbers used: start 25000, target +8% in ≤30d, 5% daily-loss / 10% total-loss caps.

## Variant grid + the trade-off you must report
Sweep risk% / stop% / target% / entry-type (pullback vs momentum) as variants. The honest result in
this workspace:
- 1% risk → 0% pass (safe, never hits +8%, times out near break-even).
- 3% risk → ~39% pass but ~30–36% of attempts BLOW the daily/total cap.
There is no free lunch in a low-vol dividend universe for a 30-day +8% target. Report pass% AND
blow-up% side by side — a pass rate without its blow-up rate is misleading.

## Mandatory before trusting a result
- **Walk-forward / out-of-sample.** Tuning all variants on one 16-month window is overfitting; the
  pass rate is optimistic. Re-run on earlier data (e.g. 2022–2024) and require >70% to call a plan
  "passable" (you need margin for Phase 1 + 2 + Verification).
- **Regime filter.** No new longs when the broad market is weak. Two implementations:
  - *Index version:* broad index (e.g. SPY/QQQ) below its 200-day MA.
  - *Breadth-proxy version (use when no index is in the universe):* compute
    `breadth[k] = (% of universe whose close[k] > its own 200d MA)` per common bar;
    gate new longs when `breadth[k] < 0.50`. This caught the late-2024 broad drawdown
    (10–13 of 45 names lost together on 1y holds) with no index ticker needed.
  Both cut blow-ups; neither alone lifts a structurally-too-low pass rate.
- **Daily-loss HALT.** If down ≥3% on the day, stop trading — this alone cuts the blow-up rate.
- **Segregate books.** An income/DRIP book and a challenge/swing book have opposite rules. Mixing them
  is why a dividend backtest "looks good" (dividends) but loses on price (PG 97% / KMB 100% of 1y
  windows negative price return).

## Walk-forward / out-of-sample is how you DISPROVE a backtest
The variant grid (above) is in-sample by construction — every variant was tuned on the
same window you report on, so its pass rate is optimistic. The real test is an **OOS window
the tuning never saw**. This workspace's decisive run:

- In-sample 2025–2026: **37.9%** pass (29 trials).
- Out-of-sample 2022–2024: **25.9%** pass (58 trials).
- OOS 12 pts BELOW in-sample → the system is mildly overfit and regime-dependent.

Disproof technique (reuse):
1. Fetch >=4y of daily history (yfinance `period="4y"`) so you have a disjoint window.
2. Run the *exact same* params found in-sample on the earlier window. Do NOT re-tune.
3. If OOS pass% << in-sample pass%, the edge is partial/overfit — say so, don't polish.
4. A passable prop-firm plan needs OOS >70% (margin for Phase 1 + 2 + Verification).
   Below that = not passable as configured; report it, don't dress it up.

The regime filter + daily halt (from above) cut blow-ups but did NOT lift the core
pass rate — confirming the universe (low-vol dividend names) structurally can't hit a
30-day +8% target. When the fix doesn't move the number, the premise is wrong, not the code.

## Zero OOS trades is NOT a pass — and small-n PF is usually noise
Two failure modes that only show up on trend-following rules with long lookbacks
(observed 2026-08-07 on a crypto bottom study):

1. **n=0 in the OOS window.** A "long only above a rising MA200" rule never fires
   during a deep bear, so the OOS split returns zero trades. That is NO EVIDENCE,
   not a pass and not a fail. Never let a `pf >= 1` default on an empty trade array
   flow into a GREEN verdict — guard with `if n_oos < 5: verdict = "NO_EVIDENCE"`.
   Report the empty window explicitly and say why the rule didn't trigger.
2. **A gaudy PF on 15–30 trades proves nothing.** Add a **permutation test**: shuffle
   the asset's daily returns ~200x, rebuild a synthetic price path, re-run the exact
   same rule, and count how often the shuffled run beats the real total return.
   `p = (count+1)/(N+1)`; require p < 0.05. In that session NEAR IS PF 1.48, LINK
   2.67, INJ 3.20 all had p between 0.26 and 0.58 — i.e. indistinguishable from a
   random walk in the same asset. Big PF + high p = story, not edge.

**Reconfirmed 2026-08-08 on an independent 500-name crypto run, and this is the
sharper version of the lesson: the permutation test is not a tie-breaker, it is
a THIRD independent gate that overturns candidates which already cleared IS and
OOS.** LINK (IS PF 3.07 / OOS PF 1.85) and BCH (IS 1.47 / OOS 1.61) both passed
a two-test bar cleanly — permutation p came back 0.18 and 0.33. On a two-test
bar they ship as GREEN; they are noise. Meanwhile DOGE showed the classic
collapse shape (IS PF 6.36 / +2367% -> OOS PF 0.70 / -41%).

Make the verdict a LADDER in code so an empty or insignificant result can never
fall through to a pass:
```
if n_oos < 5:                                 NO_EVIDENCE_OOS
elif IS.pf is None or OOS.pf is None:         NO_EVIDENCE
elif IS.pf >= 1 and OOS.pf >= 1 and p < 0.05: GREEN_PROVEN
elif IS.pf >= 1 and OOS.pf >= 1:              AMBER_NOT_SIGNIFICANT
else:                                         RED
```
Two independent studies, ~14 assets each, produced ZERO GREEN. Expect that
outcome for trend rules on single crypto assets — it is the normal result, not
a sign your harness is broken.

When every candidate fails the proof bar, say so in one line and pivot to a
**base-rate study** (bucket forward returns by some state variable and report medians
and win rates) instead of shipping a failed rule with optimistic framing. A base rate
is a weaker claim you can actually defend.

## Signal-stacking / confluence validation (forward-return band study)

When you AMPLIFY several sub-signals into ONE conviction score (rather than run a
trade system), the IS/OOS/permutation bar above still applies to each component — but
the STACK itself needs a different check: does higher stacked conviction actually
predict higher forward return?

Method (look-ahead-free, no trade sim needed):
```
for every bar k (>=200d history, forward window available):
    score_k = amplifier(df.iloc[:k+1])        # data through k ONLY
    fwd_h   = close[k+h] / close[k] - 1       # TRUE future return = the LABEL
bucket by score band; report median fwd + win% per horizon;
compare to the unconditional baseline (all windows pooled).
```
A real edge is MONOTONIC (top band > mid > bottom) AND the top band beats the
unconditional median. The theory-amplify study (2026-08-08) cleared this: 24m
ACCUMULATE +22.8% / WATCH +12.6% / AVOID -31.9% vs baseline -1.7% — but ONLY at 24m;
shorter horizons were negative, so it is an ACCUMULATION signal, not a trade-timing
one. Report the horizon honestly; never promote a 24m edge to a swing system.

Pitfall — regime master gate: a deep-discount / long-horizon thesis (e.g. buy
`<= -90%` from ATH) is NOT a trade-timing signal. If the broad regime is broken
(price below MA200 and MA200 falling), a high discount score must NOT override the
regime — hard-cap conviction at WATCH/AVOID. Letting a 24-month accumulation thesis
force an ACCUMULATE through a broken trend is the bug caught 2026-08-08.

## Support files
- `scripts/honest_backtest.py` — parameterized FTMO-style sim with correct bar-k entry / k+1 exit and
  cash-debited bookkeeping; runs a variant grid. Reuse, don't re-derive.
- `scripts/debug_single_run.py` — prints bar-by-bar equity/entries/exits for one trial to catch look-
  ahead or phantom-P&L before trusting the aggregate number.
- `scripts/walk_forward.py` — runs the same params on an in-sample window AND a disjoint OOS window,
  prints both pass rates side by side. Use this every time before calling a system "passable".
- `references/ftmo-sim-gotchas.md` — yfinance 1.5.2 on Python 3.13 fetch traps (progress kwarg,
  tz-aware dividend compare, get_dividends fallback), the two bookkeeping bugs in detail, and the
  OOS disproval recipe.
- `references/dca-score-backtest.md` — DCA Sharpe distortion (TWR vs money-weighted IRR), cross-class
  score unification to one 0–100 index, and honesty guardrails (oracle ceiling, in-sample overfit
  flagging, REAL vs SYNTHETIC labeling, CSV full-precision fidelity).
- `references/barsdb-9sector-workflow.md` — **THIS WORKSPACE**: how to backtest the verified
  `D:\Hermes\workflow\data\bars.db` (9 sectors, 1.84M bars) INSTEAD of re-fetching yfinance. The
  bundled scripts above read `ob_universe_data.json` (a fresh yf pull); use `C:\Users\victo\bt\bt_store.py`
  + `bt_runner.py` to run against the real store. Reuse the corrected bookkeeping, never re-derive it.

## This workspace: backtest the REAL bars.db, not yfinance
The bundled `honest_backtest.py` / `walk_forward.py` re-fetch via yfinance and read
`ob_universe_data.json`. This workspace already owns a **durability-checked** store at
`D:\Hermes\workflow\data\bars.db` (1.84M bars, 9 sectors: crypto 46, equity 324, indices 15,
fx 15, bonds 10, ags 8, metals 7, energy 7, dividend 6). Backtest THAT. Re-fetching is slower,
loses the verified store, and can't reproduce a past run.

Bridge engine (already built, reuse it):
- `C:\Users\victo\bt\bt_store.py` — `load_bars(symbols, tf)` → DataFrames; `add_indicators` (sma20/50/200 + rsi14);
  `align_universe`; `run_challenge(...)` (the corrected FTMO sim: entry @ close[k], risked k+1, cash
  debited, daily HALT ≥3%, total BLOW ≤90%); `band_study` (look-ahead-FREE forward return by MA200-discount
  quintile); `permutation_p` (p<0.05 ⇒ band ordering real, not random); `verify_persisted()` (reopen on
  fresh handle + recount — D: has silently discarded committed writes, so a clean commit is NOT proof).
- `C:\Users\victo\bt\bt_runner.py` — loops all 9 sectors; band study + permutation; honest sim IS/OOS
  split BY DATE for tradeable sectors; writes `D:\Hermes\workflow\backtest\reports\backtest_<tf>_<stamp>.json+.md`.
- Workspace law: code master on `C:\Users\victo\bt\`; mirror `.py` to `D:\Hermes\workflow\backtest\scripts\`.
  Data/outputs on D:. Never edit only the D: copy.

Honesty contract every run enforces: pass% shown ALONGSIDE blow-up%; IS vs OOS split by date (no same-window
tuning); permutation p<0.05 before GREEN (else AMBER/RED/NO_EVIDENCE_OOS); 100% pass on a 30d +8% target = BUG.

## Pitfalls
- Never report a backtest as "validated" until you have (a) confirmed entry/exit are on different bars,
  (b) confirmed cash is debited at entry, and (c) sanity-checked one trial bar-by-bar.
- **DCA Sharpe is a trap:** computing returns on a cash-inflated DCA value path yields a meaningless,
  near-uniform Sharpe across every basket. Use time-weighted returns (contribution stripped) for Sharpe,
  money-weighted IRR for the investor's annualized return. See `references/dca-score-backtest.md`.
- **Mixed-class score index:** never average raw scores across incompatible scales. Normalize each
  sub-factor to 0–100, weight *within* class, then rank globally.
- **Label data mode** REAL vs SYNTHETIC in every result; synthetic proves machinery, not edge.
- A high pass rate from aggressive sizing is a *blow-up rate* in disguise. Always show both.
- Overfitting: tuning on the same window you report on. Walk it forward or label it in-sample only.
