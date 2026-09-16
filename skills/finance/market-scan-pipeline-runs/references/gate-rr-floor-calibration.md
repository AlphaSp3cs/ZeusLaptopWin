# Gate R:R Floor = Calibration Cliff (not a risk screen)

Observed 2026-08-05 across the full daytime universal sweep (197 assets,
26L/39S pre-gate qualified).

## What happens

The universal scanner's `scan_asset_class()` sets T1 at *exactly* the gate's
minimum R:R (2.00 swing / 1.50 day). The enhanced gate then applies broker
costs on top. Because the entry is sitting on the floor, even a 0.01% spread
pulls **net** R:R just under it, so the setup fails H8 (net R:R floor) by a
hair.

Result that day:
- SWING: 0 GO / 65 NO-GO. Dominant binding reason:
  - 15x  "R:R to T1 is 2.00, floor is 2.0"
  - 2x   "net R:R after etoro costs is 2.00, floor 2.0 (gross 2.00; spread 0.40%)"
  - 2x   "net R:R after capital.com costs is 1.95, floor 2.0 (gross 2.00; spread 0.01%)"
- DAY: 3 GO / 62 NO-GO. Dominant binding reason:
  - 17x  "R:R to T1 is 1.50, floor is 1.5"
  - 3x   "net R:R after capital.com costs is 1.50, floor 1.5 (gross 1.50; spread 0.10%)"

So ~95% of the qualified book was rejected on the boundary, not on risk
mechanics. This is a **calibration artifact**, not a market statement.

## Do NOT loosen the floor silently

The R:R floor is a deliberate user risk control. "Fixing" the rejection by
dropping the floor manufactures a balanced ticket list out of nothing — that
is the exact error the kill-list / backtest discipline exists to prevent.

When you see this distribution, present it as a FINDING and give the user the
choice:

- **(a) Backtest the near-miss names** — the underlying rule may still have
  edge even if it can't clear the net-cost floor at this T1. Run
  `scripts/backtest_go_setups.py` on the qualified set (not just the GO set).
- **(b) Widen the floor deliberately** — only at the user's explicit say-so,
  and call it out in the report as a parameter change, not a discovery.
- **(c) Hold** — under an EXTREME DANGER gauge (>=75) the right move is often
  to size down / not trade, so a thin GO list is fine.

## How to aggregate the reasons cheaply

The validation record carries `binding_reason` (the single dominant fail) and
`all_fails` (full list). To build the mandated "gate rejection summary" grouped
by cause:

```python
import json, os
from collections import Counter

def no_go_reasons(profile_json):
    d = json.load(open(profile_json))
    c = Counter()
    for side in ("longs", "shorts"):
        for t in d.get(side, []):
            v = t.get("validation", {})
            if v.get("verdict") != "GO":
                c[v.get("binding_reason") or (v.get("all_fails") or ["?"])[0]] += 1
    return c

for name, f in (("SWING", "enhanced_setups_swing_latest.json"),
                ("DAY",   "enhanced_setups_day_latest.json")):
    print(name, "->", no_go_reasons(f).most_common(10))
```

The `binding_reason` string itself shows gross vs net-after-cost R:R, so you can
quote exactly how thin the margin was (e.g. "gross 2.00; spread 0.01%").
