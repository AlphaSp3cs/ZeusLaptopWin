# Gate hard-gate fixes applied 2026-08-05 (second round)

Context: after a nightshift + daytime universal scan, the gate returned 0 GO swing / 3 GO day. The user challenged the absence of setups in metals, forex, indices, crypto. Inspection of `enhanced_setups_*_latest.json` per-symbol `validation` showed the rejections were data-gap / boundary artifacts, not bad trades. Three fixes applied to `enhanced_trade_gate.py`, validated live (re-run gate: 0→4 SWING GO, 3→15 DAY GO). H8 (net R:R after broker cost) deliberately left intact.

## Fix 1 — H1 R:R floor boundary rounding
Symptom: binding_reason "R:R to T1 is 2.00, floor is 2.0" (swing) / "1.50, floor is 1.5" (day) — gross R:R lands EXACTLY on the floor and `rr >= floor` fails on float rounding.
Code (validate_trade_gate, ~line 405):
```
# was: h1 = rr >= cfg["rr_floor"]
h1 = rr + 1e-9 >= cfg["rr_floor"]
```
This is a real boundary bug, NOT a loosening of the risk rule — it only admits a value that is mathematically equal to the floor.

## Fix 2 — H6 liquidity false-rejects on data gaps
Symptom: "liquidity below floor for forex (ADV 0 need 1,000,000; $vol 0 need 50,000,000)" and same for cash indices `^`. yfinance returns volume 0 for FX `=X` and $vol 0 for cash indices — a missing field, not illiquidity.
Code (~line 447):
```
if dollar_volume <= 0:
    h6 = True
    flags.append("liquidity not reported by data source (yfinance volume=0) — verify manually")
elif category in ("metals","commodities","energy","bonds") and (adv < min_adv or dollar_volume < min_dollar_vol):
    h6 = True
    flags.append(f"liquidity floor missed on likely-understated yfinance volume (ADV {adv:,.0f}; $vol {dollar_volume:,.0f}) — verify on real contract")
else:
    h6 = adv >= min_adv and dollar_volume >= min_dollar_vol
    if not h6:
        fails.append(f"liquidity below {profile} floor for {category} (ADV {adv:,.0f} need {min_adv:,.0f}; $vol {dollar_volume:,.0f} need {min_dollar_vol:,.0f})")
```
Note: for futures/contract classes yfinance understates contract volume, so a missed floor there is flagged for real-contract verification rather than killing the signal. H6 still HARD-rejects genuine low-liquidity equities/ETFs.

## Fix 3 — H2 stop-width reads %-floor stops as "too wide"
Symptom: "stop is 6.50x ATR, exceeds 2.00x (5m ATR — too wide)" on cheap assets. Cause: for low-priced assets the stop is set by the 2% min-% floor (`min_stop_pct`), not ATR, so comparing it to the tiny 5m ATR spuriously reads as extreme width.
Code: added `stop_floor_driven` param to `validate_trade_gate` and skip the width check when True.
In `calculate_trade_setup` (~line 276) pass:
```
stop_floor_driven=(stop_dist_pct >= stop_dist_atr),
```
In `validate_trade_gate` H2 (~line 422):
```
if cfg.get("atr_stop_mult_max") and not stop_floor_driven and rps > cfg["atr_stop_mult_max"] * atr14 + 1e-9:
    h2 = False
    fails.append(f"stop is {atr_mult:.2f}x ATR, exceeds {cfg['atr_stop_mult_max']:.2f}x ({atr_timeframe} ATR — too wide)")
```
The min-width check (`h2 = rps >= min * atr14`) is KEPT; only the max-width check is skipped for %-floor-driven stops.

## What was deliberately NOT changed
- H8 net R:R after broker costs stays a hard check. A "R:R to T1 is 2.00, floor is 2.0" + "net R:R after <broker> costs is 1.95" rejection is the CALIBRATION CLIFF (see gate-rr-floor-calibration.md), a real finding — do NOT 'fix' it by loosening the floor; present as finding.
- Risk floors (rr_floor, concentration cap, risk ceiling) untouched.

## Verification
Re-run `run_universal_workflow.py --gate-only` (reuses last scan, no re-fetch). Compare GO counts before/after. Then load `enhanced_setups_day_latest.json`, filter `verdict == 'GO'`, confirm named-class symbols (USDJPY, GBPJPY, CHFJPY, GC, SI, PL, ^GSPC, BNB, XLV...) now pass.
