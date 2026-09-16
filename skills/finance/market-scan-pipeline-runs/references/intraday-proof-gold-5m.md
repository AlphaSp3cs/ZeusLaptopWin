# Intraday proof harness — gold 5m VWAP-bounce on capital.com (NOT PROVEN)

Condensed knowledge bank from the 2026-08-06 session. The runnable harness is
`scripts/gold_5m_proof.py`.

## The data ceiling (read this first)
yfinance caps intraday history at the LAST 60 DAYS. `period="5y"/"2y"/"1y"/
"6mo"/"3mo"` all return 0 rows for `GC=F` 5m with the error "5m data not
available ... must be within the last 60 days." Only `period="60d"` works
(13,757 bars, 2026-05-27 -> 2026-08-06 09:10 ET). Date-range `start=/end=`
queries for intraday also return 0 rows — yfinance intraday date-range is
broken; always use `period=`.

Consequence: the standing "mandatory 10y window" proof rule CANNOT be satisfied
for 5m bars from this source. Run the 3-test bar on the max 60d window and lead
with the horizon disclosure. Do not fabricate a decade of 5m bars.

## The strategy under test (recommended 5m gold set for capital.com)
- Core: 24h-rolling VWAP, EMA21, EMA50, RSI14, ATR14
- Confirm: relative volume (vol / 20-bar avg) > 1.2
- Filter: entries only in London (02:00-05:00 ET) or NY (08:30-11:00 ET)
- Long: uptrend (price > EMA21 > EMA50, above VWAP), price tags/pinned VWAP,
  RSI 40-60 turning up, volume ok -> enter next bar open, stop 1.5xATR, target
  2xATR (R:R 2.0). Mirror for short.
- Cost: net a measured capital.com round-trip of $5/oz (0.06% spread @ ~$4316).

## Results (60d window, net of cost)
| Test | Result | Value |
|------|--------|-------|
| T1 IS PF>=1.0 | FAIL | 0.38 |
| T2 Walk-fwd OOS PF>=1.0 | FAIL | 0.49 (last 1/3 of window) |
| T3 Param grid >=50% PF>=1.0 | FAIL | 0/162 combos |
| T4 t-test p<0.05 | PASS (bad) | p=0.029 — negative edge is statistically reliable |

Trades fired: 25 over 60d (9W/16L, 62% losers, mean -$4.98/oz).
VERDICT: NOT PROVEN. Do not trade this set on capital.com.

A first over-tight trigger (price within 0.15% of VWAP + RSI turn + vol + session
all at once) fired only 7 trades and lost harder (PF 0.74); widening the trigger
made it trade more but lose MORE, not better — so the failure is structural, not
a too-tight-filter artifact.

## Why it fails (the durable lesson — a broker-cost trap)
capital.com's 0.06% gold spread (~$5/oz RT) against a ~$10/oz 5m ATR = ~half a
bar of range paid in cost every round trip. A mean-reversion entry (1.5xATR stop
/ 2xATR target) is too tight for gold's 5m noise; stops clip before the
reversion pays. The edge would have to be huge to survive the spread; a VWAP
bounce isn't.

## Refinements to offer (re-run the harness on each — do NOT ship the loser)
1. Widen R:R: 2.5-3.0xATR target / 1.5xATR stop, London/NY overlap only.
2. Trend-follow not reversal: long when price > VWAP > EMA21 > EMA50, RSI>55,
   exit on VWAP cross. Plays gold's actual 5-min directional bursts.
3. Real 10y data via paid vendor (Polygon/Databento/capital.com history), then
   re-run the full proof bar on a decade.

## Reuse
Edit `backtest()` trigger or `SESSIONS` in `scripts/gold_5m_proof.py` for any
intraday edge proof. Keep `COST_PER_OZ` honest and the 60d `period=` cap. The
proof's job is to kill fragile intraday edges before they reach live margin —
treat a NOT_PROVEN as a correct, disciplined result, not a retry prompt.
