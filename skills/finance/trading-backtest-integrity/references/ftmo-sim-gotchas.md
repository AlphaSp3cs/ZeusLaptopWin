# FTMO / challenge backtest gotchas

## yfinance 1.5.2 on system Python 3.13 (this workspace)

Two fetch traps that break a backtest on first run:

1. **`progress=` / `actions=` kwargs removed.** `Ticker.history(period="3y", interval="1wk",
   auto_adjust=True, actions=True, progress=False)` raises `unexpected keyword argument 'progress'`.
   Fix: drop both kwargs. `t.history(period="3y", interval="1wk", auto_adjust=True)`.

2. **tz-aware dividend index.** `Ticker.dividends` index is `America/New_York` (tz-aware). Comparing
   to `datetime.datetime.now()` raises `Cannot compare tz-naive and tz-aware`. Fix: build cutoffs with
   `pd.Timestamp.now(tz=divs.index.tz)` (fall back to `pd.Timestamp.now()` if the index is naive).

3. **`Ticker.dividends` can be empty when dividends exist.** Fall back to `Ticker.get_dividends()`.
   Note: in 1.5.x `dividends` is sometimes a method, not just an attribute — call it (`t.dividends()`)
   or use `get_dividends()` to be safe.

4. **`Ticker.fast_info["last_price"]`** is the reliable live price; fall back to `hist["Close"].iloc[-1]`.

A working fetch wrapper is in `fetch_universe.py` (caches daily history + dividends + 52w to
`ob_universe_data.json`, reused <24h).

## The two bookkeeping bugs that fake a win

### Bug A — same-bar look-ahead
Entering AND exiting on the same bar using that bar's high/low means the sim "knows" the future.
Symptom: equity blasts past the target on day 1 (e.g. $25k → $45k in one 30-day window).
Fix: open at bar-k close; only allow stops/targets to trigger from bar k+1 onward.

### Bug B — phantom P&L (no debit at entry)
If equity is computed as `cash + Σ shares·price` but `cash` is never reduced when a position is
opened, then a stop-out ADDS cash (you "sell" at stop without ever having "bought"). A losing
trade shows a profit. Symptom: a stop hit raises equity instead of lowering it.
Fix: at entry `cash -= shares·entry`; on exit add `shares·exit_price`; equity = `cash + Σ shares·mark`.

## Honest reporting rules
- Report pass% AND blow-up% (daily/total breach) side by side. A high pass rate from aggressive sizing
  is a blow-up rate in disguise.
- 1% risk in this dividend universe → 0% pass (safe, never hits +8%, times out near break-even).
  3% risk → ~39% pass but ~30–36% attempts blow the cap.
- Tuning all variants on one 16-month window = overfitting. Walk it forward (2022–2024) before trusting.
- Require >70% out-of-sample pass to call a plan "passable" (margin for Phase 1 + 2 + Verification).

## OOS disproval recipe (the decisive test — 2026-08-07 session)
Goal: PROVE a backtest isn't overfit. Run the SAME params (no re-tuning) on a disjoint window.
1. Pull 4y daily: `period="4y"` (not 2y) so a disjoint OOS window exists. Cache + reuse <24h.
2. Tune variants on IN-SAMPLE (here 2025-05→2026-08). Best = v4 pullback, risk 3%, stop 5%,
   target 14%, timeout 25, max 4 positions.
3. Run identical params on OUT-OF-SAMPLE 2022-01→2024-12 (includes 2022 bear).
4. Compare:
   - In-sample 2025–26: **37.9%** pass (29 trials)
   - OOS 2022–24: **25.9%** pass (58 trials)  → 12 pts below = mild overfit / regime dependence.
5. Adding regime filter (breadth <50% → no new longs) + 3%-daily-loss HALT cut blow-ups (6/58 OOS)
   but did NOT raise pass rate → the universe structurally can't hit a 30-day +8% target. When the fix
   doesn't move the number, the PREMISE is wrong, not the code. Report it; don't dress it up.
Reusable script: `scripts/walk_forward.py` (prints both pass rates side by side; `--force` refetches).

## Breadth proxy (regime filter, no index needed)
Per common bar, count fraction of universe with close > own 200d SMA. <50% = risk-off → block new
long entries. Cheap, no external data, and it correctly sat out the 2022 bear (most trials stayed flat
at $25k, no signal). Use as the gate before entries in any long swing/FTMO sim.

## File-layout note for fetch cache
`fetch_universe.py` hardcodes `period="2y"` in the `work()` call — change to `"4y"` when you need
OOS. Add `import sys` + `if OUT.exists() and "--force" not in sys.argv:` guard so a cached (<24h) file
isn't blindly reused when you want fresh 4y data.
