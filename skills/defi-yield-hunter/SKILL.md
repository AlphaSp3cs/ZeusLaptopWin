---
name: defi-yield-hunter
description: "Use when scanning DeFi for TVL shifts, yield opportunities (APY >20%), governance votes, or token unlocks. Surfaces DeFi re-rating plays."
user-invocable: true
metadata:
  version: "1.0"
  author: "OuroTaurus"
  tags: ["crypto", "defi", "yield", "tvl"]
---

# DeFi Yield Hunter

> **STATUS: DEAD (audited 2026-08-08).** This script runs, exits 0, and has never
> written a row to `tvl_history, yield_opportunities`. It is scaffolding, not a data source.
> **Its silence is NOT 'no signal' — it is 'no data'.** Exclude it from any confluence
> count until `python3 ~/sentinel_audit.py` reports it LIVE. See skill `signal-provenance-audit`.

DeFiLlama-backed TVL + yield tracker. Flags >10% weekly TVL shifts, ranks top yields,
and lists governance events.

## Run it
```bash
cd ~/.hermes/skills/defi-yield-hunter
python defi_yield_hunter.py daily
python defi_yield_hunter.py weekly
```
## Notes
- Uses public DeFiLlama API (no key needed).
- Log: `defi_yield_hunter.log`.
- Part of OuroTaurus gap-closure (Gap 3).
