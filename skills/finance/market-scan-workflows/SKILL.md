---
name: market-scan-workflows
description: "Use when STARTING a market scan: pick the pipeline, ad-hoc/screenshot universes. Router."
---

# Market Scan Workflows

Covers the class of task: the user names a scan — **"do a nightshift scan"**,
"sonar scan of all sectors", "cryptoweekend scan", "premarket scan" — and expects
the existing local pipeline to be run end-to-end and summarized into a report.

## START HERE — the unified router (2026-08-08)

Every scan in this workspace now has ONE entry point:

    python3 scan.py <premarket|nightshift|allsector|crypto|rsi|bottom|ladder|news|recheck>

It runs the danger gauge first, the news overlay second, and
`enhanced_trade_gate.py` last — the gate is the only thing that authorises a
candidate. See `references/scan-router.md` for the mode table, why
`nightshift_scan.py` is the template for any new session scan, and the 22
archived duplicate scanners. Do NOT create a new `*_scan.py`; add a mode.

## How to report a scan to this user (style is part of the deliverable)

- **Lead with the decision in one line.** "DCA INJ now — $400" or "Nothing to
  do, 100% cash." Never open with methodology, and never open with a table.
- **Say DCA/BUY outright when warranted** — never bury an accumulate signal
  inside a table (standing rule; covers the dividend book too).
- **On re-checks report DELTAS, not the full table again.** The user says
  "check" / "scan again" / "continue checking" repeatedly; answer with what
  CHANGED since the last run.
- **Volunteer your own bugs and bad calls BEFORE the good news.** When a script
  crashed, a restore failed, or an earlier "it works" turned out wrong, open
  with that. This user explicitly values catching bugs over polish, and a
  failure disclosed late reads as a failure hidden.
- **Never dress up a failed backtest.** Zero GREEN means say zero GREEN, then
  say what the base rate supports instead. Do not promote AMBER to a buy.
- **Push back on 100x / moonshot asks with measured base rates**, not vibes.
  The user accepts the pushback when shown real numbers and asked for the
  brutal version — but show the numbers.
- **State infrastructure limits honestly and repeatedly.** Cron only fires
  while the Hermes scheduler is running; CLI sessions have no delivery channel
  for cron output. Never imply a reminder will reach them when it cannot.

## CRITICAL: nightshift is NOT the same pipeline as the others

These names are **not** all the same codebase. Most named scans (premarket,
sonar, cryptoweekend, sector) are the universal pipeline
(`universal_premarket_scan.py` → `enhanced_trade_gate.py`) run against the full
universe and framed for context. But **NIGHTSHIFT is a distinct scan with its
own scripts**, and conflating the two is the bug that was corrected in front of
the user.

**Nightshift = overnight markets only.** The scripts `nightshift_scan.py` and
`nightshift_report.py` (in the user's home dir) exist specifically for it. They
reuse the universal scanner's indicators but **split the universe by trading
session**:

- **TRADEABLE classes**: `forex`, `commodities`, `indices`, `crypto` — the
  markets actually open during the US overnight session. These produce real
  setups.
- **CORRELATION-ONLY classes**: `etfs`, `bonds`, `futures` — the US cash/listed
  session is *closed* at night. They are still fetched and scored for
  breadth/regime context, but their qualified long/short setup lists are
  **stripped before the gate**, so they can never become trade candidates in a
  nightshift scan. A nightshift report must NOT contain SPY/QQQ/XLF/TLT-style
  setups — those are closed-session instruments.

If you are asked for a nightshift scan, run the nightshift scripts
(`python3 nightshift_report.py`, or `--no-scan` to reuse the last scan), **not**
the full universal pipeline. Running the full universal scan for "nightshift"
produces ETF/futures setups that cannot be traded at night — that is wrong.

All nightshift outputs are **namespaced** (`nightshift_scan_results_*`,
`nightshift_setups_*_latest.json`) and must stay that way so they never clobber
the daytime universal pipeline files (`universal_scan_results_*`,
`enhanced_setups_*_latest.json`).

For premarket/sonar/sector/cryptoweekend, continue to use the universal
pipeline and frame per the named context below.

**Presence re-verified 2026-08-05:** `ls *.py` in the home dir returns both
`nightshift_scan.py` and `nightshift_report.py`, alongside
`sector_scan_comprehensive.py`, `run_all_sector_workflow.py`,
`generate_all_sector_report.py` and `linear_broker_sonar.py`. A prior session
recorded the nightshift scripts as absent; that was wrong. Still `ls` first,
but expect them to be present.

## Windows platform gotchas (discovered 2026-09-14)

### Bash eats PowerShell $ variables
When running PowerShell through the bash terminal, `$VAR` gets eaten by bash before PS sees it. Solutions:
- Write a `.ps1` file and run with `pwsh.exe -ExecutionPolicy Bypass -File script.ps1`
- Or wrap: `cmd /c "powershell -Command \"...\""` (fragile, avoid)

### Python interpreter — use the hermes venv for scan scripts
The system Python 3.13 (Windows Store) is **sandboxed** and cannot see `C:\Hermes\` or other user dirs outside its package. Scan scripts using `pathlib` will fail with `FileNotFoundError` on paths that exist. Always use the hermes venv Python:
```
C:/Users/victo/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe
```
In scans, prefer `os.makedirs(path, exist_ok=True)` over `pathlib.Path.mkdir(parents=True)` — it sidesteps the sandbox issue.

### D: drive → C: migration (2026-09-14)
D:\Hermes\workflow vanished between sessions. Code masters live on C:\ but reference D:\\Hermes\\. If D: is gone:
1. Create `C:\Hermes\workflow\{data,scripts,logs,reports,backtest}`
2. Patch `scan.py` line ~142: `BARS = pathlib.Path(r"C:\Hermes\workflow")`
3. Patch `bars_db.py` line ~37: `ROOT = pathlib.Path(r"C:\Hermes\workflow")`
4. Patch `market_open_ready.py` similarly
5. Copy scripts from `C:\Users\victo\hermes_backup_20260808\` if missing
6. Initialize bars.db: `python3 bars_db.py --init`
7. Copy sentiment skill to C:\Hermes\skills\ if scan.py references it there

Always verify with `ls /c/Hermes/workflow/` — if it shows `NOT FOUND`, the migration is needed.

### FOMC macro-event embargo (standing gate behavior)
enhanced_trade_gate.py blocks entries when a macro-event embargo is active (FOMC meetings). This is CORRECT behavior — report it as a gate doing its job, not a bug. Affected symbols show `"macro-event embargo active (FOMC) — entries blocked, exits unaffected"`.

### Firecrawl/Nous billing exhaustion
web_search and web_extract fail with `402 insufficient_funds` when Nous billing runs out. No workaround — must recharge. For news, try browser-based access to reuters.com / cnbc.com as fallback (also blocked when billing dead). Log honestly and move on.

## A scan that ends in tickets must be backtested

When the request includes the word "backtest", or asks for entry / stoploss /
takeprofit, a GO verdict alone is not enough to publish a trade. The gate
validates risk mechanics, not edge. Replay the entry rule on history before
writing the plan — see the `market-scan-pipeline-runs` skill and its
`scripts/backtest_go_setups.py`. Report positive-expectancy and
negative-expectancy GOs in **separate** tables, with an explicit DO NOT TRADE
block naming the losers. On 2026-08-05 the gate's whole index/sector short book
(SPY, QQQ, ^GSPC, XLK, XLI, XLF...) backtested at profit factors 0.32–0.68 and
had to be struck from an otherwise clean-looking GO list.

## AMPLIFY — theory confluence into all-sector scans

When the user says "amplify our theories" / "study the theories and use them in
all-sector scans", run this 4-stage pipeline (built 2026-08-08 against the 13-family
`crypto_theories_catalog.md`):

1. **STUDY** — grade each backtestable theory (T1 technical, T2 drawdown base-rate,
   T10 funding/OI, T11 breadth/regime) against the 3-TEST proof bar. Most are noise;
   only T2 (`<=-90%` from ATH) has MEASURED alpha (+109%/72% @24m).
2. **AMPLIFY** — stack sub-signals into ONE composite conviction 0-100 with
   `theory_amplifier.py`. Weights: T2 0.35 (only measured alpha), T11 0.25 (regime
   master gate), T1 0.25 (entry timing), T10 0.15 (live ccxt funding). `amplify(base, df)`
   is asset-class AGNOSTIC — pass any OHLCV frame with a 'Close' column and it scores
   T1+T2+T11; T10 only fires for the 19 mapped crypto roots, else contributes 0 (never
   fabricated). That IS the "use in all sectors" hook.
3. **BACKTEST the stacked signal** — not as a trade sim, but as a look-ahead-free
   forward-return band study (technique + the reason it's a 24m not a swing edge in
   `references/theory-amplify-pipeline.md`; the validation method is mirrored in
   trading-backtest-integrity). Confidence at bar k from data through k only; label =
   TRUE forward return 1m/6m/12m/24m. Real edge = monotonic ACCUMULATE>WATCH>AVOID AND
   top band beats the unconditional baseline.
4. **PORT** — `python3 scan.py theories` runs the amplifier + regime gauge + news
   overlay and writes `theory_amplifier_populated.json`. To drop into the universal /
   all-sector gate, enrich each candidate with `amplify(base, df).verdict` as a
   REGIME/conviction overlay (gates LONG bias; does NOT replace the trade_gate's risk
   mechanics).

CRITICAL DESIGN RULE (caught 2026-08-08): a RED regime (T11: price below MA200 and/or
MA200 falling) must HARD-CAP conviction at WATCH/AVOID. A 24-month accumulation thesis
(T2 deep-discount) is NOT a trade-timing signal and must never override a broken trend.

## Trigger conditions

- "do a nightshift scan", "run the sonar scan", "cryptoweekend scan",
  "premarket scan", "scan all sectors", "any scan at all".
- "amplify our theories" / "backtest the theories" / "use the theories in all-sector scans".
- User asks for overbought/oversold setups, VWAP setups, or qualified trades
  across asset classes.
- User pastes a **screenshot of a screener/watchlist** and asks which to buy.
  That is an ad-hoc scan over a user-supplied universe: same gates, same
  backtest bar. See `references/screenshot-watchlist-triage.md`.

## Ad-hoc universe from a screenshot

When the universe arrives as an image rather than from a pipeline:

1. `vision_analyze` first; on provider failure use `scripts/windows_ocr.ps1`
   (Windows built-in OCR, no install). Greyscale + upscale 3-6x with PIL
   LANCZOS first, and crop the left ~30% to read tickers — the numeric
   columns OCR unreliably and must be re-fetched from yfinance anyway.
2. Never trust a number read off the screenshot, and check the user's framing
   claim against the data (e.g. "most are penny stocks" was false — 3 of 11).
3. Apply the standing STOCK hard-gate and the news-protocol volume floor
   before forming any opinion, plus a dollar-volume sanity check: a name can
   pass 6x rel_vol and still be uninvestable at $3M/day.
4. Backtest the SETUP on each name's own 10y history, not just the pooled
   list — per-name replay is what vetoes gap-faders (GDRX PF 0.04, t=-3.87)
   that the momentum screen otherwise ranks highly.
5. Grade against the 3-TEST PROOF BAR and label AMBER when only part of the
   hold grid clears. One significant hold length does not prove the idea.
6. Publish an explicit DO NOT BUY list with a per-name reason, and label any
   momentum pick as outside the dividend DRIP sleeve.

## STANDING USER INSTRUCTION — blogwatcher on every scan

The user has stated explicitly: **every scan of any sort must integrate the
blogwatcher RSS news sentiment layer.** This is non-negotiable and applies to
sonar, nightshift, cryptoweekend, premarket — "any scan at all". A scan report
without a news-sentiment / regime-shift-risk section is incomplete.

Run `blogwatcher_integration.py` alongside the technical scan and fold its
`regime_shift_risk`, per-symbol sentiment, and macro events into the report's
regime section.

## The pipeline (premarket / sonar / sector / cryptoweekend)

Locate the real scripts before assuming anything. Typical chain:

1. `universal_premarket_scan.py` — scans the full universe (ETFs, stocks, bonds,
   futures, rates, forex, commodities, indices, crypto). Writes
   `universal_scan_results_latest.json` + a timestamped copy.
2. `enhanced_trade_gate.py` — applies 7 hard gates (R:R, stop width, size,
   concentration, earnings, liquidity, extension). Writes
   `enhanced_setups_swing_latest.json` and `enhanced_setups_day_latest.json`.
3. `blogwatcher_integration.py` — RSS news sentiment + macro events + regime
   shift risk. **Always run this.**
4. `danger_zone_gauge.py` — macro regime gauge 0-100 with signal breakdown.
5. `run_universal_workflow.py` — orchestrator with `--scan-only`, `--gate-only`,
   `--report-only`, `--dry-run` flags. Use `--dry-run` first to see the plan.

Find them with a narrow listing, not a recursive grep:

```bash
cd <home> && ls *.py | grep -iE "night|sonar|sector|universal|premarket|trade_gate|blogwatcher"
```

## Nightshift pipeline (distinct — do NOT use the universal chain above)

```bash
cd <home> && python3 nightshift_report.py            # full: scan -> gate -> blogwatcher -> gauge -> NIGHTSHIFT_SCAN_<DATE>.md
cd <home> && python3 nightshift_report.py --no-scan   # reuse nightshift_scan_results_latest.json
```

`nightshift_report.py` calls `nightshift_scan.main()`, runs the enhanced gate on
the nightshift scan writing **namespaced** `nightshift_setups_*_latest.json`,
pulls blogwatcher sentiment, reads `latest_gauge.json`, and renders the report.
The scan output shape is identical to the universal scan (so the gate and report
reuse the same code) but with extra `tradeable_assets_scanned`,
`correlation_assets_scanned`, and a `correlation_context` block (closed-session
assets with stripped setups).

## CRYPTO UNIVERSE — VALIDATE, DON'T ASSUME (learned 2026-08-07)

The crypto leg silently collapses if its ticker list contains delisted or
renamed symbols. yfinance `-USD` daily is the reliable source; CoinGecko's
per-coin path rate-limits (HTTP 429) and its OHLC loop is slow.

- **Delisted/renamed on yfinance (drop them or the universe shrinks):** `UNI-USD`
  (→ `UNI` trades elsewhere, not on yfinance), `MATIC-USD` (→ POL), `SUI-USD`,
  `APT-USD`, `RNDR-USD`, `GRT-USD`, `STX-USD`, `PEPE-USD`, `IMX-USD`, `FTM-USD`.
  Also drop legacy-mangled tickers like `UNI7083-USD`, `SUI20947-USD`.
- **Validated 43-coin canonical universe (real bars 2026-08-07):** BTC, ETH,
  BNB, SOL, XRP, DOGE, ADA, AVAX, TRX, LINK, DOT, LTC, BCH, NEAR, ICP, ETC,
  XLM, ATOM, FIL, HBAR, VET, INJ, AAVE, RUNE, ALGO, XMR, EGLD, THETA, AXS,
  SAND, MANA, CRV, MKR, AR, OP, TIA, SEI, WIF, FLOKI, DYDX, KAVA, ZEC, DASH
  (all `-USD`).
- **Single source of truth:** `C:\Users\victo\crypto_universe.py` exports
  `CRYPTO_YF_SYMBOLS` (the 43 above) plus the session map. Both
  `nightshift_scan._scan_crypto_yf()` and `universal_premarket_scan.CRYPTO_YF_SYMBOLS`
  import from it — keep them in sync by editing `crypto_universe.py` only.
- **Smoke-test after any universe change:**
  `python3 -c "import nightshift_scan as ns; print(len(ns._scan_crypto_yf()['assets']))"`
  must print **43**, not 15.

**SESSION / SHIFT COVERAGE — crypto populates in EVERY shift.** Crypto trades
24/7, so it must populate in all four sessions, not just "overnight". Tag each
run with its session so the report says which shift fired:
- ASIA (UTC 00–07), LONDON (07–13), NEW_YORK (13–21), OVERNIGHT (21–24).
- `crypto_universe.current_session(utc_dt)` returns the primary session;
  `crypto_session_coverage()` returns all four. Both report headers
  (nightshift + all-sector) now print "crypto populates in: ASIA, LONDON,
  NEW_YORK, OVERNIGHT".
- **Cover all shifts:** schedule the scan (cron) in all four sessions. See
  `references/crypto-universe-scan-shifts.md` for the ET↔UTC mapping and the
  cron-timing correction below.

## CRON TIMING — ET != UTC, VERIFY THE JOB LANDS IN ITS NAMED SESSION

A scheduled scan must actually run inside the session its name claims. In
summer the user is on **EDT = UTC−4**; in winter EST = UTC−5. A job created at
"37 20 * * *" (20:37 UTC) fires at **16:37 EDT = NEW_YORK session**, NOT Asia
(Asia is 20:00–03:00 ET). The session map is in UTC — convert before picking
the cron minute/hour.

- Asia open         → 20:37 ET  (`37 20 * * *` UTC in summer)
- London session    → 05:37 ET  (`37 09 * * *` UTC in summer)
- NY premarket      → 09:37 ET  (`37 13 * * *` UTC in summer)
- Overnight / NY close → 18:37 ET (`37 22 * * *` UTC in summer)
- **After creating any time-zone-bound cron job, re-read its `next_run_at`**
  and confirm the local hour falls inside the intended session. This session
  initially mis-set two jobs (14:37 UTC read as London but was NY; 02:37 UTC
  read as Asia but was overnight) and had to retime them.

## Workflow

1. **Discover, don't assume.** `session_search` for the scan name to find the
   standing instructions attached to it, then list the candidate scripts.
   For nightshift, use `nightshift_report.py` — not the universal scanner.
2. **Kick off the long scan in the background** with `background=true` and
   `notify_on_complete=true`. The universal scan takes minutes; nightshift
   shares the same yfinance/CoinGecko fetch so it is similar.
3. **Run blogwatcher in parallel** in the foreground while the scan runs — it is
   fast and its output frames the whole report.
4. **Run the trade gate** once the scan JSON lands. For nightshift this is done
   inside `nightshift_report.py` with namespaced outputs.
5. **Read the gauge** for macro regime context.
6. **Filter to GO verdicts only** before printing (see pitfalls).
7. **Write the report** to a dated markdown file and summarize in chat.

## Report shape that works for this user

Lead with regime, not with the trade list. The user wants to know the weather
before the tickets.

1. **Regime context first** — gauge value + interpretation, signal breakdown
   table, blogwatcher regime-shift-risk and per-symbol sentiment.
2. **Qualified setups (GO only)** — separate swing and day profiles, LONG and
   SHORT tables with entry / stop / T1 / R:R / size % / risk % / RSI. For
   nightshift these come ONLY from forex/commodities/indices/crypto.
3. **Raw pre-gate top signals** — top ~10 long and short with RSI and vs-VWAP,
   so the user sees what the gate rejected.
4. **The read** — numbered interpretation. This is the highest-value section.
   Call out cross-asset patterns (e.g. every global index simultaneously RSI
   65-68 AND 3.7-5.5% above VWAP = synchronized extension, not rotation).
5. **Execution posture** — a fenced block with bias, sizing, the actual orders,
   watch list, and an explicit DO NOT line.
6. **Gate rejection summary** — why setups were blocked, grouped by which hard
   gate failed. The user wants to know if a rejection was structural (liquidity
   floor on a futures contract) vs real (bad R:R).
7. **Artifacts table** — every JSON and markdown file path produced.

Flag coverage gaps honestly (e.g. "yfinance returned <43 crypto rows — N of 43
coins missing/invalid; re-run the crypto leg or check the delisted list") and
offer to re-run. Crypto now flows through yfinance `-USD` daily (not CoinGecko),
so a partial count means a ticker dropped off yfinance, not a 429.

## Pitfalls

- **Never dump the raw gate JSON.** Each setup carries a full `validation`
  object with metrics, hard-gate booleans, flags, and `all_fails`. Printing all
  candidates floods context with tens of thousands of characters. Filter to
  `validation.verdict == 'GO'` and project only the fields you will render.
- **The gauge script defaults to an infinite 60s-refresh loop — use `--once`.**
  `main()` is `while True: ... time.sleep(60)`. A `--once` flag was added
  2026-08-08 (compute → print → write `latest_gauge.json` → exit, ~2s); any
  scripted or subprocess caller MUST pass it. Without `--once` the call hangs
  until its timeout. Older guidance said to wrap it in `timeout 40` — that
  masked the loop rather than fixing it; prefer `--once`. It writes
  `latest_gauge.json`, the cheaper read once it has run at least once.
- **Parsing the gauge score: strip ANSI first.** The score token is wrapped in
  colour codes (`'Gauge: \x1b[91m\x1b[1m\x1b[5m 82.5/100\x1b[0m'`), so a naive
  `float(...)` raises, a bare `except` swallows it, and the score silently
  becomes `None` — the EXTREME-regime branch then never fires even though the
  line still PRINTS correctly. `re.sub(r"\x1b\[[0-9;]*m", "", out)` then regex
  `([\d.]+)\s*/\s*100`, and assert the parsed value is not None.
  See `references/verifying-scripted-integrations.md`.
- **Gauge generator lives in a SUBDIR — run it from there or it never refreshes.**
  `danger_zone_gauge.py` is NOT in the home dir; it is at
  `~/.hermes/gauges/danger_zone_gauge.py` and writes
  `~/.hermes/gauges/danger_zone/latest_gauge.json`. Running `python3 danger_zone_gauge.py`
  from the home dir fails with "can't open file" and the stale (possibly days-old)
  `latest_gauge.json` is silently read by the report. Always `cd ~/.hermes/gauges`
  first (or call it by absolute path) before the `timeout 40` wrap. If the gauge
  JSON's timestamp is older than the scan, the gauge did NOT refresh.
- **Do not use trailing `&` for backgrounding** — the terminal tool rejects it.
  Use `background=true` + `process(action='wait'|'log')`.
- **Recursive grep over the home directory times out.** `grep -ril <pattern> .`
  across a large home dir blows past 120s. Use `search_files` or narrow the
  listing with `ls *.py | grep`.
- **`process(action='wait')` clamps to 60s** regardless of the timeout you pass.
  For longer jobs, poll repeatedly or use `action='log'` after the notify fires.
- **Cash indices (`^`-prefixed) report $0 dollar-volume in yfinance**, so they
  fail the liquidity hard gate every time. This is a data artifact, not a real
  rejection — say so in the report rather than presenting DAX/FTSE as untradeable.
- **Zero qualified longs is a signal, not an error.** When the day profile passes
  0 longs and the gate only clears defensive names (utilities, long-duration
  Treasuries), report that as the finding. Do not loosen the gate to manufacture
  a balanced list.
- **Nightshift must not leak closed-session setups.** If a nightshift report
  shows SPY/QQQ/XLF/TLT/ETFs/bonds/futures as GO setups, the run used the wrong
  pipeline (full universal scan, not `nightshift_report.py`). Re-run with the
  nightshift scripts and confirm the gate outputs are `nightshift_setups_*`.
- **A low asset count means items were silently dropped.** The per-item
  `try/except ... continue` in the scan loops turns logic errors (e.g. an
  undefined variable in the scoring block) into missing assets with only a
  terse `[crypto TRX] skip: ...` line. If a class returns fewer assets than
  its symbol list, grep the run output for `skip:` before reporting.
- **Nightshift crypto silent-drop check.** The main nightshift scan's crypto
  path (`_scan_crypto_yf`) now carries all 43 validated coins directly via
  `crypto_universe.py`. A crypto-less or partial nightshift is the
  highest-risk "success-looking" state. After the run, confirm the crypto
  `assets` count is ~43 and BTC volume is a REAL number in
  `nightshift_scan_results_latest.json`. Divergence (e.g. 0.0 volume vs ~21.6B)
  is a data bug, not a quiet market. The separate `nightshift_crypto_leg.py`
  re-gates the SAME 43 coins for an independent namespaced file — it no longer
  adds breadth, so don't cite "run it for wider coverage".
- **Never default a missing indicator to 0.0 to make code run.** `ema200 = 0.0`
  makes `price > ema200` trivially true and silently awards a free uptrend
  bonus to every asset. Use `None` plus an `is not None` guard, so an
  unavailable indicator contributes nothing instead of contributing a lie.
- **Never synthesise a value to make a row pass a gate.** If a required input
  is genuinely absent (no ATR on a flat screener payload), leave it 0/None so
  the evaluator BLOCKS with an explicit reason. A fabricated breakeven level
  is worse than a rejected candidate.

- **Nightshift gate JSON has a DIFFERENT shape than the universal gate.**
  `nightshift_setups_day_latest.json` / `nightshift_setups_swing_latest.json`
  do NOT contain a `setups` key and do NOT use `validation.verdict`. Read the GO
  list from `validations['GO']` (a list) and counts from `summary.go_longs` /
  `summary.go_shorts`; the full long/short candidate lists are under `longs` /
  `shorts`. Each GO dict carries only `symbol`, `side`, `verdict`, `rr`,
  `deploy_pct` — entry / stop / T1 / RSI are NOT on the verdict (the report
  renders them from the `longs`/`shorts` lists or the scan JSON). Probing
  `setups[].validation.verdict == 'GO'` returns nothing and makes a real run look
  like a zero-result failure — a classic false "silent failure". See
  `references/nightshift-gate-json-shape.md`.

- **Orchestrator SCRIPT paths can be stale and crash the run before scanning.**
  `run_all_sector_workflow.py` hardcodes `SECTOR_SCAN_SCRIPT` and
  `VALIDATE_GATE_SCRIPT` at `skills/trading/...` subdir paths that do NOT exist on
  this machine, so it fails its `check_file()` guard and never scans. Before
  running it, confirm every `Path(...)` it references exists; the real files are
  `C:\Users\victo\sector_scan_comprehensive.py` and
  `C:\Users\victo\.hermes\ouroboros_backup\skills\trade-gate\scripts\validate_gate.py`.
  Sanity-check with `python3 run_all_sector_workflow.py --dry-run` (prints the
  resolved plan without executing).

## Verify scan output against a second source before trusting it

Scan pipelines fail SILENTLY far more often than they crash. A report that
renders cleanly is not evidence the numbers are real. Before reporting a
scan result — especially a zero/empty result — cross-check the same symbol's
metrics against another pipeline in the same codebase at the same timestamp.
Divergence on the SAME asset is the tell (e.g. BTC volume 18.3B in the
daytime universal scan vs 0.0 in nightshift = a nightshift data bug, not a
quiet market).

"No candidates found" is the highest-risk success-looking state. Always ask
whether the lookup *could* have matched at all before accepting zero.

Confirmed silent failures found this way, with fixes and the audit method:
see `references/silent-data-failures-audit.md`. Read it before wiring any new
data layer into a scan.

## Support files

- `references/system-bug-sweep.md` — ordered checklist for "sweep the system
  for bugs / make sure nothing's broken before Monday": compile → loop hunt →
  mock-data → cron resolution → state keys → FORCE every refusal path → money
  invariants → contamination → price cross-checks. The broad checks pass; the
  guard-forcing checks find things.
- `references/verifying-scripted-integrations.md` — how to prove a tool you
  wired into the pipeline actually works: the silent ANSI-parse failure that
  killed the EXTREME-regime branch while output still looked correct,
  `while True` monitors that hang subprocess callers, the AST import sweep for
  safely archiving duplicate scripts, and why late background notifications are
  free verification evidence. Read before wiring any tool into `scan.py`.
- `references/scan-router.md` — mode table for the unified `scan.py` entry
  point, why `nightshift_scan.py` is the template for new session scans, and
  the 22 archived duplicate scanners.
- `references/screenshot-watchlist-triage.md` — full workflow for the
  "here's a screener screenshot, which do I buy today" class: OCR fallback,
  gate order, per-name setup backtest, conviction pick shape.
- `scripts/windows_ocr.ps1` — Windows built-in OCR (Windows.Media.Ocr) for
  reading pasted screenshots when the vision model is unavailable.
- `references/nightshift-scan-worked-example.md` — a full worked nightshift run:
  the tradeable/correlation split, pipeline invocation order, the regime
  readings, and the finished report shape.
- `references/nightshift-crypto-coverage.md` — dual-path crypto coverage recipe
  (main scan + separate crypto leg) and the BTC-volume silent-drop cross-check.
- `references/crypto-universe-scan-shifts.md` — the validated 43-coin universe,
  the delisted-yfinance list, the 4-session UTC map, and the ET↔UTC cron-timing
  correction for covering all shifts.
- `references/silent-data-failures-audit.md` — six real silent-failure bugs
  (symbol key drift, substring symbol matching, hardcoded zero volume,
  NameError swallowed by per-item try/except, close-only ATR, non-idempotent
  logging) plus the verification method that surfaced them.
- `references/theory-amplify-pipeline.md` — theory-amplify 4-stage pipeline detail:
  theory_amplifier.py sub-scores, ccxt funding SWAP-symbol fix, look-ahead-free
  forward-return backtest method, and the 24m-edge finding. Read before building
  or re-running `scan.py theories`.
- `references/nightshift-gate-json-shape.md` — exact key map of
  `nightshift_setups_*_latest.json` (`validations` / `summary` / `longs` /
  `shorts`) vs the universal gate's `setups[].validation.verdict`, plus a
  verification one-liner. Read this before probing nightshift gate output.
