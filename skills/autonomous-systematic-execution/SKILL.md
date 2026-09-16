# Autonomous Systematic Execution

## Behavior Rules
1. On session start or when user asks to work - scan workspace for pending tasks and execute in optimal order.
2. Execute in this order:
   a. News aggregation
   b. Market scan (all sectors, all assets)
   c. Backtest (historical win rates)
   d. Cross-reference + report
3. Don't wait for explicit instructions - if work is obvious, start immediately.
4. Save all outputs to C:\Hermes\workflow\data\

## Data Sources
- News: fetch_news_direct.py
- Universe: download_comprehensive_universe.py
- Scans: scan_comprehensive_setups.py
- Backtest: backtest_priority.py
- 9-sector: bt/bt_runner.py

## Standing Rules
- NO auto/cron/scheduled runs - only on explicit ask
- NEVER place live orders without confirmation
- NEVER print secrets
- ALWAYS verify bars.db after writes
- Code masters on C:, mirror to D:
