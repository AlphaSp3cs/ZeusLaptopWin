---
name: trade-system-validation
description: Validate trading backtests before trusting any sim number.
---

# Trade System Validation

## When to use
- User asks to backtest a strategy, build a trading system, or "pass a challenge (FTMO 25K, etc.) / become a better trader".
- Before presenting ANY backtest win-rate / pass-rate / profit-factor / CAGR as real.
- After building a sim, before declaring it validated or "passable".

## HARD RULE: a backtest that looks too good is broken
A 100% pass rate, an equity curve that jumps implausibly (e.g. $25k→$45k on low-vol dividend names), or zero losses = almost always a BUG, not edge. Verify the P&L math before believing any number. A fake 100% pass rate is worse than no backtest — it convinces you to trade a lie.

## The two classic bugs to check FIRST
1. **Look-ahead bias** — entering AND exiting on the same bar using that bar's high/low (peeking at the future). Fix: a position opened at bar-k close can only be stopped/targeted from bar **k+1** onward.
2. **Phantom P&L (cash never debited)** — `equity += shares*exit` without ever subtracting `shares*entry`. Account drifts upward on every stop-out. Fix: keep `cash` separate; DEBIT cash at entry, CREDIT realized exit at stop/target, and compute `equity = cash + Σ shares*current_close` (mark-to-market at the close).

### Correct accounting skeleton (pseudo)
```
cash = START; pos = []
for k in range(s, e):
    still = []
    for p in pos:                      # EXITS: opened before k, risked on k's L/H
        if low[k]  <= p.stop:   cash += p.shares * p.stop
        elif high[k] >= p.target: cash += p.shares * p.target
        elif p.held >= TIMEOUT:  cash += p.shares * close[k]
        else: p.held += 1; still.append(p)
    pos = still
    equity = cash + sum(p.shares * close[k] for p in pos)
    if equity >= TARGET: return PASS
    # ENTRIES: scan at k, open at close[k], risked from k+1
    for tk ...:
        if signal:
            entry = close[k]; stop = entry*(1-STOP); target = entry*(1+TGT)
            shares = (RISK*equity)/(entry-stop)
            cash -= shares * entry        # DEBIT
            pos.append(...)
```
- **Daily-loss limit** = equity closed below 95% of the PREVIOUS bar's equity (not vs START).
- **Total-loss limit** = equity below 90% of START.
- Final equity of a reported "PASS" MUST be ≥ target. If a PASS row shows equity < target → bookkeeping bug, re-run.

## Walk-forward / out-of-sample protocol
- Split data into IN-SAMPLE (used to choose params) and OUT-OF-SAMPLE (never seen while tuning).
- Tune on in-sample ONLY. Report BOTH rates. If OOS << in-sample → overfit / regime-dependent (a 12-pt OOS drop is typical of mild overfit).
- Re-run on EARLIER history (e.g. 2022–2024 if you tuned on 2025–2026) to get a real OOS number.
- Bear markets inside the OOS window reveal timeout-near-breakeven behavior — informative, not a bug. The filter correctly avoids blow-ups there.

## Honest reporting
- Report in-sample AND out-of-sample pass % separately, with fail-reason breakdown (target / timeout / daily-blow / total-blow).
- Never dress up a 26–39% pass rate as "passable". State plainly: <50% historical pass = would fail Phase 1 most of the time.
- **Segregate books:** the income/DRIP (dividend) book is NOT an active-challenge book. A dividend universe is too low-volatility to hit a 30-day +8% target; mixing them produces dividend-driven "wins" that lose on price (e.g. PG lost on price in 97% of 1y windows). Run separate accounts with separate rules.

## Verification (do this before declaring done)
- Re-run with a single instrumented trial; print cash/equity bar-by-bar; confirm entry debits cash and a stop realizes a loss.
- Sanity check the JSON: every `pass=True` row has `equity >= target`.
- Re-run the canonical script after ANY bug fix — never trust a stale output file.

## Pitfalls
- Same-window overfit: tuning 5 variants on the same 16-month window inflates the best. Always OOS.
- A regime filter (breadth <50% → no new longs) + daily halt (flat if down ≥3% on the day) cut blow-ups but may NOT lift pass rate — report both metrics, don't claim victory on risk alone.
- Don't reuse a cached JSON across a data-refresh; force-refetch when extending the history window.

## Support files
- `references/backtest_pitfalls.md` — real bug transcripts from a session that went 100%→0%→39%→26% (OOS), with detection snippets.
- `scripts/honest_backtest_template.py` — minimal, runnable, correctly-accounted FTMO-style sim you can copy and extend.
