# Silent asset-class elimination in the scan pipeline

Diagnosed 2026-08-05 after the user said, angrily and correctly:
"I told you FOREX, COMMODITIES, INDICES and crypto, I was very specific,
you are not following orders."

The scan **did** load all four classes. The pipeline then eliminated every one
of them before the report, and three consecutive reports were handed over as
ETF-dominated without anyone noticing the mandate had been silently dropped.

## The tell that was missed three times

```python
from collections import Counter
d = json.load(open('universal_scan_results_latest.json'))
c = Counter()
for t in d['qualified_longs']:  c[(t.get('category'), 'LONG')]  += 1
for t in d['qualified_shorts']: c[(t.get('category'), 'SHORT')] += 1
print(sorted(c.items()))
```

Before the fixes this printed only `commodities / etfs / futures / indices`
in the raw scan, and the GO set after the gate was:

```
swing GO:  etfs 8, indices 3, futures 1
day   GO:  etfs 8, indices 3, futures 1
           forex 0 · commodities 0 · crypto 0
```

**Zero in a whole class is a bug signal, not a market observation.** Run this
breakdown after every scan and again after the gate.

## Defect 1 — forex was mathematically unable to qualify

`calculate_vwap()` in `universal_premarket_scan.py`:

```python
# BROKEN
if len(close) == 0 or np.sum(volume) == 0:
    return close[-1] if len(close) > 0 else 0
```

yfinance FX `=X` pairs report `volume: 0` on every bar. So VWAP collapsed to
spot, and `vwap_distance_pct` was exactly `0.00` for all 14 pairs:

```
EURUSD  px 1.1542  vol 0  vwap 1.1542  dist 0.00%
USDJPY  px 157.394 vol 0  vwap 157.394 dist 0.00%   <- RSI 23.9, invisible
```

The scorer requires VWAP deviation, so **forex could never score in any run.**

Fix — TWAP fallback (unweighted mean of typical price):

```python
if len(close) == 0:
    return 0
typical_price = (high + low + close) / 3
if np.sum(volume) == 0:
    return float(np.mean(typical_price))
return np.sum(typical_price * volume) / np.sum(volume)
```

After: USDJPY dist `-1.87%`, four JPY crosses qualified. Same class of bug
affects any volume-less feed (most cash indices).

## Defect 2 — CoinGecko free tier cannot serve this scan

The crypto leg looped ~50 sequential `/coins/{id}/ohlc` calls. The free tier
429s after roughly four, leaving `['BTC','ETH','USDT','BNB']` — one of which is
a stablecoin that can never produce a directional setup.

**Exponential backoff did NOT fix this.** It was tried first (2s/4s/8s, 4
attempts) and CoinGecko still refused every coin:

```
429 rate-limited on cardano, backing off 8s (attempt 3/4)
CoinGecko OHLC error for cardano: HTTP Error 429: Too Many Requests
```

Do not spend another session tuning backoff against this endpoint.

Fix — route crypto through yfinance `-USD` pairs, already a dependency, one
batched call, real volume:

```python
CRYPTO_YF_SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", ...]   # ~30 names
crypto_cat = {
    "symbols": CRYPTO_YF_SYMBOLS,
    "names": [s.replace("-USD", "") for s in CRYPTO_YF_SYMBOLS],
    "category": "crypto",
}
crypto_df = fetch_yfinance_batch(CRYPTO_YF_SYMBOLS, period="3mo", interval="1d")
crypto_results = scan_asset_class("CRYPTO", crypto_cat, crypto_df)
```

Result: 4 assets → 28. Note `scan_asset_class()` requires **both** `symbols`
and `names` keys — omitting `names` raises `KeyError: 'names'` and aborts the
whole scan before it writes, leaving the previous `_latest.json` in place (which
then looks like a successful run to anything checking only for a file).

Ticker quirks: some yfinance crypto symbols carry numeric suffixes
(`UNI7083-USD`, `SUI20947-USD`). MATIC may return no data.

## Defect 3 — liquidity-only failures vanished without trace

Commodities, futures and cash indices qualify in the raw scan, then die on the
H6 liquidity floor because the feed reports **contract counts** (or `$vol 0`
for `^`-prefixed indices) against an **equity dollar-volume** threshold:

```
RB: liquidity below swing floor for commodities ($vol 557 need 10,000,000)
^GDAXI: liquidity below swing floor for indices ($vol 0 need 100,000,000)
```

That is a data-shape mismatch, not a risk failure. Every other hard check
passed on these names.

Fix — a WATCH verdict, **without touching the risk floors**:

```python
verdict = "GO" if passed else "NO-GO"
if not passed:
    non_liq_hard_fail = any(not v for k, v in hard.items() if k != "H6_liq")
    non_liq_fails = [f for f in fails if "liquidity" not in f]
    if hard.get("H6_liq") is False and not non_liq_hard_fail and not non_liq_fails:
        verdict = "WATCH"
```

Also widen `all_validations = {"GO": [], "WATCH": [], "NO-GO": []}` (it is
indexed by verdict and will `KeyError` otherwise) and add
`watch_longs` / `watch_shorts` to the summary.

WATCH means: passes every risk check, blocked only on liquidity. **Not
sized-and-ready.** Report it as "trade a liquid proxy or size manually."

## Why the floors themselves were not changed

Changing liquidity floors decides what counts as tradeable with real money. A
wrong floor either hides good trades or green-lights something that cannot be
exited. That is the user's call. The agent asked; when no answer came it took
the conservative path — surface the setups as WATCH, leave the floors alone.
Do the same.

## Post-fix coverage (2026-08-05, 134 assets)

```
FOREX        14 scanned → 4 qualified   (previously structurally impossible)
COMMODITIES  16 scanned → 3L / 3S       (previously 0 GO)
INDICES      17 scanned → 7 short
CRYPTO       28 scanned → 5 qualified   (previously 4 assets, 1 a stablecoin)
```
