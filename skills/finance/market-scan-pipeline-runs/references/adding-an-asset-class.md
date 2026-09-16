# Adding a new asset class to the scanner (so it appears in every scan)

The scanner's universe is curated symbol lists (Finviz-style watchlists), NOT
pulled live from a website. "Add small caps like the website scanner does"
means: make a first-class asset-class group that flows through the same
`scan_asset_class()` path as every other class. Because the daytime **universal**
scan (the "hunt/scan" pipeline) and the **nightshift** scan (the "sonar"
pipeline) both `import` the same `ASSET_UNIVERSE` + `scan_asset_class()` from
`universal_premarket_scan.py`, one edit to that dict populates BOTH scanners.

## The 4 files you must touch

1. **`universal_premarket_scan.py`** — add a group to `ASSET_UNIVERSE`. The dict
   entry MUST have both `symbols` and `names` (parallel lists), and a `category`
   key that is the new class id (e.g. `"small_cap"`). `scan_asset_class()`
   iterates `ASSET_UNIVERSE` and routes every group through the same scorer.

   ```python
   "US_SMALL_CAP": {
       "symbols": ["BBW", "TZOO", "HROW", "NX", "CODI", ...],   # 1:1 with names
       "names":   ["Build-A-Bear", "Travelzoo", "Harrow Health", ...],
       "category": "small_cap",
   },
   ```

2. **`enhanced_trade_gate.py` — `SECTOR_PROFILES`** — add a per-profile risk
   profile so the gate knows how to size/stoploss the class. If you SKIP this,
   the gate falls back to `DEFAULT_PROFILE` (atr_stop_mult 1.5, conc 0.20) —
   wrong for thin/high-beta names. Small caps got wider stops:

   ```python
   "small_cap": {
       "swing": {"rr_floor": 2.0, "atr_stop_mult": 2.0, "risk_pct": 0.01, "concentration_cap": 0.10},
       "day":   {"rr_floor": 1.5, "atr_stop_mult": 1.25, "risk_pct": 0.005, "concentration_cap": 0.10},
   },
   ```

3. **`enhanced_trade_gate.py` — `LIQUIDITY_FLOORS`** — add a class-specific
   liquidity floor. **This is the trap.** If the new class is absent here, the
   gate uses `DEFAULT_LIQUIDITY` (ADV 100k / $10M) for the H6 liquidity hard
   gate. Thin small caps routinely trade < $2M/day and would FAIL liquidity
   every time, then emit a WATCH (or no verdict) — silently killing the whole
   class. Set the floor to a realistic thin-name level:

   ```python
   "small_cap": {"adv": 250_000, "dollar_volume": 2_000_000},  # thin caps - lower floor
   ```

4. **`make_universal_report.py` — `cat_order`** (local var inside the report
   builder fn) — insert the class id so the quant report groups it under its
   own header. Without this the class still scans and gates fine, but its GO
   setups get dumped under a default section with no grouping.

   ```python
   cat_order = ["crypto", "forex", "indices", "commodities", "bonds", "etfs", "small_cap", "futures"]
   ```

## The default-fallback gotcha (the part that bites)

`enhanced_trade_gate.py` resolves profile/floors via a chain: symbol-prefix
override → `category in SECTOR_PROFILES/LIQUIDITY_FLOORS` → `DEFAULT_*`. A class
id that is missing from step 2's dict is NOT an error — it silently inherits
generic equity-ETF risk params and the $10M liquidity floor. For a thin-name
class this shows up as "gate returns zero GOs / all WATCH" with no obvious cause.
**Always add the class to both `SECTOR_PROFILES` and `LIQUIDITY_FLOORS`.**

## Verify before declaring done (smoke test, no full scan)

Run a focused check on JUST the new group so you don't wait for the whole
multi-hundred-symbol universal scan:

```python
import universal_premarket_scan as ups
grp = ups.ASSET_UNIVERSE["US_SMALL_CAP"]
df = ups.fetch_yfinance_batch(grp["symbols"], period="3mo", interval="1d")
res = ups.convert_to_serializable(ups.scan_asset_class("US_SMALL_CAP", grp, df))
print(len(res["assets"]), len(res["qualified_longs"]), len(res["qualified_shorts"]))
assert {a["category"] for a in res["assets"]} == {"small_cap"}
from enhanced_trade_gate import get_sector_profile, get_liquidity_floors
assert get_sector_profile("small_cap", "BBW", "swing")["atr_stop_mult"] == 2.0
```

A live run of the above on 2026-08-05 fetched 35/44 small-cap symbols, qualified
4 longs + 3 shorts, with correct `small_cap` tagging and the gate resolving to
atr_mult 2.0 / ADV floor 250k.

## Overnight classification (nightshift)

`nightshift_scan.py:TRADEABLE_CLASSES` / `CORRELATION_ONLY_CLASSES` decide the
role of each `ASSET_UNIVERSE` group. Classes NOT listed there default to
**correlation-only** (scanned for regime context, setups stripped before the
gate). A NEW US-cash-session class (like US small caps) should stay
correlation-only in nightshift, because it does not trade overnight — verify
with `nightshift_scan._classify("small_cap") == "correlation"`. If you WANT a
new class tradeable overnight, add its category to `TRADEABLE_CLASSES`.
