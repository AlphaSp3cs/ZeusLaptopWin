# ZeusLaptopWin — Hermes Agent Backup

Backup of Hermes Agent state from Windows laptop.

## Contents
- `config/` — config.yaml, auth.json, SOUL.md
- `skills/` — all installed skills (autonomous execution, crypto scanning, etc.)
- `scripts/` — scan.py, bars_db.py, fetch_news_direct.py, position_tracker.py, etc.
- `memories/` — persistent memory entries
- `HERMES_TRADING_OPERATING_MANUAL.md` — workflow manual
- `hermes_failure_success_log.md` — failure/success log

## Scan Pipeline
1. `fetch_news_direct.py` → `news_headlines.json`
2. `download_comprehensive_universe.py` → `universe_comprehensive.json` (yfinance + binance + coingecko)
3. `scan_comprehensive_v2.py` → trader-ready setups with entry/stop/target + staleness alert + position log + feedback DB
4. `backtest_priority.py` → historical win rates
5. `position_tracker.py` → unified portfolio/risk tracking

## Standing Rules
- Code masters on C:, mirror to D:
- NEVER print secrets
- NO auto/cron/scheduled runs
- ALWAYS verify bars.db after writes
