# Backtesting the 9-sector bars.db (this workspace)

## Why NOT the bundled scripts
`scripts/honest_backtest.py` / `walk_forward.py` call `yfinance` and read
`ob_universe_data.json` — a fresh fetch. The workspace already holds the **verified** store
`D:\Hermes\workflow\data\bars.db` (1.84M bars, 9 sectors). Backtest THAT; don't re-fetch.
Re-fetching is slower, loses the durability-checked store, and can't reproduce a past run.

## Store schema (recap)
- `bars(symbol,tf,ts,o,h,l,c,v)` PK(symbol,tf,ts); `ts` = unix seconds.
- `symbols(symbol,sector)`; 9 sectors: crypto 46, equity 324, indices 15, fx 15, bonds 10,
  ags 8, metals 7, energy 7, dividend 6 (dividend also a 20-symbol tag).
- Daily 2021-08-09→2026-08-07. Hourly 2024-08-08→2026-08-08 (Sunday-open sectors only:
  crypto, fx, metals, energy, indices, bonds, ags). Equity & dividend have ~no 1h.
- `fetch_log(status)` all OK; `verify_persisted()` reopens on a fresh handle + recounts
  (D: has silently discarded committed writes — a clean commit is NOT proof of persistence).

## Engine (reuse, don't re-derive)
`C:\Users\victo\bt\bt_store.py`:
- `load_bars(symbols, tf)` → {sym: DataFrame[open,high,low,close,volume]} full float precision.
- `add_indicators(df)` → sma20/50/200 + rsi14.
- `align_universe(frames)` → common date grid, ffill, indicators.
- `run_challenge(frames, COMMON, s, e, P, use_regime)` → honest FTMO sim
  (entry @ close[k], risked k+1, cash debited, daily HALT ≥3%, total BLOW ≤90% of start).
  `P` = {max_pos, risk_pct, stop_pct, target_pct, timeout, entry(pullback|momentum)}.
- `band_study(frames, horizons)` → look-ahead-FREE forward return by MA200-discount quintile.
- `permutation_p(state, state, fwd, n)` → p<0.05 ⇒ band ordering real, not random.

`C:\Users\victo\bt\bt_runner.py`:
- loops all 9 sectors; band study + permutation; honest sim IS/OOS split by DATE for the
  tradeable sectors (crypto, fx, metals, energy, indices, bonds, ags).
- writes `D:\Hermes\workflow\backtest\reports\backtest_<tf>_<stamp>.json` + `.md`.

## Honesty contract (enforced)
- pass% reported ALONGSIDE blow-up%.
- IS vs OOS split by date; no same-window tuning.
- permutation p<0.05 before GREEN (else AMBER / RED / NO_EVIDENCE_OOS).
- 100% pass on a 30d +8% target = BUG (same-bar look-ahead), not edge.

## Workspace law
Code master `C:\Users\victo\bt\`; mirror `.py` to `D:\Hermes\workflow\backtest\scripts\`.
Data/outputs on D:. Never edit only the D: copy.
