---
name: token-unlock-sentinel
description: "Use for token-unlock / supply-shock warnings: 7/30/90-day unlock calendar, % of circulating supply (alert >5%), and historical unlock reactions."
user-invocable: true
metadata:
  version: "1.0"
  author: "OuroTaurus"
  tags: ["crypto", "unlocks", "supply", "risk"]
---

# Token Unlock Sentinel

> **STATUS: DEAD (audited 2026-08-08).** This script runs, exits 0, and has never
> written a row to `upcoming_unlocks`. It is scaffolding, not a data source.
> **Its silence is NOT 'no signal' — it is 'no data'.** Exclude it from any confluence
> count until `python3 ~/sentinel_audit.py` reports it LIVE. See skill `signal-provenance-audit`.

Tracks upcoming unlocks via CoinGecko/TokenUnlocks, flags >5% circulating-supply shocks,
and reports how price reacted to past unlocks.

## Run it
```bash
cd ~/.hermes/skills/token-unlock-sentinel
python token_unlock_sentinel.py daily
python token_unlock_sentinel.py weekly
python token_unlock_sentinel.py scan 14     # next 14 days
```
## Notes
- Uses CoinGecko public API (no key). TokenUnlocks enrichment optional.
- Log: `token_unlock_sentinel.log`.
- Part of OuroTaurus gap-closure (Gap 11).
