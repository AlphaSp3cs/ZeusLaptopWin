# yfinance 1.5.2 — live dividend/price fetch (Windows, py3.13)

Verified pattern used to pull LIVE price + TTM dividends + 3y weekly history
for a dividend backtest. Works on system Python 3.13 with `yfinance==1.5.2`.

## Traps hit and fixed
- `Ticker.history(progress=False)` -> **TypeError: unexpected keyword 'progress'**.
  yfinance 1.5.2 removed it. OMIT `progress` and `actions` from the call:
  `t.history(period="3y", interval="1wk", auto_adjust=True)`.
- Dividend Series index is **tz-aware** (America/New_York). Comparing to a naive
  `datetime` raises "Cannot compare tz-naive and tz-aware". Build a tz-aware now:
  ```python
  tz = getattr(divs.index, "tz", None)
  now = pd.Timestamp.now(tz=tz) if tz else pd.Timestamp.now()
  ttm = float(divs[divs.index >= (now - pd.Timedelta(days=365))].sum())
  ```
- `.dividends` attribute vs `get_dividends()` differ by version. Try attribute,
  fall back to method:
  ```python
  d = getattr(t, "dividends", None)
  if d is None or not len(d): d = t.get_dividends()
  divs = d.dropna()
  ```
- Price: prefer `t.fast_info["last_price"]`; else last `hist["Close"]`.

## Live yield + pay-cycle
- `live_yield = ttm_div / price * 100`
- Pay months from last ~2y of ex-div dates; map to JAJO/FMAN/MJSD/Monthly for the
  dividend-income cycle framework.
- Wrap each ticker fetch in a retry (3x, exp backoff) — yfinance throws transient
  network errors.
