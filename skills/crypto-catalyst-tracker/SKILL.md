---
name: crypto-catalyst-tracker
description: "Use to track upcoming crypto catalysts: upgrades, hard forks, governance votes, unlocks. Timeline view + countdown + High/Med/Low impact scoring for pre-event positioning."
user-invocable: true
metadata:
  version: "1.0"
  author: "OuroTaurus"
  tags: ["crypto", "catalysts", "events", "calendar"]
---

# Crypto Catalyst Tracker

> **STATUS: DEAD (audited 2026-08-08).** This script runs, exits 0, and has never
> written a row to `catalyst_events`. It is scaffolding, not a data source.
> **Its silence is NOT 'no signal' — it is 'no data'.** Exclude it from any confluence
> count until `python3 ~/sentinel_audit.py` reports it LIVE. See skill `signal-provenance-audit`.

Maintains a catalyst DB (upgrades, forks, unlocks, votes), shows a timeline, T-7 day
countdown alerts, and scores impact (High/Med/Low) to remind you to position pre-event.

## Run it
```bash
cd ~/.hermes/skills/crypto-catalyst-tracker
python crypto_catalyst_tracker.py daily
python crypto_catalyst_tracker.py weekly
```
## Notes
- Uses CoinGecko public API for event data.
- Deprecation warning on sqlite3 datetime adapter is harmless (Python 3.12).
- Log: `crypto_catalyst_tracker.log`.
- Part of OuroTaurus gap-closure (Gap 12).
