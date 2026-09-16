---
name: crypto-price-alerts
description: "Use when you need real-time crypto price alerts (BTC/ETH/alts) with Telegram/Discord/webhook push and Zeus auto-execution. Catches entries/exits during off-hours (Asia session)."
user-invocable: true
metadata:
  version: "1.0"
  author: "OuroTaurus"
  tags: ["crypto", "alerts", "execution", "zeus"]
---

# Crypto Price Alerts

Live price-alert engine (CoinGecko free tier). Sets target levels, polls, and pushes
notifications.

> **STATUS: PARTIAL (audited 2026-08-08).** The alert engine genuinely works — 12 real
> alerts have fired (e.g. ETH $1,916.51 vs $1,856.90 target). But `--check` **exits 1**:
> it raises after triggering when Telegram is unconfigured. Alerts land in `alert_log`,
> delivery does not happen. Do not rely on being notified; read the DB.
> Note `price_history` is empty (0 rows) — no historical series is being kept.
> Re-verify with `python3 ~/sentinel_audit.py`. See skill `signal-provenance-audit`.

## Run it
```bash
cd ~/.hermes/skills/crypto-price-alerts
python crypto_price_alerts.py --list-alerts          # show active alerts
python crypto_price_alerts.py --check                 # poll prices vs alerts
python crypto_price_alerts.py --set-alert BTC --price 62000 --direction below
python crypto_price_alerts.py --clear-alerts
```
## Notes
- Telegram/Discord/webhook delivery requires gateway tokens in `.env`; without them alerts are logged only.
- DB: `price_alerts.db`. Log: `price_alerts.log`.
- Part of OuroTaurus gap-closure (Gap 1). Wire `--check` to a 15m cron once the gateway is up.
