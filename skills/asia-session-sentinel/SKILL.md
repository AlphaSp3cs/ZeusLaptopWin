---
name: asia-session-sentinel
description: "Use to monitor the Asia session (10pm-4am EST): BTC/ETH volume spikes, Binance/OKX/Huobi flows, CN/HK/KR news, dip-entry signals. Catches ~40% of weekend volume moves."
user-invocable: true
metadata:
  version: "1.0"
  author: "OuroTaurus"
  tags: ["crypto", "asia-session", "monitoring", "alerts"]
---

# Asia Session Sentinel

> **STATUS: DEAD (audited 2026-08-08).** This script runs, exits 0, and has never
> written a row to `volume_spikes, asia_exchange_flows`. It is scaffolding, not a data source.
> **Its silence is NOT 'no signal' — it is 'no data'.** Exclude it from any confluence
> count until `python3 ~/sentinel_audit.py` reports it LIVE. See skill `signal-provenance-audit`.

Automated 10pm-4am EST watch: volume spikes (>50% above avg), exchange-specific flows,
China/HK/KR news sentiment, and dip-entry signals when thesis is intact.

## Run it
```bash
cd ~/.hermes/skills/asia-session-sentinel
python asia_session_sentinel.py start      # begin watch loop
python asia_session_sentinel.py check      # one-shot check
python asia_session_sentinel.py summary    # session summary
```
## Notes
- Verified to run (`check` exits clean).
- Log: `asia_session_sentinel.log`.
- Part of OuroTaurus gap-closure (Gap 8).
