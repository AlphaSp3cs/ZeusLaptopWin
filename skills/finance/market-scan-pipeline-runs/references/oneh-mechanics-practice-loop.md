# The 1h Mechanics Practice Loop — wiring the proven edge into the scan pipeline

This reference captures the 2026-08-05 "rebuild on 1h bars" work and the
HTF-anchored grab that became the project's FIRST GREEN_PROVEN edge (GBPJPY
long). It is the missing link between the scan/gate pipeline and the mechanic
proof: the pipeline produces GOs, and this loop PROVES them on intraday bars
before any ticket.

## The loop (end to end)

1. Fresh nightshift scan  -> `nightshift_scan.py` (crypto now via yfinance `-USD`,
   see below)
2. Recalibrated gate     -> `enhanced_trade_gate.py` (H1/H2/H6 fixes from
   `references/gate-hardgate-fixes.md`)
3. Mechanics proof        -> read gate GOs from `enhanced_setups_day_latest.json`,
   map each to a yfinance ticker, run each through the 3 mechanics triggers on
   1h bars with the 3-test proof.

Driver: `mechanics_practice_1h.py` (reads gate GOs, proves on 1h).
Standalone: `mechanics_1h.py` :: `prove_htf_grab(sym, side)` for ad-hoc checks.
Direct inspector: `inspect_metals_fx.py` for the metals/forex structural read.

## Why 1h (the whole point)

Daily bars give ~60 grab events over 10y -> t-test has NO power (p~0.5, edges
look "unproven" for the wrong reason). 1h bars give thousands of events -> real
sample. We trade calendar depth (10y daily) for EVENT SAMPLE SIZE. yfinance caps
1h history at ~2y — that is enough for a mechanic edge.

## The HTF-anchored grab (the fix that worked)

Bare 1h grab (sweep any local 1h swing + reject): parameter-robust (grid 81/81)
but sub-breakeven (USDJPY IS 0.83, t-test p 0.68). It was catching 1h noise.

HTF-anchored grab (sweep must hit a DAILY liquidity level — prior-day H/L or
daily swing — then reject): GBPJPY long results —
  in-sample PF 2.0, walk-forward OOS PF 3.0, grid 9/9, t-test p 0.0037, n=70
  -> GREEN_PROVEN (first edge to clear all four proof gates).

Other JPY longs showed the bias but did NOT clear the full bar:
  USDJPY  IS 1.38 OOS 7.0  grid 9/9 p=0.0502 (t-test borderline)
  CHFJPY  IS 3.60 OOS 0.889 grid 9/9 p=0.0137 (OOS PF < 1)
  EURJPY  IS 1.48 OOS 1.5  grid 9/9 p=0.1786 (t-test too weak)
So: the JPY-long liquidity-grab bias is REAL, but only GBPJPY is green-lit so
far. Do not over-extrapolate to other pairs without their own proof.

## Nightshift scan crypto patch (2026-08-05)

`nightshift_scan.py` now overrides the crypto leg with `_scan_crypto_yf()`
(yfinance `-USD` daily) because `scan_crypto()` hard-loops CoinGecko OHLC and
429s after ~4 calls, hanging the whole scan. The override produces the same dict
shape (`assets` / `qualified_longs` / `qualified_shorts`) using the universal
scanner's long/short scoring, so downstream gate code is unchanged. If you see
the scan hang on crypto, this is why — and the fix is in place.

## Windows / yfinance 1h gotchas (this loop specifically)

- **No SIGALRM on Windows.** `signal.alarm()` raises `AttributeError`. Use a
  `concurrent.futures.ThreadPoolExecutor` with `future.result(timeout=)` for a
  per-symbol download timeout; if it stalls, fall back to a shorter `period`
  (2y -> 1y -> 6mo). Do NOT use `signal` on Windows.
- **`df._symbol` does NOT survive `.iloc[]` slicing.** Pass the symbol as an
  explicit parameter to triggers that need per-symbol context (HTF daily
  levels). A sliced train/test DataFrame silently loses the attribute -> zero
  trades -> false NOT_PROVEN. This was a real, silent bug; the fix is to pass
  `sym=` explicitly in `prove_htf_grab`.
- **JSON serializes `inf` PF as `null`.** `profit_factor` returns `float("inf")`
  on zero losing trades; render as string `"inf"` before `json.dumps` or the
  edge is mis-flagged as "no data".
- **yfinance 1h endpoint throttles after heavy same-session usage.** After many
  pulls, GBP/CHF/EUR JPY 1h downloads hang (killed by OS `timeout`). Only
  USDJPY served that night. Retry later; the module is correct. Use OS `timeout`
  per symbol, not a Python `signal`.
- Run phase scripts with **system `python3`** (3.13), not the Hermes venv — scan
  deps (yfinance) live there.

## Status / next gating steps before any ticket

GBPJPY long HTF grab is GREEN_PROVEN but NOT executed (validation milestone).
Before a ticket: (1) 2nd OOS split (reverse the 60/40 cut) to confirm;
(2) generate the executable ticket (Entry = next 1h bar after a daily-level
sweep+reject, SL = 2*ATR, TP = 2*risk, size per 1% risk rule); (3) widen the
proven set — test HTF grab on shorts and the other gate GOs.

Deliverable files (Desktop + D:\Hermes):
  C:\Users\victo\Desktop\NIGHTSHIFT_METALS_FX_20260805.txt
  C:\Users\victo\Desktop\NIGHTSHIFT_1H_REBUILD_20260805.txt
  C:\Users\victo\Desktop\HTF_GRAB_PROOF_20260805.txt
  D:\Hermes\mechanics_1h.py, D:\Hermes\HTF_GRAB_PROOF_20260805.txt,
  D:\Hermes\VICTOR_LAWS.txt (proven-edge milestone recorded)
