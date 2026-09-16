# Nightshift Gate JSON Shape

`nightshift_report.py` writes namespaced `nightshift_setups_day_latest.json` and
`nightshift_setups_swing_latest.json`. These are NOT the universal gate shape
described elsewhere (which uses `setups[].validation.verdict`).

## Top-level keys
`profile`, `account_equity`, `scan_timestamp`, `scan_source`, `scan_mode`,
`summary`, `validations`, `longs`, `shorts`

## Verdicts
- `validations`: dict with keys `GO`, `WATCH`, `NO-GO` — each a LIST of verdict dicts.
- `summary`: dict with `total_longs`, `total_shorts`, `go_longs`, `go_shorts`,
  `no_go_longs`, `no_go_shorts`, `watch_longs`, `watch_shorts`.
- `longs` / `shorts`: full candidate lists (lengths match the `summary` totals).

## GO verdict dict fields
```json
{ "symbol": "CT", "side": "SHORT", "verdict": "GO", "reason": "", "rr": 1.5, "deploy_pct": 20.0 }
```
NOTE: NO `entry` / `stop_loss` / `tp` / `rsi` here. Those live in the
`longs` / `shorts` lists (or the scan JSON). Pull them from there when rendering
a report table — do not expect them on the GO verdict.

## Verification one-liner (real run: 2026-08-08, ASIA session)
```python
import json
d = json.load(open('nightshift_setups_day_latest.json'))
print(d['summary']['go_shorts'], len(d['validations']['GO']))   # -> 10, 10
sw = json.load(open('nightshift_setups_swing_latest.json'))
print(sw['summary']['go_longs'], sw['summary']['go_shorts'])    # -> 0, 0
```

## Common mistake (false silent-failure trap)
Probing `d['setups']` or `x['validation']['verdict']` returns KeyError / nothing.
That makes a healthy 10-GO run look like a zero-result failure. Use the key map
above instead.
