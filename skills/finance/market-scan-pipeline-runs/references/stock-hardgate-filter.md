# Stock Hard-Gate Filter (standing rule, 2026-08-06)

The user mandated a permanent equity-screen on every scan: an equity may only
become a trade candidate when it shows a real liquidity event. This is now wired
into `universal_premarket_scan.py` (the scanner both the universal/daytime and
nightshift pipelines import). This file records the exact edits and a verification
snippet so a future session can confirm the gate is live without re-deriving it.

## The rule (verbatim intent)

> "relative volume has to be x4 on a stock at least for us higher than the 50day
> average relative volume when we scan, gapping up stocks, higher trade volume,
> stocks any price any market price."

Translation into the scanner:
- Equities (small_cap + micro_cap) need **relative volume ≥ 4.0× the 50-day average**
  AND, for longs, **gap up ≥ 1.0%** (today's open > prior close).
- No minimum share price, no minimum market cap ("any price, any market").

## Edits applied (universal_premarket_scan.py, verified 2026-08-06)

1. Constants — inserted right after `CRYPTO_YF_SYMBOLS = [...]`:
   ```python
   # STOCK SCAN HARD-GATE (standing rule)
   STOCK_CATEGORIES = {"small_cap", "micro_cap"}
   VOL_RATIO_FLOOR = 4.0     # x4 relative volume vs 50d avg, minimum
   GAP_UP_MIN_PCT = 1.0      # longs must gap up at least this much (%)
   ```

2. Volume block (inside `scan_asset_class`, after the existing 20d avg):
   ```python
   avg_volume_50 = np.mean(volumes[-50:]) if len(volumes) >= 50 else np.mean(volumes)
   vol_ratio_50 = volumes[-1] / avg_volume_50 if avg_volume_50 > 0 else 1
   opens = ticker_df["Open"].values
   gap_up_pct = ((opens[-1] - closes[-2]) / closes[-2] * 100.0) if len(closes) > 1 else 0.0
   ```

3. Store fields on `asset_result`:
   ```python
   "avg_volume_50": int(avg_volume_50),
   "vol_ratio_50": round(vol_ratio_50, 2),
   "gap_up_pct": round(gap_up_pct, 2),
   ```

4. Gate guards (after appending to `results["assets"]`, before LONG qualification):
   ```python
   is_stock = asset_data["category"] in STOCK_CATEGORIES
   vol_ok_stock = (not is_stock) or (vol_ratio_50 >= VOL_RATIO_FLOOR)
   gap_ok_long = (not is_stock) or (gap_up_pct >= GAP_UP_MIN_PCT)
   ```

5. LONG qualification line changed to:
   ```python
   if rr >= 2.0 and long_score >= 0.5 and atr > 0 and vol_ok_stock and gap_ok_long:
   ```
   SHORT qualification line changed to:
   ```python
   if rr_s >= 2.0 and short_score >= 0.5 and atr > 0 and vol_ok_stock:
   ```
   (both gate the stock liquidity event; non-stock classes are unaffected because
   `is_stock` is False → `vol_ok_stock`/`gap_ok_long` short-circuit to True)

6. Long/short reason annotations (for the report):
   ```python
   if is_stock:
       long_reasons.append(
           f"Stock liquidity event: {vol_ratio_50:.1f}x 50d vol, gap {gap_up_pct:+.1f}%")
   # same for short_reasons
   ```

## Verification snippet (run to confirm the gate is live)

```python
import universal_premarket_scan as ups
print(ups.STOCK_CATEGORIES, ups.VOL_RATIO_FLOOR, ups.GAP_UP_MIN_PCT)
src = __import__("inspect").getsource(ups.scan_asset_class)
assert "vol_ratio_50 >= VOL_RATIO_FLOOR" in src
assert "gap_ok_long" in src
```

## Calibration read (2026-08-06 — why zero stock setups is correct)

63 small/micro-cap stocks scanned, then counted by the gate's own fields:
- `vol_ratio_50 >= 4.0` : **0** stocks (highest was ASNS at 3.85× — and that one
  GAPPED DOWN -25% on a reverse-split/dilution, so not a long candidate anyway).
- `gap_up_pct >= 1.0` : 18 stocks, but NONE of them also hit 4× volume.

So the hard-gate produced **0 equity trade candidates** — exactly what the rule
demands on a day with no high-volume gap-up stock event. Do NOT loosen the floor
or synthesize stock entries to balance the book. When a real one appears it will
show `vol_ratio_50` and `gap_up_pct` in the scan JSON, and you layer the standing
blogwatcher + danger-zone regime read on top (small/micro-cap news coverage is
sparse — flag when a candidate lacks a per-symbol news read rather than implying it).

## Relationship to other rules

This is a *scanning* filter — it sits upstream of the enhanced trade gate. The
enhanced gate's 7 hard checks (R:R, liquidity, extension, etc.) still apply to
whatever the scanner passes through. The stock hard-gate only restricts WHICH
equities may reach the gate; it does not change gate verdicts for forex /
commodities / indices / crypto / ETFs.
