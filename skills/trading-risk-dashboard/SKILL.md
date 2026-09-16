---
name: trading-risk-dashboard
description: "Use for real-time portfolio risk view: exposure %, per-position stops, correlation matrix, VaR, drawdown vs -8% rule, and a Green/Yellow/Red risk odometer."
user-invocable: true
metadata:
  version: "1.0"
  author: "OuroTaurus"
  tags: ["risk", "portfolio", "var", "correlation"]
---

# Trading Risk Dashboard

> **STATUS: DEAD (audited 2026-08-08).** This script runs, exits 0, and has never
> written a row to `portfolio_exposure`. It is scaffolding, not a data source.
> **Its silence is NOT 'no signal' — it is 'no data'.** Exclude it from any confluence
> count until `python3 ~/sentinel_audit.py` reports it LIVE. See skill `signal-provenance-audit`.

Real-time risk monitor: total deployed %, auto-calculated stops, BTC/ETH/alt correlation
matrix, 1-day 95% VaR, drawdown tracker (enforces max -8% rule), and a risk odometer
(Green/Yellow/Red). Alerts on high correlation ("reduce alt exposure").

## Run it
```bash
cd ~/.hermes/skills/trading-risk-dashboard
python trading_risk_dashboard.py hourly     # live snapshot
python trading_risk_dashboard.py trade       # evaluate a new trade's risk
python trading_risk_dashboard.py report      # full report
```
## Notes
- Reads positions from `positions.db`. Verified to run.
- Log: `trading_risk_dashboard.log`.
- Part of OuroTaurus gap-closure (Gap 7).
