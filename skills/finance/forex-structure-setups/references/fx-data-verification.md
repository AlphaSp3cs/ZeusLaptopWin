# FX Data Verification (yfinance `=X` spot proxy)

Captured 2026-08-05 while building EUR/USD, USD/CHF, GBP/CAD, NZD/JPY setups.
The scanner produced a level that looked impossible (USD/JPY 1h low 156.2 vs
daily low 159.9 — a 3-yen gap that cannot both be true for the same window).
Root cause and the verification recipe that resolved it.

## The consistency check (run BEFORE trusting any level)

For every pair, pull BOTH frames and confirm the last close agrees:

```python
import yfinance as yf, pandas as pd, numpy as np
for t in ["EURUSD=X","USDCHF=X","GBPCAD=X","NZDJPY=X","USDJPY=X"]:
    d = yf.download(t, interval="1d", period="5d", progress=False, auto_adjust=False)
    h = yf.download(t, interval="1h", period="2d", progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex): d = d.droplevel(1, axis=1)
    if isinstance(h.columns, pd.MultiIndex): h = h.droplevel(1, axis=1)
    print(t, "daily close", round(float(d["Close"].iloc[-1]),5),
          "| hourly", round(float(h["Close"].iloc[-1]),5))
```

**Expectation:** daily last close ~= hourly last close (within a pip or two).
If they match, the feed is live and consistent — the "impossible" extreme was a
**frame/scope artifact**, not a market move.

## What the 2026-08-05 "anomaly" actually was

First scanner pass used `1d, period="3mo"` for the daily swing LOW and
`1h, period="5d"` for the intraday LOW. The 3-month daily low (155.26 for
USD/JPY) is legitimately far below the 5-day hourly low (156.22) — those are
*different lookback windows*, not a contradiction. The confusion came from my
comment labeling the 3-month extreme as if it were the same window as the
hourly data. Lesson: **when comparing daily vs intraday structure, state the
lookback explicitly** and never imply they must overlap. Once framed correctly,
all five pairs verified clean (daily close == hourly close to the pip).

## Pitfalls confirmed by this session

- **MultiIndex columns:** `yf.download` returns `(Close, TICKER)`; always
  `df = df.droplevel(1, axis=1)` before indexing or every access throws.
- **`=X` volume is 0** for FX (like cash indices `^`). VWAP unavailable -> use
  structure + ATR, never volume-weighted levels.
- **Stale frame:** if daily and hourly last close diverge by more than a few
  pips, re-pull with explicit `period` and inspect raw OHLC before publishing.
- **Timezone:** hourly bars carry `+01:00` stamps; ignore the tz, use the value.

## Why ATR-multiple TP (not absolute swings)

When price is already beyond nearby structure, deriving TP from the "next
historical swing low/high" can place a sell entry *below* current price (seen in
the first swing-plan cut). Fix: TP = `entry +/- k*risk` from the entry actually
traded. The intraday plan is always sign-correct; the swing plan should also use
ATR multiples or explicitly sorted structure *relative to current price*.
