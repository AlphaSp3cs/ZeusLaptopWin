---
name: market-scan-pipeline-runs
description: Use when a scan is RUNNING/failing: gate, staleness, proof bar, pitfalls. Deep reference.
---

# Market Scan Pipeline Runs

Covers the class of task: "run a market scan" — nightshift, premarket, sonar,
sector scan, crypto weekend, or any named scan the user asks for. These are
multi-phase pipelines (scan → gate → sentiment → regime → report), not single
scripts.

## Trigger conditions

- User says "do a nightshift scan", "premarket scan", "sonar scan", "crypto
  weekend scan", "scan all sectors", or any named scan.
- User asks to re-run or refresh scan results.
- Any request that ends in a trade-setup list with entries and stops.

## STANDING USER RULE: blogwatcher sentiment in EVERY scan

The user gave a standing instruction: **any scan of any sort** must integrate
`blogwatcher_integration.py` RSS news sentiment. Not just crypto scans — every
scan. Run it and fold `regime_shift_risk`, per-symbol alignment/impact, and
macro headlines into the report. Do not treat this as optional or ask whether
they want it.

### Blogwatcher matches symbols by WORD BOUNDARY, not substring (fixed 2026-08-06)

`analyze_sentiment_for_symbols()` originally used a bare `sym in title`
substring test against an upper-cased title. Every short ticker collided with
ordinary English: `CL` matched "MARKETS **CL**OSE", `ES` matched "T**ES**LA",
`SI` matched "SHORT **SI**GNAL", `TOPS` matched "STOCK TOPS ESTIMATES". A live
100-article run returned 21 "news" keys, nearly all garbage.

This is not cosmetic — those keys drive CONVICTION ranking, so a bogus
`SI BULLISH` tag flips a Silver SHORT to CONFLICT and re-orders the deploy list.

Fixed via `_symbol_in_title()` in `blogwatcher_integration.py`: `$TICKER` always
matches; full-name aliases (BITCOIN→BTC, SILVER→SI, CRUDE OIL→CL) are checked
**before** the length guard; 1–2 char tickers and English-word tickers
(`_ENGLISH_WORD_TICKERS`: NEAR, TOPS, LINK, OPEN, GAS, CORE...) match only via
`$`. Live keys dropped 21 → 6, all real.

`_ENGLISH_WORD_TICKERS` is inherently incomplete — when a nonsense symbol
appears in a report's news section, add the word to that set. Details, the
alias-before-length-guard ordering trap, and the 18-case test in
`references/blogwatcher-symbol-matching.md`.

## NIGHTSHIFT: check for dedicated scripts, else use the universal chain

**Verify which case you are in before running anything** — this has been wrong
in both directions across sessions:

```bash
ls *.py | grep -iE "night|sonar|sector|universal|premarket|trade_gate"
```

**Case A — dedicated nightshift scripts exist** (`nightshift_scan.py` /
`nightshift_report.py`): use them. They split the universe by trading session:

- **TRADEABLE**: `forex`, `commodities`, `indices`, `crypto` (open overnight).
- **CORRELATION-ONLY**: `etfs`, `bonds`, `futures` (US session closed at night).
  Scanned for breadth/regime context but their qualified setup lists are
  **stripped before the gate** — they never become trade candidates.

Run with `python3 nightshift_report.py` (or `--no-scan` to reuse the last
`nightshift_scan_results_latest.json`). They write **namespaced**
`nightshift_setups_*` outputs.

**USER PRESENTATION ORDER — STANDING PREFERENCE (2026-08-06).** The user wants
nightshift setups presented **by asset class, not by profile**. The default
`nightshift_report.py` renders the GO tables grouped by *profile* (Section 2
SWING then Section 3 DAY), which the user does NOT want — they ask for
"commodities and metals first, then forex, last indices and crypto." When you
run the pipeline, re-order the setups into:
    **commodities / metals → forex → indices → crypto**
before showing them. The gate JSON (`nightshift_setups_day_latest.json` /
`nightshift_setups_swing_latest.json`) carries `category` on every setup, so
sort GO rows by category-priority then side. A ready sorter:
`scripts/reorder_gate_by_class.py` (reads the namespaced outputs from the home
dir, prints GO rows in class order + NO-GO/WATCH reasons). Lead the verbal read
with the regime block, then the class-ordered setups, then blockers. Always name
the profile each setup belongs to (swing vs day) in the output even when ordered
by class.

**CRYPTO ABSENCE IS A COVERAGE FACT, NOT A GATE REJECTION.** When the user asks
for "crypto last" and the GO list shows zero crypto, distinguish the two
meanings before reporting:
- If crypto produced **0 pre-gate qualified signals** (the scan's
  `qualified_longs`/`qualified_shorts` have no `asset_class == "crypto"`), say
  plainly: crypto had no tradeable signals this run (thin data leg / no qualified
  setups) — this is NOT a gate rejection and must not be dressed as one.
- Per the standing rule, `blogwatcher_integration.py` sentiment covers only
  BTC/ETH/SOL; that read feeds the overall `regime_shift_risk`, it is NOT a
  per-coin setup. Don't imply crypto coverage where it doesn't exist.
Verify with the `Counter`-over-`asset_class` check in the MANDATORY coverage
section before asserting "no crypto."

**CORRECTION 2026-08-05 (later session): Case A is the reality.** A direct
`ls *.py | grep -iE "night|..."` returned **both `nightshift_scan.py` and
`nightshift_report.py`** present in the home dir, alongside the universal chain.
An earlier note in this skill claimed they were absent; that claim was wrong.
This is exactly why the instruction is to `ls` first and trust the listing over
any prose — including this paragraph. Re-check every time.

## STANDALONE NIGHTSHIFT CRYPTO LEG (re-run crypto on demand)

Sometimes the nightshift universe silently produces **0 qualified crypto
signals** even though crypto is tradeable overnight — a thin data leg, not a
gate rejection (see the coverage-fact note above). When the user wants crypto
shown LAST and judged on its own (their explicit order: commodities/metals →
forex → indices → crypto), run a **dedicated crypto leg** so the crypto read is
real and gate-consistent with the other three classes, instead of an empty
placeholder.

The reusable runner is `scripts/nightshift_crypto_leg.py`. It does exactly what
the main scanner does for crypto but in isolation:

1. `ups.fetch_yfinance_batch(ups.CRYPTO_YF_SYMBOLS, period="3mo", interval="1d")`
   — the SAME 28 `-USD` symbols `nightshift_scan.py` uses for crypto (yfinance
   path, not CoinGecko, which 429s).
2. `ups.scan_asset_class("CRYPTO", crypto_cat, crypto_df)` — note the cat dict
   needs BOTH `symbols` AND `names` keys, else `scan_asset_class` errors.
3. Feeds the qualified longs/shorts to the SAME `gate.process_all_setups(scan_data,
   profile, account_equity=100000)` → GO/NO-GO verdicts, sizing, R:R are directly
   comparable to the commodities/forex/indices nightshift setups.
4. Writes **namespaced** `nightshift_crypto_*` files (scan + swing + day) so it
   never clobbers `nightshift_setups_*` or `enhanced_setups_*`.

**PITFALL — numpy types break json.dump.** `scan_asset_class()` returns numpy
types (incl `numpy.bool_`); `json.dump` then raises `TypeError: Object of type
bool is not JSON serializable`. The main scanner applies
`ups.convert_to_serializable(scan_data)` before any dump — the crypto-leg script
MUST do the same, or it dies after the scan completes and before writing
anything. (Hit live 2026-08-06; fixed by wrapping the returned dict in
`convert_to_serializable`.)

**WHAT CRYPTO LOOKED LIKE UNDER THE 2026-08-06 EXTREME-DANGER READ (calibration
note, not a market rule):** 28 coins scanned → 3 longs (XRP, ADA, XLM, all deep
VWAP pullbacks) + 1 short (UNI, extended). The gate returned **0 GO in BOTH
profiles**, for two structural reasons, not a data gap:
- SWING floor is 2.0 net-of-broker-cost R:R. Crypto's capital.com spread is
  **0.25%** (vs 0.01% on FX), so gross 2.00 → net 1.76–1.99 — every name fails
  the 2.0 floor by a hair. Same R:R-calibration-cliff as
  `references/gate-rr-floor-calibration.md`, amplified by crypto's wider spread.
- DAY floor is 1.5 R:R-to-T1 with a tight 0.75×ATR stop. Crypto was extended vs
  VWAP, so T1 (mean-reversion target) sat far from entry while the stop sat
  close → R:R collapsed to 0.36–1.25.

So "crypto = stand aside tonight" was a legitimate gate result under an 82.5
gauge, NOT missing data. When you report a 0-GO crypto leg, lead with the spread
+ structure reason, not "no setups exist." Offer the same three moves as the
calibration-cliff finding: backtest the near-miss set, widen the crypto floor
explicitly + label it a parameter change, or hold.

**Case B — they are absent.** Only the universal chain exists
(`universal_premarket_scan.py`, `enhanced_trade_gate.py`,
`run_universal_workflow.py`, `blogwatcher_integration.py`,
`danger_zone_gauge.py`). "Nightshift" in practice means running the universal
chain over the full multi-asset universe.

In that case run the universal chain and **say so in the report** — note that
ETF/bond/futures setups are US-session instruments surfaced overnight, so they
are context and next-open candidates rather than immediately tradeable. Do not
silently present them as live overnight trades.

Do not assume Case A from this skill's text alone; `ls` first. Both this skill
and persistent memory previously claimed the dedicated scripts existed, and
acting on that claim without checking wasted a cycle.

### The kill list is STANDING — the scanner will re-emit rejected names

Across three runs in one four-hour session the gate re-produced `^GSPC` SHORT
and `DOT-USD` LONG as fresh GO verdicts *every time*, having been rejected on
every prior run. The scanner has a structural bias toward fading strength and
it does not remember. You must.

- Carry the rejection list forward across runs **within and between sessions**,
  in the report as a `STANDING KILL LIST` block with the disqualifying numbers.
- When a killed symbol reappears, **re-backtest it rather than refusing from
  memory**, then report that it was rejected *again*, with the figures side by
  side against the prior run. Identical numbers are the point — they prove the
  rejection is structural, not a one-off.
- The user explicitly asks for this carry-forward. Dropping it silently reads
  as having forgotten your own warning.

### Falling GO counts and an empty short book are FINDINGS

Same session: 14 GO → 8 GO → 5 GO across three runs while RSI rose on every
index (^DJI 66.7 → 70.1). The third run produced **zero** qualified shorts in
a market the gauge scored 82.5 EXTREME DANGER. Lead with that. "The machinery
could not validate a single short while calling the regime extreme" is more
informative than any individual ticket. A thinning gate into a stretching tape
is late-cycle signature, not an empty result.

### When the backtest kills everything, "no position" is the deliverable

Do not manufacture a trade to satisfy the shape of the request. State the
refusal, the reason, and the **trigger conditions that would create a setup**
(specific level + indicator state), so the user can act without re-asking.

Corollary — **when a level you already gave gets taken out, say so first,
plainly, unprompted.** Over one session gold ran 4213 → 4259 → 4294; two
successive short entries were stopped. The user asked for gold levels four
more times. The correct answer each time was to refuse and note the prior stop,
not to produce a fifth number chasing price. Re-quoting a fading trade at ever
higher entries is precisely the error the kill list exists to prevent. The user
tracks the diff between answers and values the retraction over the new number.

## THE CRITICAL PITFALL: stale output from a test-harness `__main__`

This one silently produced an entire wrong report and had to be retracted in
front of the user. It is the single most important thing in this skill.

Several phase scripts in this pipeline are **libraries, not entry points**.
Their `if __name__ == "__main__":` block is a *test harness with hardcoded
sample data*. Running them directly:

- prints plausible-looking output (one hardcoded symbol, verdict GO),
- writes nothing,
- leaves the previous run's `*_latest.json` files untouched,
- so downstream reads serve results that can be many hours old.

`enhanced_trade_gate.py` was the known instance: no `main()`, `__main__` was a
single hardcoded GC trade. The real entry point was the orchestrator
`run_universal_workflow.py` (supports `--scan-only`, `--gate-only`,
`--report-only`, `--execute-only`, `--monitor-only`, `--dry-run`).

### STATUS UPDATE — `enhanced_trade_gate.py` has been fixed

It now has a real `run_gate()` entry point plus a CLI, so invoking it directly
is safe and is the fastest path for a gate-only re-run:

```bash
python3 enhanced_trade_gate.py                    # both profiles, writes _latest
python3 enhanced_trade_gate.py --dry-run          # validate, write nothing
python3 enhanced_trade_gate.py --profile swing
python3 enhanced_trade_gate.py --scan-file <f> --allow-stale   # deliberate backtest
```

Guards it now enforces (verified against live data):
- **90-minute staleness refusal.** Reads the scan's own `scan_timestamp`,
  prints the age, and exits 1 rather than validating an old scan.
  `--allow-stale` overrides, which makes the intent visible in the transcript.
- **Missing scan file** → clear error + exit 1 (was a bare traceback).
- **Exit 0 only on a real validated run**, so it cannot pass silently in a chain.
- **Provenance stamped into every output file** — `scan_timestamp` and
  `scan_source` are embedded in `enhanced_setups_*_latest.json`. Read those
  fields instead of diffing mtimes:

```python
d = json.load(open('enhanced_setups_swing_latest.json'))
print(d['scan_timestamp'], d['scan_source'])
```

`run_universal_workflow.py --gate-only` still works and is unchanged. Prefer the
orchestrator for full pipeline runs; use the direct CLI for gate-only iteration.

The general lesson still stands for **every other phase script**: before
invoking one directly, read its `__main__`. If it builds literal sample data,
it is a demo — find the orchestrator. The reusable guard pattern (timestamp
parse, age check, refusal, provenance stamping) is in
`references/stale-artifact-pipeline-bug.md`; apply it when you fix the next one.

### Mandatory guard — verify freshness before reading any result file

After every phase, compare the output file mtime against the input's:

```bash
ls -la --time-style=full-iso \
  universal_scan_results_latest.json \
  enhanced_setups_swing_latest.json \
  enhanced_setups_day_latest.json
```

If a downstream `*_latest.json` is older than the upstream scan file, the phase
did not run. Re-run via the orchestrator, never by invoking the module.

A second, cheaper tell: **row counts must match.** If the raw scan reports
15 longs / 27 shorts and the gate reports 17/17, the gate read a different
file. Cross-check the symbol lists, not just the counts.

### Before invoking any phase script directly

`grep -n "def main\|__main__" <script>.py` and read the block. If it is sample
data, use the orchestrator instead.

Note also: symlink creation fails on Windows without privilege
(`WinError 1314`); the workflow falls back to copying to `*_latest.json`. That
fallback is fine and expected — but it only happens when the phase actually runs.

## ZERO RESULTS MUST EXPLAIN THEMSELVES

A bare "no candidates qualified" is indistinguishable from a broken
integration, and will hide a defect indefinitely. Every gated/filtered feature
must emit near-misses with the specific blocking reason:

```
No symbol qualified under the protocol this run.
Nearest misses:
- BTC SHORT: volume 0 below 30,000,000 floor
- ETH SHORT: volume 0 below 30,000,000 floor
```

That block, added 2026-08-06, immediately exposed a real upstream data bug on
its first live nightshift run: `nightshift_scan.py` reports crypto volume
**0.0** for BTC/ETH while the daytime universal scan reports 18.4B/7.9B for the
same assets. A silent zero would have looked like a quiet market forever.

Build this into any new filter from the start, not as an afterthought.

**Standing consequence for the news protocol:** because nightshift reports
crypto volume 0.0, the 30M-share news-protocol floor can never be cleared on
the overnight session. Treat a 0-candidate nightshift protocol block as an
upstream data bug in the nightshift crypto leg, NOT as an absence of setups —
and never "fix" it by lowering the floor.

## AUDITING A CROSS-PIPELINE INTEGRATION

When the user asks to "check for gaps" — or before declaring any multi-pipeline
integration done — AST-clean + import-clean + wired is **not** evidence it
works. Four silent-failure gaps were found in code already reported as
complete; two would have made it do nothing forever.

Minimum checks (full sequence in `references/integration-gap-audit.md`):

1. `grep -ln "<upstream_module>" *.py` — enumerate ALL consumers, not just the
   ones you wired. Two extra were missed on the first pass.
2. **Diff key shapes across the boundary.** Scans emit `BTC-USD`; blogwatcher
   keys news as `BTC`. A raw `dict.get()` never matched → zero candidates
   forever. Print both key sets side by side.
3. Check nested value TYPES (`headlines` entries are dicts, not strings).
4. Run identical input 2–3× and diff the output store — recurring crons plus
   manual reruns need signature dedupe or every downstream statistic is wrong.
5. Assert the system cannot emit contradictory pairs (LONG and SHORT on the
   same symbol from neutral news).
6. Test degenerate inputs (`{}` news, `{}` scan) — clean message, not a
   traceback.

Structural rules that prevented worse: one shared module imported by all
consumers (never copy-paste per pipeline); every integration call site wrapped
in try/except so an add-on can't kill the host scan; adapter functions for
shape drift; and **never fabricate a missing input** — leave ATR 0 so the gate
blocks with "no ATR(14)" rather than inventing a breakeven, and flag proxy
values (`trigger_low_is_proxy` → `*` + footnote) so nobody trades a guess.

## Workflow

1. **Locate the pipeline.** Scripts live in the user's home dir, not a repo.
   `ls *.py | grep -iE "scan|gate|workflow|premarket|sonar|nightshift"`. Avoid
   recursive `grep -r` / `find` from the home root — it times out on this machine.
2. **Phase 1 — scan.** For universal scans: `run_universal_workflow.py
   --scan-only`, or the scanner directly if it has a real `main()`. For nightshift:
   `python3 nightshift_report.py` (runs scan+gate+sentiment+gauge+report).
   Long-running; use `background=true` with `notify_on_complete=true`.
3. **Phase 2 — gate.** Universal: `run_universal_workflow.py --gate-only`
   (**never** run `enhanced_trade_gate.py` directly). Nightshift: the gate runs
   inside `nightshift_report.py` and writes **namespaced** `nightshift_setups_*`.
4. **Phase 3 — sentiment.** `blogwatcher_integration.py` (standing rule above).
5. **Phase 4 — regime.** `danger_zone_gauge.py` is an infinite 60s loop — wrap
   in `timeout N` and run backgrounded, or it never returns.
6. **Verify freshness** (guard above) before reading anything.
7. **Extract GO verdicts only** for the headline table; keep NO-GO reasons for
   the rejection summary.
8. **Write the report** to a dated markdown file in the user's home dir.

## Reporting shape that works for this user

- **Lead with regime**, not with setups. Danger Zone gauge value + interpretation
  + blogwatcher `regime_shift_risk` come first; they govern position sizing for
  everything below.
- Separate **GO verdicts** (passed all hard gates) from **raw pre-gate signals**.
  Never present a raw signal as a qualified setup.
- Tables with entry / stop / T1 / R:R / size / risk% / RSI. Concrete numbers.
- A **gate rejection summary** explaining why N setups were blocked, grouped by
  which hard check failed (liquidity, R:R, stop width, extension).
- Call out the **cross-signal agreement** cases — where the technical gate and
  the news sentiment engine independently agree. Those are the high-conviction
  names and the user cares about them most.
- An explicit execution posture block (bias, sizing, longs, shorts, do-nots).
- Note coverage gaps honestly (e.g. CoinGecko 429 rate-limiting truncating the
  crypto leg) rather than presenting partial data as complete.
- **STANDING PRESENTATION ORDER (2026-08-06, user said "remember"):** for an
  all-asset scan, lead the ranked list with **$2–20 USD stocks first**, then
  **all other candidates by highest conviction** (conviction = 10y daily
  backtest profit factor on the scan's own RSI/VWAP rule). And **backtest every
  candidate in one combined pass** — build a single `go_setups_tmp.json` covering
  the gate GOs + every gap-screen stock, then run `backtest_go_setups.py` once.
  Recipe + $2–20 extraction snippet in
  `references/equity-momentum-gap-screener.md`.

## MANDATORY: verify per-class coverage before reporting

The user specifies an asset universe ("FOREX, COMMODITIES, INDICES and crypto")
and expects the report to cover it. A scan can load all four classes and still
**silently eliminate every one of them** downstream, producing an ETF-only
report that looks fine. This happened three reports in a row and the user was
rightly angry.

Run this after the scan AND again after the gate — every time:

```python
from collections import Counter
d = json.load(open('universal_scan_results_latest.json'))
c = Counter()
for t in d['qualified_longs']:  c[(t.get('category'), 'LONG')]  += 1
for t in d['qualified_shorts']: c[(t.get('category'), 'SHORT')] += 1
print(sorted(c.items()))
```

**Zero qualified in a whole requested class is a bug signal, not a market
observation.** Do not report until you have explained it. If the user named
classes and your GO set is all `etfs`, you are about to hand over a wrong
report.

Three root causes found and fixed 2026-08-05 — full diagnosis, code, and the
reason the risk floors were deliberately left alone in
`references/asset-class-coverage-defects.md`:

1. **Volume-less feeds cannot score.** yfinance FX `=X` pairs report
   `volume: 0`, so a volume-weighted VWAP collapses to spot and
   `vwap_distance_pct` is `0.00` for every pair — the scorer needs deviation,
   so forex could never qualify. `calculate_vwap()` now falls back to TWAP.
   Suspect this for any class where every symbol shows `dist 0.00%`.
2. **CoinGecko free tier cannot serve ~50 sequential OHLC calls.** It 429s
   after about four, truncating crypto to `[BTC, ETH, USDT, BNB]`.
   **Exponential backoff does not fix it — that was tried and failed.** Crypto
   now routes through yfinance `-USD` pairs via `CRYPTO_YF_SYMBOLS`
   (28 assets). `scan_asset_class()` needs both `symbols` and `names` keys.
3. **Liquidity-only failures used to vanish.** Futures/commodities/cash indices
   report contract counts or `$vol 0` against an equity dollar-volume floor.
   The gate now emits a **WATCH** verdict when H6 liquidity is the *only*
   failure. Risk floors were NOT loosened — that is the user's decision, not
   the agent's.

## STOCK SCAN HARD-GATE (standing user filter, 2026-08-06)

The user added a permanent equity-screening rule to `universal_premarket_scan.py`.
Equities (small_cap + micro_cap) must clear a **liquidity-event gate** before they
can become trade candidates:

- **Relative volume ≥ 4.0× the 50-DAY average** — `vol_ratio_50 >= VOL_RATIO_FLOOR`
  (`VOL_RATIO_FLOOR = 4.0`). CRITICAL: the user said **50-day**, NOT the scanner's
  default 20-day baseline. Compute it from `np.mean(volumes[-50:])` as `vol_ratio_50`;
  the 20d `vol_ratio` is still kept but must not be used for the stock gate.
- **LONGS additionally must GAP UP ≥ 1.0%** — `open[-1] > close[-2]`, i.e.
  `gap_up_pct >= GAP_UP_MIN_PCT` (`GAP_UP_MIN_PCT = 1.0`). SHORTS require only the
  volume gate (no gap-direction constraint).
- **No price or market-cap floor** — the user said "any price, any market." Do NOT
  add a minimum share price or mkt-cap filter to this gate.

Wiring (all in `universal_premarket_scan.py`, verified 2026-08-06):
- Constants right after `CRYPTO_YF_SYMBOLS`:
  `STOCK_CATEGORIES = {"small_cap","micro_cap"}`, `VOL_RATIO_FLOOR = 4.0`,
  `GAP_UP_MIN_PCT = 1.0`.
- In `scan_asset_class()`: compute `avg_volume_50`/`vol_ratio_50` and `gap_up_pct`
  (today's open vs prior close); set `is_stock = asset_data["category"] in
  STOCK_CATEGORIES`; qualify a LONG only if `vol_ok_stock and gap_ok_long`, a SHORT
  only if `vol_ok_stock`. Store `vol_ratio_50`, `gap_up_pct`, `avg_volume_50` in
  `asset_result` so reports can show the liquidity event.
- Other classes (forex/commodities/indices/crypto/ETFs) are **UNCHANGED** — the gate
  applies only to `STOCK_CATEGORIES`.

**A zero-stock qualified result is the INTENDED behavior, not a bug.** 2026-08-06
calibration: 63 small/micro-cap stocks scanned → 0 hit ≥4× 50d volume (highest was
ASNS at 3.85×, and it GAPPED DOWN -25% on a reverse-split/dilution, not a buy). 18
gapped up but none with the volume, so the gate correctly produced no equity
candidates. Report this as a finding ("no high-volume gap-up stock event in the
universe today") — do NOT loosen the floor or manufacture stock entries to balance
the list. The user wants the discipline explicitly. The blogwatcher + danger-zone
standing rules still compose on top: when a real gap-up high-vol stock appears, layer
blogwatcher sentiment on it, and flag when a candidate lacks a news read (small/micro
coverage is sparse) rather than implying coverage.

Exact code edit locations + reproduction in `references/stock-hardgate-filter.md`.

**STALE-NAME GUARD (same session, 2026-08-06 — part of the stock discipline).**
yfinance returns synthetic/flat series for delisted/halted/sub-penny names
(e.g. price `0.0001`, RSI 100, zero volume). These pollute the scan and can reach
qualification. Guard added in `scan_asset_class()`: for `STOCK_CATEGORIES` only,
skip the symbol if `price <= 0.10` (sub-penny/defunct) OR `last_bar volume <= 0`
(no real trading). Verification 2026-08-06: equities scanned dropped 63 → 55 after
the guard killed 8 dead rows (SIRC, CCTL, ALPP, VIVE, GLBS, AVD, VSTS, others at
$0.0001). The guard sits BEFORE indicator calc so dead rows never score. Place it
right after `last_vol = volumes[-1]` and `price = closes[-1]`, inside the
`if asset_data["category"] in STOCK_CATEGORIES:` block. This is scanner hygiene, not
a toggle — always keep it.

## CONVICTION-FIRST DEPLOY (standing trade rule, 2026-08-06)

The user stated plainly: **"when conviction, deploy to trade those first, always."**
This is a deployment-priority rule, not a gate change. It governs the ORDER setups
are presented and acted on, and it is now baked into the report wrapper
(`cron_allsector_open_scan.py` / `scripts/standing_open_scan_cron.py`).

**Conviction defined:** blogwatcher news `alignment` agrees with the trade side —
- LONG + `BULLISH`, or SHORT + `BEARISH` → **CONVICTION**
- LONG + `BEARISH` or SHORT + `BULLISH` → **CONFLICT** (news opposes the trade; extra headline risk)
- no per-symbol news → **NONE** (regime risk is the only overlay; small/micro-cap
  coverage is sparse, so NONE is common and not a negative)

**Behavior:**
- Ranked DEPLOY ORDER block leads every report: conviction setups first (sub-sorted
  by news `impact` weight HIGH>MEDIUM>LOW), then CONFLICT, then NONE.
- The conviction setup deploys FIRST, ahead of everything else — even under an
  extreme-danger gauge. Sizing still stays within the gate's limits (the gauge
  already caps size; conviction does not raise it).
- Example from 2026-08-06 (gauge 82.5 EXTREME, regime HIGH): PL (Platinum SHORT +
  BEARISH/HIGH) ranked #1 and was the only CONVICTION; SI (Silver SHORT + BULLISH/HIGH)
  was flagged CONFLICT and de-prioritized.

**Why it matters for this user:** they explicitly want the news-aligned trade to be
the one that goes first, because it is the highest-conviction expression of the
regime read. This overrides "present everything by class" — the deploy order IS the
priority. When you hand over a GO list, lead with the conviction name and state
plainly that the rest are non-conviction / conflict.

Implementation snippet (conviction_of in the wrapper):
```python
def conviction_of(t):
    v = hits.get(t["symbol"].upper())
    if not v: return ("NONE", 0)
    al = (v.get("alignment") or "").upper()
    imp = (v.get("impact") or "").upper()
    aligned = (t["side"]=="LONG" and al=="BULLISH") or (t["side"]=="SHORT" and al=="BEARISH")
    if not aligned: return ("CONFLICT" if al in ("BULLISH","BEARISH") else "NONE", 0)
    return ("CONVICTION", {"HIGH":2,"MEDIUM":1,"LOW":0}.get(imp,0))
# rank: conviction first, then by impact weight desc
ranked = sorted(gos, key=lambda t:(conviction_of(t)[0]!="CONVICTION",
                                     -conviction_of(t)[1], t["category"], t["side"]))
```
Also saved to durable memory as a standing trade rule.

## Extending the universe: adding a brand-new asset class

When the user says "add X to all scans" (e.g. "add US small caps to hunt/sonar/
scan"), they mean: make `X` a first-class `ASSET_UNIVERSE` group so it flows
through `scan_asset_class()` like every other class. Because the universal scan
("hunt/scan") and nightshift scan ("sonar") both import the SAME
`ASSET_UNIVERSE` + `scan_asset_class()` from `universal_premarket_scan.py`, one
edit to that dict populates BOTH scanners. The scanner's universe is curated
symbol lists (Finviz-style watchlists), not pulled live from a website — there
is no "website scanner" module in the repo. The exact 4-file edit template and
the default-fallback gotcha (a missing class silently inherits generic
`DEFAULT_PROFILE` / `$10M` liquidity floor and gets zero GOs) are in
`references/adding-an-asset-class.md`. Always smoke-test the new group in
isolation before declaring done (the snippet there fetches only the new symbols,
not the whole multi-hundred-symbol scan).

## INTRADAY PROOF HARD LIMIT — yfinance caps history at 60 days

The "mandatory 10y window" proof rule (below) applies to **daily** bars only. It
does NOT apply to intraday (5m/15m/1h) because **yfinance refuses intraday
history older than ~60 days**:

```
$GC=F: 5m data not available for startTime=... The requested range must be within the last 60 days.
```

Verified 2026-08-06: `period="5y"/"2y"/"1y"/"6mo"/"3mo"` all return 0 rows; only
`period="60d"` (and smaller) succeeds — 13,757 gold 5m bars for 2026-05-27 →
2026-08-06 09:10 ET. Date-range `start=/end=` queries for intraday also return 0
rows (yfinance intraday date-range handling is broken; use `period=`). So:

- **A literal 10-year 5m backtest is IMPOSSIBLE from this source.** Do NOT claim a
  10y intraday proof; the data does not exist here. State the 60-day cap openly.
- When the user asks to "prove" an intraday edge, run the 3-test bar on the max
  60d window, lead with the horizon disclosure, then walk-forward OOS / param
  grid / t-test on that window. It is a shorter, weaker proof — say so.
- A real 10y intraday proof needs a paid vendor (Polygon, Databento, capital.com
  history). Offer that path rather than fabricating a decade of 5m bars.

## Worked intraday proof: GOLD 5-min VWAP-bounce on capital.com = NOT PROVEN

The user asked which indicator set is best for a 5-min gold trade on capital.com,
then asked to prove it. Recommended set: session VWAP, EMA21/50, RSI14, ATR14,
relative-volume confirm, London/NY session filter. Proof harness:
`scripts/gold_5m_proof.py` (runs the 3-test bar, net of a measured capital.com
round-trip of $5/oz = 0.06% spread @ ~$4316).

**Result 2026-08-06 (calibration, NOT a market rule):**
- Realistic VWAP-bounce trigger → 25 trades / 60d, **PF 0.38**, 9W/16L (62%
  losers), mean −$4.98/oz. A first, over-tight trigger (price within 0.15% of
  VWAP + RSI turn + vol + session all at once) fired only 7 trades and lost even
  harder (PF 0.74) — widening the trigger made it trade more but lose MORE.
- T1 IS PF≥1.0 FAIL (0.38) · T2 walk-fwd OOS PF≥1.0 FAIL (0.49) · T3 param grid
  ≥50% FAIL (0/162 combos PF≥1.0) · T4 t-test p<0.05 **PASS (p=0.029)** — a PASS
  here means the NEGATIVE edge is statistically reliable, i.e. reliably
  unprofitable after costs.
- **VERDICT: NOT PROVEN. Do NOT trade this 5-min gold set on capital.com.**

**Why it fails (durable lesson — a broker-cost trap, not a bad indicator
choice):** capital.com's 0.06% gold spread (~$5/oz round trip) against a ~$10/oz
5m ATR means you pay ~half a bar of range in cost every round trip. A
mean-reversion entry (1.5×ATR stop / 2×ATR target) is too tight for gold's 5m
noise — stops get clipped before the reversion pays. The edge would have to be
huge to survive the spread, and a VWAP bounce isn't.

**When the user wants a 5-min gold edge, offer these three refinements (re-run
the harness on each) instead of shipping the losing set:**
1. **Widen R:R** — 2.5–3.0×ATR target / 1.5×ATR stop, only on the highest-volume
   London/NY overlap, so winners run past the spread.
2. **Trend-follow, not reversal** — long when price > VWAP > EMA21 > EMA50 with
   RSI>55, exit on VWAP cross; plays gold's actual 5-min directional bursts.
3. **Real 10y data** — get a paid intraday feed, then re-run the full proof bar
   on a decade so the 60-day window is no longer the limiting factor.

The harness is reusable for ANY intraday edge proof on this stack: edit
`backtest()` or `SESSIONS`, keep `COST_PER_OZ` honest, keep the 60d `period=`
cap. Do NOT "loosen" the floor to manufacture a GO — the proof's job is to kill
fragile intraday edges before they reach live capital.com margin. Condensed
knowledge + the full harness in `references/intraday-proof-gold-5m.md`.

## The proof bar is now THREE tests, not just PF >= 1.0

The user's standing rule escalated during 2026-08-05 from "backtest PF >= 1.0"
to **"prove profitable all we can."** A single 10y PF>=1.0 aggregate is NOT
enough — it can be a few large winners dragging a near-breakeven strategy
positive. A GO is only GREEN-LIGHTED if it passes THREE independent stress tests
(see `references/robustness-proof.md` and `scripts/robustness_proof.py`):

1. **10-YEAR WINDOW (mandatory).** Backtest window is now `10y` daily (was 3y).
   Regimes cycle longer than 3y. Proved: ZS/ZC passed at 3y (PF 1.07/1.15) but
   FELL to 0.78/0.84 at 10y and were correctly killed. The 3y number
   overstated edge.
2. **WALK-FORWARD out-of-sample.** PF >= 1.0 on UNSEEN test data (train 60% /
   test 40% of the 10y series). An in-sample PF that collapses OOS (e.g. ^FCHI:
   1.29 in-sample -> 0.98 OOS) is an artifact, not an edge.
3. **PARAMETER GRID + SIGNIFICANCE.** Edge must survive >=50% of a 60-combo
   RSI/ATR-mult/R:R sweep AND the per-trade R must be statistically
   distinguishable from zero (one-sample t-test, p < 0.05).

**The 2026-08-05 finding that defines this bar:** all 5 candidates that passed
10y-PF>=1.0 (GBPJPY, USDJPY, BNB-USD, CHFJPY, ^FCHI) were run through the full
proof. Result: **ZERO passed.** Every FX/crypto long had PF>1.0 in- and
out-of-sample and survived the grid 60/60, but their per-trade average R was
statistically indistinguishable from zero (t ~0.8-1.6, p 0.10-0.43) — the 10y PF
was a handful of large winners, not a real edge. ^FCHI additionally failed OOS.
**Under this rule, "no position" is the correct, disciplined deliverable** — the
proof did its job by stopping fragile setups from reaching live capital.

Consequences for the report and the agent's behavior:
- The 10y-PF>=1.0 filter is a NECESSARY but NOT SUFFICIENT screen. Do not hand
  over a GO list that has only cleared step 1. Run all three before declaring
  anything tradeable.
- When the proof kills everything, RESCIND the earlier GO list in the same
  breath, state the reason (which test failed, with the numbers), and give the
  user the trigger conditions / refinement options that could produce a real
  edge (trail-to-breakeven + winner-run, tighter RSI/VWAP confluence, regime
  filter so longs only fire when gauge < 60, broader universe scan). Do NOT
  manufacture a trade to satisfy the shape of the request.
- This is the standing "prove profitable all we can" mandate made operational.
  It overrides the older "PF>=1.0 then trade" framing wherever they conflict.

## Build entries on MECHANICS, not symptoms

The symptom rule (`RSI<40 & close<VWAP`, or `RSI>60 & close>VWAP`) describes a
*state*, not a *cause* — and it is the reason the 5 PF>=1.0 candidates failed the
proof (no "why", so no real edge). When the user asks to "understand market
mechanics" / "better entries on price" / "why price moves", build entries on the
event that FORCES price, not on a static threshold.

**SYMPTOM vs CAUSE — the hard rule.** A static RSI/VWAP condition is a FILTER,
not an ENTRY. It describes a state; it does not explain why price would move. The
aggregate PF it produces can be a few large winners dragging a near-breakeven
strategy positive (t-test p 0.10–0.99 → noise). The original 5 candidates that
passed 10y-PF>=1.0 ALL failed the 3-test proof for exactly this reason. Therefore:
**every new entry must (1) NAME its driver, (2) REQUIRE the EVENT that forces
price, not a bare RSI level, (3) PASS the 3-test proof before any ticket.** This
is non-negotiable — do NOT fall back to the symptom rule as "an entry".

Canonical driver model (the five drivers D1–D5, what our data can/can't see, the
HTF-anchoring fix that produced the first proven edge, and the Windows/yfinance-1h
gotchas) is in `references/mechanics-driver-model.md` — read it whenever the user
asks for mechanics-based entries. Short form:

- **D1 Liquidity grab / stop-run** — sweep a prior swing low/high (or a DAILY
  liquidity level), then reject back inside + directional candle; enter next bar.
  (`mechanics_entries.py` `_trig_liqgrab`; proven variant `mechanics_1h.py`
  `prove_htf_grab`)
- **D3 VWAP reclaim w/ VOLUME** — close back through VWAP after being below, on
  rising volume + directional candle. Volume = confirmation the move is funded.
  (`_trig_reclaim`)
- **D4 Exhaustion fade** — volume spike (>2.5x avg) at extended RSI + reversal
  candle = last chasers in, fade it. (`_trig_exhaust`)
- D2 (market structure BOS+pullback) and D5 (session/regime timing) are
  documented in the reference; D2 is not yet coded (flagged for a future leg).

Each trigger is proven through the SAME 3-test harness — `mechanics_entries.py`
imports from `robustness_proof.py` and `prove_trigger()` returns GREEN_PROVEN /
NOT_PROVEN with the failing test named. Run it backgrounded; it is heavy (3
triggers x 108-combo grid x 10y). A GO on the symptom rule that then fails the
mechanic proof is not a contradiction; it means the rule caught noise.

**Direct structural read (explaining WHY price is where it is):** when the user
asks "check metals and forex" or "why is price here", run `inspect_metals_fx.py`
— it pulls daily + 1h for the named class and prints the mechanic state
(distance to VWAP, RSI, whether a liquidity sweep already fired on the 1h). That
is the "understand market mechanics" deliverable: a plain-English read of what
is forcing price, not just a level. Pair it with the 1h proof loop
(`references/oneh-mechanics-practice-loop.md`) to go from "why" to "is it
tradeable".

**Proven edge exists:** the HTF-anchored 1h grab (sweep must hit a DAILY
liquidity level) cleared all four proof gates on GBPJPY long (IS 2.0 / OOS 3.0 /
grid 9/9 / t-test p=0.0037, n=70) — the first GREEN_PROVEN entry in the project.
Other JPY longs show the bias but did not clear the full bar. See the reference
for the loop and the exact code in `mechanics_1h.py :: prove_htf_grab`.

## A GO verdict is NOT evidence of edge — backtest before handing over tickets

The enhanced gate checks *risk mechanics* (R:R, stop width, size, concentration,
earnings, liquidity, extension). It does **not** check whether the entry rule has
ever made money on that symbol. Treating GO as a trade recommendation ships
negative-expectancy trades wearing tidy-looking stops.

When the user asks for entries/stops/targets — and especially when they say
"backtest" — replay the scan's own rule on history for every GO symbol before
writing the plan. `scripts/backtest_go_setups.py` in this skill does exactly
that: RSI(14)<40 & close<VWAP(20) long / RSI>60 & >VWAP short, 2×ATR stop, 2R
target, 20-bar timeout, stop checked before target (conservative), 3y daily bars,
TWAP fallback for volume-less feeds. It reads `go_setups_tmp.json` (the projected
GO rows) and writes `backtest_go_results.json` with win rate, avg R, total R,
profit factor and max drawdown in R.

**The 2026-08-05 finding, which will likely recur:** the gate's largest and most
confident block — the RSI-overbought short book on US index/sector ETFs
(SPY, QQQ, ^GSPC, ^IBEX, XLK, XLI, XLF, XLB, XLY) — backtested at 16–29% win
rate, −0.2 to −0.54 R average, profit factors 0.32–0.68 over 3 years. Shorting
strength on this ruleset is a bull-market artifact, not an edge. The quiet
defensive names passed cleanly: XLU long PF 2.47, HYG short PF 1.55, XLE short
PF 1.35.

Consequences for the report:
- Split the GO list into **positive expectancy (tradeable)** and **negative
  expectancy (DO NOT TRADE despite GO)** tables, with PF and avg R in both.
- A high Danger Zone gauge does not rescue a 0.32 profit factor. Never justify a
  losing rule with a bearish macro reading — say plainly that the correct bearish
  expression is the short that actually backtests positive (credit/HYG, energy),
  not the index short book.
- Size the surviving set by profit factor, not by gate conviction score.
- Full worked run: `references/backtest-validated-scan-run.md`.

### WATCH is not tradeable

WATCH = every risk check passed, liquidity floor is the sole blocker. Report it
in its own section, clearly marked "trade a liquid proxy or size manually",
never mixed into the GO table.

## Verify the instrument is the one the user asked for

`CL=F` is front-month NYMEX **futures**, not spot; `GC=F` is COMEX futures, not
spot. There is no free spot feed for gold or WTI in this stack — `XAUUSD=X`,
`WTICOUSD=X`, `USOIL` and `CL1!` all 404. Worse, `WTI` silently resolves to an
unrelated **$3.42 NYQ equity**; a wrong-instrument quote that *looks* valid is
more dangerous than an error. Sanity-check `fast_info['exchange']` and price
magnitude on any unfamiliar symbol.

When the user asks for spot: say the scanner has no spot feed, cross-check an
independent source (oilpriceapi, EIA Cushing FOB, FRED `DCOILWTICO`), and quote
the **basis** so levels transfer (2026-08-05: spot $76.50 vs CL=F 76.36 =
+$0.14, transfers ~1:1).

Prefer the **ETF over the raw future** unless the user specifies a vehicle:
same rule and window, USO LONG 1.52 PF vs CL=F 1.00; GLD SHORT 1.42 vs GC=F
1.02. Wider futures ATR chops through the same stop. Show the paired PFs.

## Deliverable shape: sequenced plain-text execution files

When the user asks for something executable ("tell me exactly buy this first,
then sell this next"), a markdown report is not the deliverable. Write a
**plain-text `.txt`** with numbered `STEP 1 of N` in one mandatory sequence,
phase-separated (PHASE 1 BUY / PHASE 2 SELL), hard gate lines between steps
(`>>> DO NOT PROCEED UNTIL X IS FILLED AND THE STOP IS LIVE. <<<`), steps
ordered by **backtest quality descending**, per-step kill triggers, a blank
account-size field, totals for deployed capital and worst-case risk, a DO NOT
TRADE section carrying the disqualifying numbers, and a FILL LOG with blanks.
Intraday variants get a TIME STOP per position and an explicit "flat by HH:MM
ET, no overnight". Full template in the reference below.

## Re-pull prices before restating an actionable entry

Quotes go stale mid-conversation. GC=F moved 4213.10 → 4221.80 between two
answers, taking a proposed short entry from $12 away to $3 away. Re-fetch the
last bars before repeating any level the user is about to act on, and say it
moved.

## Answer direct factual questions first, in plain prose

The user may ask something factual alongside the scan ("is the war resolved yet
with hormuz?"). Answer it **first**, with a plain verdict and a dated bullet
timeline — do not bury it under tables. Then fold it into the positions as
named **kill triggers**, not atmosphere.

## Pitfalls

The full catalog (~12KB, 25+ entries) lives in
`references/pitfalls-catalog.md`. **Read it before debugging any scan
failure** — it is the difference between a 2-minute fix and a re-derivation.

The five that bite most often, kept inline:

- **Stale `latest.json` after editing a phase script.** A cached `.pyc` makes
  the subprocess run OLD bytecode and write output with a fresh mtime but
  missing your new fields. Fix: `rm -rf __pycache__` in the SCRIPT dir (a
  recursive home-root wipe times out on this machine), re-run, then confirm
  the new key is PRESENT in the JSON — not merely that the log line printed.
  `scripts/verify_scan_memory.py` catches this automatically.
- **Wrong interpreter.** Phase scripts need SYSTEM `python3` 3.13, not the
  Hermes venv. `ModuleNotFoundError` = check the interpreter first.
- **Never state a rejection reason you have not actually read** from the
  gate output. Read `binding_reason`; do not infer it.
- **A GO is a risk-mechanics pass, NOT edge.** Never hand over tickets before
  backtest validation. For a pure SCAN request do NOT run the MT5 execute
  phase (`run_universal_workflow.py` Phase 4 places live orders) — ask first.
- **Recursive searches from the home root time out.** Always scope to a
  subdirectory.

## Accelerating the narrative layer with the NVIDIA text-LLM

The user supplied a NVIDIA hosted inference key (NVAKEY). The endpoint is OpenAI-compatible chat-completions (`https://integrate.api.nvidia.com/v1/chat/completions`) and is a **TEXT/LLM endpoint ONLY** — it cannot speed up the numeric scan/gate/gauge math, but it *can* offload the INTERPRETATION layer: turning gate JSON + danger-zone gauge + blogwatcher into a plain-English regime read + per-setup rationale, batched into ONE call that runs in parallel with the report assembly. Working models on this account (verified 2026-08-05): `meta/llama-3.1-8b-instruct` (~1-2s, FAST default) and `nvidia/llama-3.3-nemotron-super-49b-v1` (~30s, quality). Key rotates per session — set via env `NVAKEY`, never persist the value. Reusable client + content-hash cache: `scripts/nvidia_llm.py` (`synthesize_nightshift(...)`). Full endpoint details, model probe, and the gauge-direction pitfall in `references/nvidia-llm-narrative-acceleration.md`.

**PITFALL — the LLM inverts the gauge sign.** Left unprompted, the model reads gauge 82.5 as "high risk appetite" — backwards. In this stack higher gauge = MORE danger = LOWER risk appetite (82-100 = EXTREME DANGER -> hedge/suppress). The `synthesize_nightshift` prompt carries an explicit CRITICAL DIRECTION RULE for this; any future LLM delegated to read the gauge must too.

## Support files

The annotated index of every bundled script and reference — plus the home-dir
scripts the pipeline depends on — is in `references/support-files-index.md`.
Consult it when you need to know which artifact does what.

Most-used, at a glance:
- `scripts/verify_scan_memory.py` — proves the last-scan memory layer attached
  (`attached == 0` => FAIL). Run after any scan that should remember prior runs.
- `scripts/backtest_go_setups.py` — replays the scan's own entry rule before
  any report containing entries and stops.
- `scripts/robustness_proof.py` — the three-test proof harness.
- `scripts/reorder_gate_by_class.py` — nightshift presentation order.
- `gap_rvol_screener.py` (home dir) — the equity momentum / $2-20 band layer.

