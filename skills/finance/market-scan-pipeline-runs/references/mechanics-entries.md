# Mechanics-based entries (the "why price moves" layer)

Status: 2026-08-05 — user pushed explicitly for entries built on MARKET
MECHANICS, not the symptom-level `RSI<40 & close<VWAP` rule. The symptom rule
catches dead-cat bounces that fizzle; a mechanic entry requires the EVENT that
forces price to move. This is the durable reference. Permanent copy of the
driver model also lives at `D:\Hermes\MARKET_MECHANICS.txt`.

## The five drivers (what we can see in our data)

- **D1 Liquidity grab / stop-run reversal.** Price spikes through a prior
  swing low/high to sweep resting stop orders (forced selling), then snaps back
  because sellers are exhausted. Enter on the rejection candle. Biggest short-term
  mover. Implemented in `scripts/mechanics_entries.py` as `_trig_liqgrab`.
- **D2 Market structure (BOS + pullback).** Series of HH/HL (up) or LH/LL
  (down); after a break of structure, enter the pullback toward the break level.
  (Documented; not yet coded — structural continuation is harder to express as a
  single candle event. Flagged for a future leg.)
- **D3 VWAP reclaim with volume.** Price was below value, then closes back above
  VWAP on RISING volume — real participants funding the move, not a wick.
  Volume = confirmation. `_trig_reclaim`.
- **D4 Exhaustion / climax fade.** Volume spike (>2.5x avg) at an extended RSI
  with a reversal candle = the last chasers are in; nobody left to buy -> fade.
  `_trig_exhaust`.
- **D5 Session / regime timing.** Liquidity and directionality are not uniform
  across the session; macro gauge sets the backdrop (offensive longs fight the
  tape under EXTREME danger). A filter/context layer, not a trigger.

## What our data CANNOT see
True order flow / L2 / tape depth / tick delta, actual stop clusters (we INFER
them from swings + round numbers), dealer gamma / options flow. So our edge is
**structural + volume + auction**, which is enough for a real proven edge IF we
require the mechanic EVENT, not a static threshold.

## Entry-design rule (applies to every new entry)
1. Name the driver it exploits (1-5).
2. Require the EVENT (sweep+reject, reclaim+volume, exhaustion spike), not a
   bare RSI level.
3. Prove it via the 3-test harness (walk-forward OOS, param grid, t-test) before
   any ticket.

## The first finding (why this matters)
The 5 candidates that passed 10y-PF>=1.0 on the symptom rule ALL FAILED the
mechanics-aware proof: their per-trade R was statistically ~0 (t 0.8-1.6, p
0.10-0.43) — a few large winners dragging a near-breakeven strategy positive.
The symptom rule has no "why", so it cannot tell a real reversal from noise.

## How to extend
To add a mechanic: write a `_trig_*` fn in `mechanics_entries.py` returning a
list of per-trade R multiples, register it in `TRIGGERS`, then `prove_trigger`
runs the 3-test proof automatically. Keep functions side-effect-free on the
input frame (copy before adding `vol_avg`). D2 (structure) is the next candidate.

## Run it
```
cd /c/Users/victo
python3 mechanics_entries.py "USDJPY=X,GBPJPY=X,BNB-USD" "long,long,long"
# prints JSON: per (symbol,side,trigger) -> pf_in/out, grid_pass, sig t/p, verdict
```
Requires `robustness_proof.py` in the same dir (it imports `_load,_pf,_sig,rsi,
atr,vwap`). Heavy: 3 triggers x 108-combo grid x 10y per symbol — run
backgrounded with notify_on_complete.
