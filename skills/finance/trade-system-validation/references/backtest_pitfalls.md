# Backtest Pitfalls — real transcripts

From a session that started at a fake 100% FTMO pass rate and converged to honest numbers:
100% pass (bug) → 0% (bookkeeping fixed) → 39% in-sample (variants) → 25.9% out-of-sample.

## Bug A: same-bar look-ahead (peeking)
Symptom: equity jumped $25k → $45k on low-volatility dividend names; 100% of 28 trials "passed".
Cause: in the exit loop the system tested `l<=stop / h>=target` using bar-k's low/high AND opened the
position on bar-k's close in the same loop, so it "exited" on the same bar it entered using that bar's range.
Fix: entry opens at bar-k close; the position can only be stopped/targeted starting bar k+1.

## Bug B: phantom P&L (cash never debited)
Symptom: after fixing A, a "PASS" row showed equity $25,121 — BELOW the $27,000 target, reason
`timeout_no_target`, yet labeled pass=True.
Root cause: `equity += shares*exit` never subtracted `shares*entry`, so a stop-out *added* cash.
Fix: separate `cash` from `equity`. DEBIT `cash -= shares*entry` at entry; CREDIT realized
`cash += shares*stop`/`shares*target` at exit; `equity = cash + Σ shares*close[k]`.
Verification: re-run one instrumented trial, print cash/equity bar-by-bar. A stop must realize a loss.

## Stale-file trap
Symptom: JSON on disk showed `pass=True, eq=25120` (below target) while a fresh re-run showed pass=False.
Cause: the file was written by an intermediate buggy run; the canonical script had since been fixed but
the artifact was never regenerated.
Fix: ALWAYS re-run the canonical script after a bug fix; never trust a cached output file. In the Python
cache script, gate reuse with `--force` when the history window changed (e.g. extending 2y→4y).

## Walk-forward result (honest)
Variant v4 (pullback, 3% risk, 5% stop, 14% target, max 4 pos, 25-bar timeout) + regime filter (breadth<50% →
no new longs) + 3%-daily-loss halt:
- In-sample 2025-05 → 2026-08: 37.9% pass (29 trials; 11 target / 8 timeout / 10 total-blow)
- Out-of-sample 2022-01 → 2024-12: 25.9% pass (58 trials; 15 target / 37 timeout / 6 total-blow)
OOS 12 pts below in-sample ⇒ mild overfit / regime dependence. Filters cut blow-ups (6 vs 10) but did NOT
lift pass rate — the dividend universe timeouts near breakeven. Conclusion: NOT passable as configured.

## Detection checklist (run before trusting any backtest)
1. Every `pass=True` row has `equity >= target`. (catches B)
2. No position exits on the same bar it opened. (catches A)
3. A hand-checked single trial: cash debited at entry, stop realizes loss.
4. In-sample AND out-of-sample pass % both reported.
5. Script re-run after every fix; output file freshly written.
