# Market Mechanics — the "why price moves" driver model

Canonical playbook for building ENTRIES on the event that FORCES price, not on a
static indicator condition. This is the methodology behind `mechanics_entries.py`
and `mechanics_1h.py`. Read it whenever the user asks to "understand market
mechanics", "integrate better entries on price", or "why price moves".

## The core principle: CAUSE, not SYMPTOM

A static condition (`RSI<40 & close<VWAP`, or `RSI>60 & close>VWAP`) describes a
*state*. It catches noise. It is a **FILTER, not an ENTRY**. The original 5
candidates that passed 10y-PF>=1.0 all FAILED the 3-test proof because their rule
had no "why" — the aggregate PF was a handful of large winners dragging a
near-breakeven strategy positive (t-test p 0.10–0.99). An entry must name the
driver event that actually forces price.

## The five drivers (D1–D5)

- **D1 Liquidity grab / stop-run.** Price sweeps a prior swing low/high (or a
  daily liquidity level) to trigger resting stops / fill size, then rejects back
  inside + directional candle. Enter next bar. This is the single biggest
  short-term mover. HOW it was made PROVEN: anchoring the sweep to a DAILY level
  (prior-day H/L or daily swing) — see below.
- **D2 Market structure (BOS + pullback).** Break of structure, then retrace into
  the origin OB / order block. NOT YET CODED — flagged for a future leg. The ICT
  structure for this lives in `market-timing-mastery` (OB/FVG/liquidity-sweep).
- **D3 VWAP reclaim w/ VOLUME.** Price was below value, then closes back through
  VWAP on RISING volume + directional candle. Volume = confirmation the move is
  funded, not a wick.
- **D4 Exhaustion fade.** Volume spike (>2.5× avg) at extended RSI + reversal
  candle = the last chasers are in, nobody left to buy → fade it.
- **D5 Session / regime timing.** The same mechanic fires differently in London
  vs Asian vs NY; and offensive longs only work when the gauge is NOT extreme.
  (Under an 82.5 EXTREME gauge, indiscriminate longs get crushed — only precise
  liquidity-pool snipes revert.)

## What our data CAN and CANNOT see (yfinance)

- CAN: OHLCV on daily and 1h (1h capped at ~2y free-tier); RSI/ATR/VWAP computed
  locally; FX `=X`, futures `=F`, crypto `-USD`, indices `^`.
- CANNOT: order-book / footprint / actual stop clusters. We INFER liquidity
  levels from prior swing highs/lows and prior-day H/L — that is the HTF anchor.
- GAPS: FX `=X` and cash `^` report `volume 0` (VWAP unavailable → use structure
  + ATR, not volume-weighted levels); CoinGecko 429s on crypto (route crypto via
  yfinance `-USD`).

## The 1h rebuild lesson: trade calendar depth for EVENT SAMPLE SIZE

Daily bars give ~60 grab events over 10y → t-test has NO power (p~0.5, edges look
"unproven" for the wrong reason). 1h bars give thousands of events → real sample.
We traded 10y-daily calendar depth for ~2y-1h EVENT sample size. That is the
correct trade for a mechanic whose essence is the intrabar sweep.

## The HTF-anchoring fix (the proven pattern)

Bare 1h grab (sweep any local 1h swing + reject): parameter-robust (grid 81/81)
but sub-breakeven (USDJPY IS 0.83, t-test p 0.68) — it caught 1h noise.

HTF-anchored grab (the sweep must hit a DAILY liquidity level — prior-day H/L or
daily swing — then reject): **GBPJPY long = the project's FIRST GREEN_PROVEN
edge** (IS 2.0 / OOS 3.0 / grid 9/9 / t-test p=0.0037, n=70). Other JPY longs
showed the bias but did NOT clear the full bar (USDJPY p=0.05 borderline; CHFJPY
OOS 0.89; EURJPY p=0.18). The bias is real; only GBPJPY is green-lit so far.

Implementation: precompute daily levels per date from a 2y daily pull
(`prev_lo`/`prev_hi` = prior-day H/L + rolling 5-bar swing over 20-bar lookback);
for each 1h bar look up that date's level; LONG = `Low < level*0.999` (swept) AND
`Close > level and Close > Open` (rejected + bullish); entry = next 1h bar open;
SL = `atr_stop*ATR` (2.0); TP = `rr*risk` (2.0). In `mechanics_1h.py ::
prove_htf_grab`.

## Entry-design rule (non-negotiable)

Every new entry must: (1) NAME its driver, (2) REQUIRE the EVENT, not a bare RSI
level, (3) PASS the 3-test proof (10y IS PF>=1, walk-fwd OOS PF>=1, >=50% grid,
t-test p<0.05) before any ticket. Do NOT fall back to the symptom rule as "an
entry" — it is a filter, not a mechanic.

## Windows / yfinance-1h gotchas (when running the 1h loop)

- No `signal.alarm` (SIGALRM) on Windows → use `ThreadPoolExecutor` with
  `future.result(timeout=)` for per-symbol download timeout; fall back 2y→1y→6mo.
- `df._symbol` is DROPPED by `.iloc[]`/`.loc[]` slicing → pass `sym=` explicitly
  to triggers that need per-symbol context, or in/out-of-sample returns zero
  trades silently (false NOT_PROVEN).
- `profit_factor` returns `float("inf")` on zero losing trades; render as string
  `"inf"` before `json.dumps` or the edge is mis-flagged as "no data".
- yfinance 1h throttles after heavy same-session usage (some pairs hang) — use OS
  `timeout` per symbol; retry later. The module is correct.
- Run phase scripts with **system `python3`** (3.13), not the Hermes venv.

## Code pointers

- `mechanics_entries.py` — D1/D3/D4 triggers + `prove_trigger()` (daily, 10y).
- `mechanics_1h.py` — 1h loader (Windows-safe) + `_trig_htf_grab` + `prove_htf_grab`.
- `mechanics_practice_1h.py` — runs the gate GOs through the 1h proof.
- `inspect_metals_fx.py` — direct daily+1h structural read (the "why price here").
