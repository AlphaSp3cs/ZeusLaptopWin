---
name: forex-structure-setups
description: Generate FX entry/SL/TP setups from real price structure.
---

# Forex Structure Setups

Class of task: the user names specific FX pairs with a direction and wants
concrete, checked **entry / stop-loss / take-profit** levels — usually both an
intraday (1h) and a swing (daily) plan. These are NOT the named scan pipelines
(`market-scan-workflows`); they are direct, on-request FX setup builds from raw
price structure. The user has asked for these repeatedly (fx majors recur
session to session — "the ones you had" = prior pairs).

## CRITICAL: instrument & basis disclosure (Victor enforces this)

- **State the basis on every FX setup.** The data source here is **SPOT FX via
  yfinance interbank / retail-CFD proxy** (`<PAIR>=X` tickers). It is **NOT a
  futures contract**. Broker feeds may differ by a few pips. Always print a
  one-line `BASIS: SPOT FX proxy` header so spot/futures are never conflated.
- **blogwatcher sentiment is crypto-only (BTC/ETH/SOL).** The standing
  "blogwatcher on every scan" rule does NOT cover FX. For FX setups you MUST say
  the per-symbol sentiment layer is **N/A** rather than implying coverage. Do not
  paste a crypto sentiment block into an FX report.

## Verified method (intraday + swing)

Both plans use the SAME mechanical core — only the timeframe of the swing
extremes and ATR changes. Do NOT derive TP from absolute historical swing levels
(see Pitfalls — that produced illogical entries).

For each pair fetch TWO frames:
- `1h`, `period="5d"` → intraday structure (recent swings, 1h ATR)
- `1d`, `period="3mo"` → swing structure (daily swings, daily ATR)

Then, per direction:

```
jpy = "JPY" in label
hatr = ATR(high, low, close)[-1]            # on the chosen frame
# recent swing high (ih) / swing low (il) within last 60 bars
if sell:
    entry = min(cur, ih - 0.2*hatr)        # current, or a pullback limit toward resistance
    sl    = ih + 0.6*hatr                   # stop ABOVE resistance
    risk  = sl - entry                      # positive
    tp_k  = entry - k*risk                  # k = 1.5 (TP1), 2.5 (TP2)
else:  # buy
    entry = max(cur, il + 0.2*hatr)         # pullback limit toward support
    sl    = il - 0.6*hatr                   # stop BELOW support
    risk  = entry - sl                      # positive
    tp_k  = entry + k*risk
```

Rounding: **JPY pairs → 3 decimals**, everything else → **5 decimals**.
R:R per TP = `abs(tp - entry) / risk` (target ≥ 1.5).

## HTF-ANCHORED LIQUIDITY GRAB (proven edge — the "why price moves" entry)

This is the entry that actually cleared the proof bar (first GREEN_PROVEN edge in
the project: GBPJPY long, ~2y 1h, in-sample PF 2.0 / walk-fwd OOS PF 3.0 /
grid 9/9 / t-test p=0.0037, n=70). It is the refinement of the bare liquidity
grab — the missing ingredient was **HTF anchoring**.

**Mechanic:** price drains liquidity below a DAILY level (prior-day low or daily
swing low — where retail stops actually sit) to fill size, then real participants
step in and drive it back. A grab only COUNTS if the 1h sweep hits a DAILY
liquidity level, not a random 1h wiggle. The bare 1h grab (sweep any local 1h
swing) was parameter-robust but sub-breakeven (USDJPY IS 0.83, t-test p 0.68) —
it was catching noise. HTF anchoring turned it into a significant, profitable,
robust edge.

**Implementation (reusable):** in `mechanics_1h.py` (`_trig_htf_grab` /
`prove_htf_grab`), the daily levels are precomputed per date from a 2y daily bar
pull: `prev_lo = prior-day low`, `prev_hi = prior-day high`, plus rolling daily
swing pivots (5-bar left/right over a 20-bar lookback). For each 1h bar, look up
the daily level for that date; LONG trigger = `Low < daily_level*0.999` (swept)
AND `Close > daily_level and Close > Open` (rejected + bullish). Entry = next 1h
bar open; SL = `atr_stop * ATR` (default 2.0); TP = `rr * risk` (default 2.0).
Note: pass the symbol explicitly to the trigger — **the `_symbol` attribute does
NOT survive `df.iloc[]` slicing**, so a sliced in/out-of-sample DataFrame loses
it and silently returns zero trades (this was a real, silent bug; see pitfalls).

**Proof bar it had to pass** (see `market-timing-mastery` "PROVE-PROFITABLE BAR"):
(1) in-sample PF>=1, (2) walk-forward OOS PF>=1, (3) >=50% of param grid PF>=1,
(4) per-trade R t-test p<0.05. GBPJPY cleared all four; USDJPY/CHFJPY/EURJPY did
NOT (borderline t-test, or OOS PF<1). So: the bias is real across JPY longs, but
only GBPJPY is green-lit so far — do not over-extrapolate to other pairs.

**Why 1h, not daily:** daily bars give ~60 grab events over 10y — t-test has no
power (p~0.5, "not proven" for the wrong reason). 1h bars give thousands of
events → real sample. Trade calendar depth (10y daily) for EVENT SAMPLE SIZE.
yfinance caps 1h history at ~2y — that's enough for mechanic edge.

## Data verification (run before trusting any level)

yfinance `=X` feeds are usually consistent, but verify before publishing:
- Confirm **daily last close ≈ hourly last close** for each pair (they should
  match; a multi-hundred-pip gap means a wrong frame or stale cache).
- If a swing extreme looks impossible (e.g. 1h low far below the daily low over
  the same window), re-pull `1d, "5d"` and inspect raw OHLC — the bug is almost
  always a stale/mismatched period, not the market.
- `yfinance` FX `=X` pairs carry volume 0 (like cash indices) — VWAP is
  unavailable; use structure + ATR, not volume-weighted levels.

## Report shape that works for Victor

Lead each setup with the basis + sentiment-N/A line, then per pair:
- spot last, ATR, intraday structure (H/L), daily range (H/L)
- INTRADAY: entry (mkt) + pullback limit, SL, risk, TP1, TP2, R:R
- SWING: entry, SL, risk, TP1 (R:R), TP2 (R:R)

Keep it terminal-plain (no markdown tables — Victor reads in CLI). Numbered
interpretation is optional; the levels are the deliverable.

## Pitfalls

- **SL/TP SIGN FLIP is the #1 bug.** For a SELL, TP must be BELOW entry and SL
  ABOVE; for a BUY the reverse. The naive `risk = entry - sl` gives a NEGATIVE
  risk for sells and flips TP direction. Use the sign-correct formulas above
  (`risk = sl - entry` for sell; `risk = entry - sl` for buy). This was debugged
  live in-session — a first cut printed sell TPs above entry. Verify by checking
  `entry > tp1 > tp2` for sells and `entry < tp1 < tp2` for buys before sending.
- **Do NOT set TP from absolute prior swing lows/highs.** When price is already
  above (buy) or below (sell) nearby structure, looking up "the next daily swing
  low below current" can place a sell entry BELOW the current price — illogical.
  Always derive TP as `entry ± k*risk` from the entry you actually trade.
- **JPY decimal places.** Rounding NZD/JPY or USD/JPY to 5 decimals makes levels
  nonsense (e.g. 92.77500). Use 3 decimals for any JPY pair.
- **`yfinance` multi-index columns.** `yf.download` returns a MultiIndex
  (`(Close, TICKER)`); `df = df.droplevel(1, axis=1)` before indexing, or every
  column access throws.
- **Session timezone.** Hourly bars carry a `+01:00` (or similar) tz stamp; don't
  assume UTC for the index — only the value matters for structure.
- **blogwatcher ≠ FX coverage.** Never imply RSS sentiment applies to EUR/USD
  etc. It's BTC/ETH/SOL only. State N/A.
- **SILENT `_symbol` loss on `.iloc[]` slicing (proof-killer).** When a trigger
  reads a custom attribute off the DataFrame (e.g. `df._symbol` for HTF daily
  levels), that attribute is DROPPED by `.iloc[]`/`.loc[]` slices. Passing a
  sliced train/test DataFrame to the trigger yields zero trades with no error —
  the in/out-of-sample PF then serializes as `null` and the edge looks
  NOT_PROVEN even when it's real. FIX: pass the symbol as an explicit parameter
  to the trigger, never rely on a DataFrame attribute surviving a slice.
- **JSON serialization of `inf` PF.** `profit_factor` returns `float("inf")`
  when there are zero losing trades; `json.dumps(inf)` emits `null`, which a
  downstream check reads as "no data". Render inf as the string `"inf"` before
  serializing so the edge isn't mis-flagged.
- **SCOPE = FX + METALS + ENERGY (user correction).** "Forex and metals" does NOT
  mean exclude energy. ALWAYS include Brent (BZ=F), WTI (CL=F), NatGas (NG=F) in the
  same setup sheet — user flagged the omission explicitly ("so nothing on oil even
  with Hormuz closed?"). Energy is part of the mover screen, not a separate ask.
- **VERIFY GEOPOLITICAL/SUPPLY-SHOCK PREMISES VS LIVE PRICE (critical).** Before
  building a "Hormuz closed / supply shock" oil setup, CHECK live Brent. A genuinely
  closed Hormuz prints Brent ~$100+ within hours; if Brent is ~$82 with weak RSI the
  "closed" premise is STALE/OPEN (impaired-but-flowing, e.g. Kpler ~75% flow reduction,
  not zero). Build oil as a geopolitical RISK-PREMIUM play (buy dip to support), NOT a
  breakout chase. On "explain in English"/"why": 1-sentence bottom line FIRST, then
  detail — drop BASIS/ATR/RSI jargon from the opener.

## Support files

- `scripts/fx_setup_scanner.py` — re-runnable scanner: fetches 1h+1d per pair,
  builds intraday + swing plans with the verified ATR-multiple method, prints
  terminal-plain. Edit the `PAIRS` / `PRIOR` lists at the top for the request.
- `references/fx-data-verification.md` — the daily-vs-hourly consistency check
  and the swing-level anomaly debugging recipe.
- `references/htf-liquidity-grab.md` — the proven HTF-anchored grab: full
  mechanic, daily-level precompute recipe, proof-bar results (GBPJPY green-lit),
  and the Windows/yfinance 1h gotchas. Condensed from the 2026-08-05 session.
