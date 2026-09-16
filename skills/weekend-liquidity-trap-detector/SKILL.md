---
name: weekend-liquidity-trap-detector
description: "Use on weekends to detect low-volume pump/dump traps, widening spreads, and thin order books before they reverse. Prevents scam-pump losses."
user-invocable: true
metadata:
  version: "1.0"
  author: "OuroTaurus"
  tags: ["crypto", "weekend", "liquidity", "risk"]
---

# Weekend Liquidity Trap Detector

> **STATUS: DEAD (audited 2026-08-08).** This script runs, exits 0, and has never
> written a row to `pump_detections, volume_history`. It is scaffolding, not a data source.
> **Its silence is NOT 'no signal' — it is 'no data'.** Exclude it from any confluence
> count until `python3 ~/sentinel_audit.py` reports it LIVE. See skill `signal-provenance-audit`.

Quantifies weekend liquidity: volume vs 20-day avg, bid-ask spread widening, order-book
depth, and pump detection (>5% in <10min on low volume). Outputs reversal-probability warnings.

## Run it
```bash
cd ~/.hermes/skills/weekend-liquidity-trap-detector
python weekend_liquidity_detector.py check      # current liquidity health
python weekend_liquidity_detector.py outlook    # weekend risk outlook
```
## Notes
- No API key required.
- Log: `weekend_liquidity_detector.log`.
- Part of OuroTaurus gap-closure (Gap 5).
