---
name: on-chain-intelligence
description: "Use when you need on-chain data: whale flows, exchange netflow, MVRV/Z-score, stablecoin dry powder. Closes the 2-24h delay gap on accumulation/distribution signals."
user-invocable: true
metadata:
  version: "1.0"
  author: "OuroTaurus"
  tags: ["crypto", "on-chain", "whales", "glassnode"]
---

# On-Chain Intelligence

> **STATUS: DEAD (audited 2026-08-08).** This script runs, exits 0, and has never
> written a row to `exchange_flows, whale_movements`. It is scaffolding, not a data source.
> **Its silence is NOT 'no signal' — it is 'no data'.** Exclude it from any confluence
> count until `python3 ~/sentinel_audit.py` reports it LIVE. See skill `signal-provenance-audit`.

Aggregates on-chain signals (Glassnode-style): exchange inflows/outflows, top-100 whale
wallets, stablecoin supply ratio, MVRV Z-score, NUPL.

## Run it
```bash
cd ~/.hermes/skills/on-chain-intelligence
python on_chain_intelligence.py hourly     # quick poll
python on_chain_intelligence.py daily       # full report
```
## Notes
- Requires `GLASSNODE_API_KEY` in `.env` (free tier). Without it, whale/exchange-flow calls fail gracefully — verify the key before relying on output.
- Log: `on_chain_intelligence.log`.
- Part of OuroTaurus gap-closure (Gap 2).
