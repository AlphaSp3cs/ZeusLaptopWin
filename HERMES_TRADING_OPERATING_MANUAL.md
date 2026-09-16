# HERMES TRADING OPERATING MANUAL
## Single source of truth — rebuilt 2026-09-14
## Supersedes scattered notes. Read on session start.

================================================================================
## TABLE OF CONTENTS
1. Workflow Overview
2. Critical Bugs & Gaps (active issues)
3. Standing Rules
4. Scan Router
5. Backtest Engine
6. DCA Ladder
7. Sentinel Audit
8. FX+Metals+Energy Setups
9. Valuation Scorecard
10. Data Stores & Durability
11. What to Skip / What to Fix (Failure/Success Log pointer)
================================================================================

## 1. WORKFLOW OVERVIEW

The Hermes trading operating manual covers every automated and semi-automated
workflow in this workspace:

- **Scan Router** (`python3 ~/scan.py <mode>`) — single entry point for all scans
- **Backtest Engine** (`~/bt/bt_store.py` + `bt_runner.py`) — runs backtests vs REAL bars.db
- **DCA Ladder** (`~/dca_ladder_cron.py` wrapper) — refreshes tape then checks tranches
- **Sentinel Audit** (`~/sentinel_audit.py`) — proves which data sources are alive
- **Valuation Scorecard** (`~/valuation_scorecard.py`) — fundamental check before any equity buy

Every scan mode routes through the SAME rails:
1. danger_zone_gauge.py → regime risk score
2. blogwatcher/news → catalyst + repetition context
3. enhanced_trade_gate.py → the ONLY thing that authorises a candidate

Nothing here places an order. The gate outputs candidates; execution stays manual.

================================================================================
## 2. CRITICAL BUGS & GAPS (active issues — priority order)

### BUG-1: D: Drive Gone — bars.db Foundation Missing [CRITICAL]
- D:\Hermes\workflow does NOT exist
- bars_db.py hardcoded to ROOT = pathlib.Path(r"D:\Hermes\workflow")
- DB = ROOT / "data" / "bars.db" — bars.db is GONE
- scan.py BARS = pathlib.Path(r"D:\Hermes\workflow") — all bar refresh calls FAIL
- Impact: Every scan calling bars_refresh() fails. No bars = no scan.
- Fix: Either restore D: drive, OR migrate bars.db to C: and update ALL path refs.
- Files affected: scan.py (line 142), bars_db.py (line 37), market_open_ready.py

### BUG-2: Missing Workflow Scripts [CRITICAL]
- D:\Hermes\workflow\scripts\market_open_ready.py — MISSING
- Only backup exists: C:\Users\victo\hermes_backup_20260808\
- scan.py bars_ready() looks for this at BARS / "scripts" / "market_open_ready.py"
- Fix: Restore to C:\Users\victo\workflow\scripts\ and update scan.py path.

### BUG-3: Stale Nightshift Data [HIGH]
- Latest nightshift_scan_results: 2026-08-13 (32 days old)
- Crypto leg: 2026-08-07 (38 days old)
- Fix: Force fresh scan when D: / bars.db restored.

### BUG-4: AGENTS.md Context Overflow [MEDIUM]
- Current: 74,668 chars > 62,914 limit
- Fix: Trim AGENTS.md or use larger-context model.

### BUG-5: Kanban DB Corrupt [MEDIUM]
- sqlite3.OperationalError: no such table: tasks (loops every ~60s)
- Fix: `hermes db reset` or recreate kanban.sqlite.

### BUG-6: Search Backend Billing Exhausted [HIGH]
- Firecrawl/Nous billing: insufficient_funds (402)
- web_search and web_extract both dead
- Fix: Recharge Nous billing, OR switch to alternative search backend.

### BUG-7: prediction_sentiment Import Path [LOW]
- scan.py does importlib.import_module("prediction_sentiment")
- Must be on sys.path or import fails silently.
- Fix: Add C:\Users\victo to sys.path or use absolute import.

### BUG-8: MCP nemoclaw PermissionError [MEDIUM]
- Windows Error 5: Access is denied
- Fix: Check Windows permissions / reinstall nemoclaw.

### BUG-9: Nous Auxiliary Auth Missing [MEDIUM]
- "no Nous authentication found"
- Fix: `hermes auth` for Nous provider.

### BUG-10: OpenRouter Auxiliary PAID Lane [MEDIUM]
- PAID lane engaged — may incur spend
- Fix: Set auxiliary.free_only: true or use :free models.

================================================================================
## 3. STANDING RULES

1. **Two token stores**: config.yaml AND .env both have TELEGRAM_BOT_TOKEN.
   Hermes reads .env first. Always update BOTH.
2. **yaml.dump masks secrets**: Never use yaml.dump for config.yaml — it replaces
   secrets with ***. Use Python string writes.
3. **Status command lies**: `hermes gateway status` process detection is unreliable.
   Verify with `tasklist | grep hermes` + `gateway-stdio.log`.
4. **Token format**: Telegram tokens are BOT_ID:SECRET (46 chars after colon).
   Truncated tokens = instant reject.
5. **NO auto/cron/scheduled runs**: Universal rule — only run on explicit user ask.
6. **DCA ladder ALWAYS via wrapper**: `python3 "C:\Users\victo\AppData\Local\hermes\scripts\dca_ladder_cron.py"` — refreshes tape THEN checks.
7. **Long-horizon DRIP dividend book**: PEP/KO/SCHD/VYM/O remains the wealth base.
8. **On re-check**: Run `python3 ~/scan.py recheck`, report only DELTAS.
9. **On "good-to-accumulate"**: Say it OUTRIGHT — never buried in a table.
10. **FX+METALS setups**: Include ENERGY (Brent/WTI/NatGas) on same sheet.
    Verify geopolitical supply-shock claims vs LIVE price.
11. **On "explain in English"/"why"**: 1-sentence bottom line first, no jargon.
12. **Brutal honesty + backtest bug catching**: User values both.
13. **Rate-limit work**: Don't overheat the system. Work with care. Same as
    rate-limiting connections.

================================================================================
## 4. SCAN ROUTER

Command: `python3 ~/scan.py <mode> [options]`

Modes:
| Mode | Script | Output JSON |
|------|--------|-------------|
| premarket | universal_premarket_scan.py | universal_scan_results_latest.json |
| nightshift | nightshift_scan.py | nightshift_scan_results_latest.json |
| allsector | run_all_sector_workflow.py | (composite) |
| crypto | cerebro_crypto_weekend.py | (composite) |
| rsi | crypto_rsi_sweep.py | (composite) |
| bottom | crypto_bottom_rescreen.py | (composite) |
| ladder | dca_tape_refresh + dca_ladder_check | — |
| news | crypto_news_tracker.py | — |
| recheck | cerebro + crypto_news + dca_tape + dca_ladder | — |
| cryptofut | cryptofut_scan.py | (own JSON) |
| theories | theory_amplifier.py | (cached JSON) |
| income | covered_call_scan.py | — |
| allpop | full_population_sweep.py | — |
| allscan | comprehensive_scan.py | — |
| value | valuation_scorecard.py | valuation_latest.json |
| ready | market_open_ready.py | — |
| bars | bars_db.py --update | — |

Rails (every scan):
1. danger_zone_gauge.py --once → regime risk score
2. crypto_news_tracker.py --quiet → catalyst context
3. enhanced_trade_gate.py --scan-file <json> --equity <N> --profile both → GO/WATCH/NO-GO

================================================================================
## 5. BACKTEST ENGINE

Location: D:\Hermes\workflow\backtest\ (MASTER — never re-fetch yf)
Engine: ~/bt/bt_store.py + ~/bt/bt_runner.py

CRITICAL RULE: Backtest vs REAL bars.db only. Never re-fetch Yahoo data.
D:\Hermes\workflow\ is the canonical backtest store.

Options:
| Flag | Effect |
|------|--------|
| --start YYYY-MM-DD | Backtest start date |
| --end YYYY-MM-DD | Backtest end date |
| --equity N | Starting equity |
| --min-rr N | Minimum R:R filter |
| --tf 1d/1h | Timeframe |

================================================================================
## 6. DCA LADDER

Wrapper: `python3 "C:\Users\victo\AppData\Local\hermes\scripts\dca_ladder_cron.py"`
This refreshes tape THEN checks. Running dca_ladder_check.py alone evaluates
STALE levels and the 36h gate silently blocks all buys.

Assets covered: PEP, KO, SCHD, VYM, O (long-horizon DRIP wealth base)

Standing: ALWAYS run the wrapper, never the check alone.

================================================================================
## 7. SENTINEL AUDIT

Command: `python3 ~/sentinel_audit.py --json`

Proves which data sources are LIVE/DEAD/STALE. A dead sentinel is SILENT,
and silence gets misread as "no signal". Never count empty scaffolding as
a passing risk check.

================================================================================
## 8. FX+METALS+ENERGY SETUPS

FX Scan: forex_scan.py
Metals/Energy Scan: metals_energy_ai_scan.py
Gold/Oil Intraday: gold_oil_intraday_scan.py

Include ENERGY (Brent/WTI/NatGas) same sheet as metals.
Verify geopolitical supply-shock claims vs LIVE price.

================================================================================
## 9. VALUATION SCORECARD

Command: `python3 ~/valuation_scorecard.py TICKERS --json output.json`

Price/flow signals say WHEN. This says WHETHER the business is worth owning.
A scan candidate with no valuation read is an unverified candidate — same
rule as a dead sentinel: silence is not a pass.

================================================================================
## 10. DATA STORES & DURABILITY

D:\Hermes\workflow\ — Canonical backtest store. Code masters on C:, mirror to D:.
C:\Users\victo\ — Scan configs, JSON results, logs.

CRITICAL INCIDENT (2026-08-08): D: drive silently discarded a committed
1.2M-row write. A commit that returns cleanly is NOT proof the bytes survived.
ALWAYS verify bars.db row count after every write.

D: drive currently MISSING (2026-09-14). bars.db foundation is gone until restored.

================================================================================
## 11. WHAT TO SKIP / WHAT TO FIX

See: C:\Users\victo\Desktop\hermes_failure_success_log.md
(Full failure/success log with 27 failures to skip, 13 successes to repeat,
9 active issues to fix, 10 key rules, workflow status of every component)

================================================================================
## END OF MANUAL
