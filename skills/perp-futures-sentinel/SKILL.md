---
name: perp-futures-sentinel
description: "Use when monitoring perp futures sentiment: funding rates, open-interest spikes, long/short extremes, liquidation clusters. Warns on crowded trades and squeeze setups."
user-invocable: true
metadata:
  version: "1.0"
  author: "OuroTaurus"
  tags: ["crypto", "futures", "funding", "sentiment"]
---

# Perp Futures Sentinel

> **STATUS: DEAD (audited 2026-08-08).** This script runs, exits 0, and has never
> written a row to `funding_rates, open_interest`. It is scaffolding, not a data source.
> **Its silence is NOT 'no signal' — it is 'no data'.** Exclude it from any confluence
> count until `python3 ~/sentinel_audit.py` reports it LIVE. See skill `signal-provenance-audit`.

Tracks perp funding rates, OI changes (>20% spike = alert), long/short ratio extremes,
and basis. Alerts on overcrowded shorts/longs (e.g. funding -0.5%).

## Run it
```bash
cd ~/.hermes/skills/perp-futures-sentinel
python perp_futures_sentinel.py hourly
python perp_futures_sentinel.py 4h
```
## Notes
- No API key required (exchange public endpoints).
- Log: `perp_futures_sentinel.log`.
- Part of OuroTaurus gap-closure (Gap 4).
