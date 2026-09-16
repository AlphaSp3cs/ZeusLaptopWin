# Support Files Index — market scan pipeline runs

Extracted from SKILL.md 2026-08-07. Full annotated index of every bundled
script and reference, plus the home-dir scripts the pipeline depends on.

## Support files

- `references/nightshift-pipeline-map.md` — phase-by-phase script map, entry
  points, output files, and the gate's 7 hard checks.
- `references/blogwatcher-symbol-matching.md` — the substring→word-boundary fix
  for `analyze_sentiment_for_symbols()`: the false-positive classes observed
  live, the alias-before-length-guard ordering trap, the 18-case test, and why
  it took three live-data passes. Read before touching symbol matching.
- `references/integration-gap-audit.md` — the reusable audit sequence for any
  cross-pipeline integration: consumer enumeration, key-shape diffing, value-type
  checks, idempotency, contradictory-pair detection, degenerate inputs, and the
  explain-your-zeros rule. Read when asked to "check for gaps" or before
  declaring a multi-pipeline feature done.
- `references/stale-artifact-pipeline-bug.md` — full diagnosis of the stale
  `_latest.json` failure, the reproduction command, and the reusable
  staleness-guard + provenance-stamping code pattern to apply to the next
  phase script you fix.
- `references/asset-class-coverage-defects.md` — the three defects that made
  forex/commodities/crypto structurally unreportable (volume-less VWAP,
  CoinGecko rate limiting, liquidity-only rejections), with the fixes, the
  coverage-check snippet, and why the risk floors were left alone.
- `references/backtest-validated-scan-run.md` — full worked all-sector run
  (2026-08-05): phase order, the two environment gotchas, coverage counts,
  regime readings, the 17-symbol backtest table, and the ticket format the user
  wants.
- `scripts/reorder_gate_by_class.py` — re-sorts nightshift gate GO verdicts by
  asset class (commodities → forex → indices → crypto) instead of by profile;
  the user's standing presentation order for nightshift reads. Reads the
  namespaced `nightshift_setups_*_latest.json` from the home dir.
- `nightshift_crypto_leg.py` (home dir `C:\Users\victo`) — re-runs ONLY the
  crypto universe (yfinance `-USD` via `scan_asset_class("CRYPTO")`) through the
  same `enhanced_trade_gate.process_all_setups`, writing namespaced
  `nightshift_crypto_*` files. Use it when the user wants a real crypto leg
  appended LAST to a nightshift read (see "STANDALONE NIGHTSHIFT CRYPTO LEG").
  Copy into this skill's `scripts/` to version it; it is the working runner saved
  from the 2026-08-06 session where the technique was developed.
- `scripts/verify_scan_memory.py` — probes `universal_scan_results_latest.json` + `universal_scan_last_snapshot.json` and proves the last-scan memory layer actually attached `last_scan` + `*_chg_since_last` to populated assets (attached==0 => FAIL). Run it after any scan that should remember the prior run; it catches the stale-`__pycache__` trap automatically.
- `scripts/backtest_go_setups.py` — replays the scan's own entry rule on 3y
  daily bars for every GO symbol and emits win rate / avg R / profit factor /
  max DD. Run this before writing any report that contains entries and stops.
- `gap_rvol_screener.py` (home dir `C:\Users\victo`) — **the new-config equity
  momentum layer**. Cross-asset gap-up + relative-volume screen, any price / any
  market, reusing `universal_premarket_scan.ASSET_UNIVERSE` + `CRYPTO_YF_SYMBOLS`
  + `blogwatcher_integration.fetch_live_catalysts`. Defaults: gap≥1.0%,
  rvol≥1.5×, vol_vs_prevday≥1.0×, news=any. Writes
  `gap_screener_results_latest.json` + `gap_screener_report.md`. Emits
  `category` as `small_cap`/`micro_cap` (normalized from the scan's
  `US_SMALL_CAP`/`US_MICRO_CAP`). This is where the **$2–20 USD stock band**
  candidates come from — see `references/equity-momentum-gap-screener.md`.
- `scripts/intraday_focus_scan.py` — for "concentrate on these 2 assets, give
  me intraday positions" requests. Live 15m snapshot (session VWAP, RSI, ATR,
  opening range, prior-day levels) plus a 60-day 15m VWAP-reversion backtest of
  **both** directions per symbol, so the tradeable side is chosen by data.
  Edit `UNIVERSE` and run.
- `references/repeated-scans-and-kill-list-discipline.md` — the multi-run
  session pattern: falling GO counts as a finding, names the scanner re-emits
  after rejection, the standing kill list, and the worked gold-refusal sequence
  (two stopped entries, a declared invalidation level, and why refusing a fifth
  number was correct).
- `references/backtest-validation-and-instrument-selection.md` — the
  spot-vs-futures ticker resolution matrix (including the `WTI` wrong-instrument
  trap), ETF-beats-future profit factors, the intraday 15m harness, the
  sequenced plain-text execution-file template, and the blogwatcher
  commodity-coverage gap.
- `references/stock-hardgate-filter.md` — the standing equity hard-gate (≥4× 50d
  relative volume; longs must gap up; no price/mkt-cap floor): exact code edits,
  verification snippet, and the 2026-08-06 calibration read showing a zero-stock
  result is the intended behavior.
- `references/adding-an-asset-class.md` — the 4-file edit template + the
  default-fallback gotcha for adding a brand-new asset class (e.g. US small
  caps) so it propagates through the universal scan, nightshift, the gate, and
  the report. Read this BEFORE editing `ASSET_UNIVERSE`.
- `references/gate-rr-floor-calibration.md` — the R:R-floor calibration cliff:\n  why ~95% of qualified setups fail H8 on a boundary, the fail-reason\n  distribution observed 2026-08-05, and the `Counter`-over-`binding_reason`\n  snippet to build the gate rejection summary.\n- `references/gate-hardgate-fixes.md` — the three live gate fixes applied\n  2026-08-05 after a near-zero GO count was challenged: H1 R:R-floor epsilon,\n  H6 volume=0 data-gap handling, H2 %-floor stop-width skip. Exact diffs +\n  before/after GO counts. Read this before "fixing" the gate on a thin result.\n- `references/backtest-and-liquidity-validation.md` — the PRE-TICKET validation\n  pattern: backtest every GO on its own rule + backfill REAL 20-day volume for\n  the FX/indices/metal symbols the gate flagged "verify manually" (yfinance\n  returns volume 0 for `=X`/`^`), then consolidate to GO_TRADEABLE /\n  BLOCKED_LIQUIDITY / DO_NOT_TRADE. Includes two bugs found in\n  `backtest_go_setups.py` (side-case mismatch that returned None for ALL\n  symbols; profit_factor None-on-no-losses) and the yfinance ticker suffix\n  matrix (`=X` / `=F` / `-USD`) required for 3y history. Read this whenever a GO\n  list is about to be handed over as trades.\n- GO-validation orchestration (backtest + liquidity backfill + consolidation,
  emitting `go_postanalysis.json` with per-symbol PF + real-liquidity verdict)
  has NO bundled script — `validate_go_setups.py` does not exist in this skill
  or in `C:\Users\victo`. Compose it from `scripts/backtest_go_setups.py` plus
  the backfill recipe in `references/backtest-and-liquidity-validation.md`.
- `scripts/robustness_proof.py` — the three-test proof harness ("prove
  profitable all we can"): 10y window + walk-forward OOS + 60-combo parameter
  grid + t-test significance. `validate(sym, side)` returns GREEN_PROVEN /
  NOT_PROVEN with the failing tests named. Run `python3 robustness_proof.py
  "USDJPY=X:long"`. Read `references/robustness-proof.md` before using.
- `scripts/gold_5m_proof.py` — intraday edge proof harness for capital.com 5m
  gold (or any intraday symbol). 3-test bar on the max 60d yfinance window, net
  of a measured broker round-trip. Result 2026-08-06: gold 5m VWAP-bounce =
  NOT PROVEN (broker-cost trap). Knowledge bank in
  `references/intraday-proof-gold-5m.md`.
- `references/intraday-proof-gold-5m.md` — the yfinance 60-day intraday cap
  (why the "mandatory 10y" proof rule does NOT apply to sub-daily bars), the
  gold 5m VWAP-bounce proof result, and the three refinements to offer. Read it
  before promising any intraday edge proof from this source.
- `references/robustness-proof.md` — the three-test proof bar, why one PF number
  is insufficient, the 2026-08-05 all-candidates-failed finding, and how to act
  on a NOT_PROVEN result (rescind + refine, do NOT manufacture a trade).
- `references/equity-momentum-gap-screener.md` — `gap_rvol_screener.py` (the
  new-config equity momentum layer): filters, output shape, the `small_cap`/
  `micro_cap` category normalization, the $2–20 USD band extraction snippet, and
  the single-pass combined-backtest recipe (`go_setups_tmp.json` shape +
  `backtest_go_setups.py` one-shot over all candidates).
- `references/mechanics-entries.md` — the "why price moves" layer: the five
  drivers (D1 stop-run, D3 VWAP-reclaim+volume, D4 exhaustion fade, D2 structure,
  D5 regime), what our data can/can't see, and the entry-design rule. Read this
  when the user asks for mechanics-based entries.
- `references/mechanics-driver-model.md` — the CANONICAL driver-model playbook:
  the symptom-vs-cause trap that sank the original 5 candidates, the five drivers
  D1–D5, what our data can/can't see, the 1h EVENT-SAMPLE-SIZE lesson, and the
  HTF-anchoring fix that produced the first GREEN_PROVEN edge (GBPJPY long). The
  single source of truth for "build entries on mechanics, not symptoms".
- `scripts/mechanics_entries.py` — the coded D1/D3/D4 triggers + `prove_trigger()`
  that runs each through the 3-test proof. Depends on `robustness_proof.py` in
  the same dir (imports `_load,_pf,_sig,rsi,atr,vwap`). Run backgrounded.
- `references/oneh-mechanics-practice-loop.md` — the 1h rebuild + HTF-anchored
  grab that produced the project's FIRST GREEN_PROVEN edge (GBPJPY long, ~2y 1h:
  IS 2.0 / OOS 3.0 / grid 9/9 / t-test p=0.0037, n=70). Wires the scan→gate→1h
  proof loop together, documents `mechanics_1h.py` / `mechanics_practice_1h.py` /
  `inspect_metals_fx.py`, and the Windows/yfinance-1h gotchas (no SIGALRM, `_symbol`
  lost on `.iloc[]`, inf-PF JSON, 1h throttle). Read this to RUN the practice
  loop, not just build entries.
- `references/nvidia-llm-narrative-acceleration.md` — the NVIDIA text-LLM endpoint: working models, the FAST default, the text-only caveat, the gauge-direction inversion pitfall, and a model-probe snippet.
- `scripts/nvidia_llm.py` — reusable client: `synthesize_nightshift(scan_data, gate_results, catalysts, gauge)` batches GO/WATCH setups into one call with a content-hash cache (0.0s re-runs). Key via env `NVAKEY`; `__main__` runs it against the latest nightshift artifacts.

- `references/standing-open-scan-cron.md` — the 09:37 / 14:37 ET standing
  all-sector open scan: cron wiring, `scripts/standing_open_scan_cron.py`,
  and the `ALLSECTOR_OPEN_YYYYMMDD.md` output contract.
  **Operational check:** these jobs are `deliver: local` AND only fire while
  the Hermes gateway runs. Confirm with `hermes cron status`; if the gateway
  is down the scans silently never run and no artifact is produced. Verify by
  the presence of a dated `ALLSECTOR_OPEN_*.md`, never by the job being listed
  as `[active]`.
