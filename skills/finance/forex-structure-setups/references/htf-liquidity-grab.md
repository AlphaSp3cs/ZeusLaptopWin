# HTF-Anchored Liquidity Grab — Proven Edge (2026-08-05)

## The mechanic (why price moves)
Price drains liquidity below a DAILY level (prior-day low / daily swing low —
where retail stops sit) to fill size, then real participants step in and drive it
back. The grab is only valid if the 1h sweep hits a DAILY liquidity level, not a
random 1h wiggle. HTF anchoring is the difference between noise (bare 1h grab:
IS 0.83, t-test p 0.68) and a real edge (HTF grab: IS 2.0, OOS 3.0, p 0.0037).

## Daily-level precompute (reusable recipe)
Pull 2y daily bars for the symbol. For each date build a level dict:
- `prev_lo` = prior-day Low
- `prev_hi` = prior-day High
- rolling daily swing pivots: 5-bar left/right over a 20-bar lookback
  (`swing_lo = min` of window, `swing_hi = max` of window)
Cache by symbol. For each 1h bar, look up the daily level for that bar's date.

## 1h trigger (LONG)
```
pool = min([x for x in (lv.swing_lo, lv.prev_lo) if x is not None])
swept = r.Low < pool * 0.999
rej   = r.Close > pool and r.Close > r.Open
cond  = swept and rej and r.atr > 0
```
Entry = next 1h bar Open. SL = `atr_stop * ATR` (default 2.0).
TP = `rr * risk` (default 2.0). SHORT is mirror (sweep daily swing_hi/prev_hi).

## Proof-bar results (JPY longs, ~2y 1h, 3-test bar)
| Symbol  | IS PF | OOS PF | Grid | t-test p | Verdict      |
|---------|-------|--------|------|----------|--------------|
| GBPJPY  | 2.00  | 3.00   | 9/9  | 0.0037   | GREEN_PROVEN |
| USDJPY  | 1.38  | 7.00   | 9/9  | 0.0502   | NOT (p>=.05) |
| CHFJPY  | 3.60  | 0.889  | 9/9  | 0.0137   | NOT (OOS<1)  |
| EURJPY  | 1.48  | 1.50   | 9/9  | 0.1786   | NOT (p high) |

GBPJPY is the only GREEN_PROVEN entry to date. Bias is real across JPY longs but
only GBPJPY cleared the full bar — do not over-extrapolate to other pairs.

## Windows / yfinance 1h gotchas (real, hit this session)
- **No `signal.alarm` on Windows.** Use `concurrent.futures.ThreadPoolExecutor`
  with `future.result(timeout=)` for a per-download timeout; SIGALRM is absent.
- **yfinance 1h throttle.** After heavy same-session 1h pulls, some FX pairs hang
  indefinitely (not a quick fail). Wrap each symbol's pull in a thread timeout and
  fall back to shorter periods (2y->1y->6mo). A hung C-extension call may ignore the
  thread timeout — wrap the whole per-symbol run in the OS `timeout` command
  (`timeout 100 python3 ...`) so one stall can't block the batch.
- **`_symbol` attribute does NOT survive `.iloc[]`.** Pass symbol explicitly to
  triggers; see forex-structure-setups pitfalls.
- **`json.dumps(float('inf'))` -> `null`.** Render inf as `"inf"` before dump.
- **yfinance `=X` FX volume = 0** (known gap); VWAP unavailable — use structure+ATR.
- Crypto via yfinance `-USD` (CoinGecko 429s on free tier); futures need `=F`.

## Next gating steps before any ticket (still NOT executed)
1. 2nd OOS split (reverse the 60/40 cut) to confirm GBPJPY holds.
2. Executable ticket: Entry next 1h bar after daily-level sweep+reject,
   SL=2xATR, TP=2xrisk, size per 1% risk rule.
3. Extend HTF grab to shorts + the other 9 gate GOs.
