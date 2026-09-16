# Pitfalls Catalog — market scan pipeline runs

Extracted from SKILL.md 2026-08-07 to keep the always-loaded skill lean.
Every pitfall previously inline lives here verbatim.

## Pitfalls

- **Never state a rejection reason you have not read.** Asked "is UNG a buy same
  as RB?", the honest move was to open the validation record. Grouping two names
  under one asserted cause was wrong: RB failed liquidity ($557/day dollar
  volume), UNG passed every gate and was a GO. Always print
  `validation.hard`, `binding_reason`, and `all_fails` per symbol before
  characterising why something was excluded.
- **A liquidity failure on a futures symbol says nothing about its ETF proxy.**
  yfinance reports tiny dollar volume for raw futures (`RB=F`) and `$0` for
  cash indices (`^GSPC`), so those fail liquidity floors mechanically. The
  liquid ETF equivalent may pass easily. Check the proxy before writing a name off.
- **Nightshift and daytime pipelines share the SAME gate module but MUST write
  SEPARATE output files.** Running the enhanced gate on a nightshift scan with
  default output names (`enhanced_setups_*_latest.json`) silently overwrites the
  daytime universal gate results, and vice-versa. Nightshift writes
  `nightshift_setups_swing_latest.json` / `nightshift_setups_day_latest.json`;
  daytime writes `enhanced_setups_*_latest.json`. Keep them namespaced. If you
  must run the gate directly for nightshift, pass `--scan-file
  nightshift_scan_results_latest.json` AND redirect the outputs to the
  namespaced names (the orchestrator `nightshift_report.py` does this for you).
- **Do not use `&` backgrounding in the terminal tool.** It is rejected; use
  `background=true`. `process action=wait` clamps to ~60s, so poll again rather
  than requesting a long timeout.
- **The gauge does not live in the home dir.** `danger_zone_gauge.py` is at
  `~/.hermes/gauges/danger_zone_gauge.py` and writes its JSON one level deeper at
  `~/.hermes/gauges/danger_zone/latest_gauge.json` — not `~/latest_gauge.json`.
  Running it from the home dir gives "No such file". `cd ~/.hermes/gauges`, wrap
  in `timeout 60`, then read the `danger_zone/` JSON.
- **LAST-SCAN MEMORY (standing carry-forward, added 2026-08-06).** The scanner now remembers the previous run and reuses it AS ASSETS POPULATE: `universal_premarket_scan.py` writes `universal_scan_last_snapshot.json` (compact per-symbol price/rsi/vwap/vol/gap) at the end of every scan, and `main()` loads it before each run so every populated asset gets `last_scan` + `*_chg_since_last` deltas (`price_chg_since_last`, `price_chg_pct_since_last`, `rsi_chg_since_last`, `vwap_dist_chg_since_last`, `vol_ratio_50_chg_since_last`, `gap_chg_since_last`) and `is_new_since_last`. The all-sector report (`cron_allsector_open_scan.py`) renders a `## SINCE LAST SCAN` section (top movers by |% chg| + newly-appeared count). Wiring: `load_last_scan_snapshot()` / `save_last_scan_snapshot()` in the scanner; `prev_snapshot` threaded into `scan_asset_class()`. This makes the standing kill-list carry-forward discipline STRUCTURAL instead of manual. Verify it landed with `scripts/verify_scan_memory.py` (probes latest.json + snapshot).
- **EDITING A PHASE SCRIPT CAN LEAVE A STALE `latest.json` UNTIL `__pycache__` IS CLEARED — a DIFFERENT trap from the `__main__`-harness one above.** After you edit `universal_premarket_scan.py` (or any phase module), the cron path shells out via `subprocess.run([sys.executable, ...])`. If a stale `.pyc` is cached, the subprocess runs OLD bytecode and writes a `latest.json` that looks fresh (new mtime) but is missing your new fields — e.g. 0/188 assets had `last_scan` attached despite the module printing 'Last-scan memory: N symbols'. Symptom: the module prints its new log line but the produced `*_latest.json` does NOT contain the new keys. Fix: `rm -rf __pycache__` (narrow, in the script dir — a recursive home-root wipe TIMES OUT on this machine) then re-run. Always confirm the new field is actually PRESENT in the output JSON, not just that the run printed the expected log line. `scripts/verify_scan_memory.py` catches this automatically (attached==0 => FAIL).
- **If a phase script dies on `ModuleNotFoundError`, check the interpreter before
 blaming the pipeline.** `run_universal_workflow.py` shells out to
 `sys.executable`, which under Hermes is the agent venv; the scan deps
 (yfinance etc.) live on the *system* interpreter. Probe with
  `python3 -c "import yfinance,sys;print(sys.executable)"` and invoke the phase
  scripts with whichever interpreter resolves, rather than concluding the chain
  is broken.
- **Recursive searches from the home root time out.** Scope to a subdirectory
  or use `ls`+`grep` on a narrow glob.
- **When the user pushes back on a claim, verify before defending or
  re-running.** Twice this session a challenge ("is UNG a buy same as RB?",
  "you are not following orders") exposed a real bug rather than a
  misunderstanding. The correct first move is to open the underlying record and
  say plainly what you got wrong and why — not to re-run the same pipeline and
  hand back the same shape of answer. Diagnose, state the defect, then fix.
- **Report contradictory signals as contradictions, not as extra confirmation.**
  The 2026-08-05 scan produced four long-JPY-cross forex setups (USDJPY RSI
  24.0) alongside a large short-equity book. Both are real, but they are
  opposite sides of the same yen/risk-off trade — stacking them is not
  diversification. Say so explicitly and make the user pick a side. Listing
  every GO in one table implies they combine.
- **Do not silently substitute a different universe for the one requested.** If
  the user named asset classes and the pipeline cannot deliver them, say that
  out loud in the report rather than shipping whatever did survive. Volume of
  correct-looking output is not the deliverable; covering the mandate is.
- **Report retractions are expensive.** When you discover a prior report was
  built on stale data, say so plainly, state exactly which claims changed, and
  reissue the corrected numbers. The user tracks the diff between the two.
- **The gate rejects ~95% of the qualified book on the R:R FLOOR, not on fundamentals — a calibration cliff, not a market read.** The universal scanner sets T1 at *exactly* the gate's minimum R:R (2.00 swing / 1.50 day); broker costs then shave **net** R:R just under it, so H8 fails by a hair. Signature: dominant `binding_reason` = "R:R to T1 is 2.00, floor is 2.0" (swing) or "1.50, floor is 1.5" (day), with a tail of "net R:R after <broker> costs is 1.95, floor 2.0 (gross 2.00; spread 0.01%)". On 2026-08-05 this produced 0 GO / 65 NO-GO swing and 3 GO / 62 NO-GO day. **Do NOT silently loosen the floor** — that manufactures tickets from nothing. Present it as a FINDING and offer three moves: (a) backtest the near-miss set, (b) widen the floor explicitly and label it a parameter change, (c) hold (often right under an EXTREME DANGER gauge). Evidence + the `Counter`-over-`binding_reason` aggregation snippet in `references/gate-rr-floor-calibration.md`. To aggregate per profile: load `enhanced_setups_*`_latest.json`, iterate `longs`/`shorts`, and `Counter(v.get("binding_reason") or (v.get("all_fails") or ["?"])[0])` for each `verdict != "GO"`.
- **The enhanced gate crashes on `ZeroDivisionError` when a flat/stale instrument has ATR == 0.** `validate_trade_gate()` builds the extension check `ext = (real_entry - ema20) / atr14 ...` but only guarded `ema20 > 0`, not `atr14`. Any symbol with `atr14 == 0` (no range over the window) divides by zero and the WHOLE gate run dies — even for one symbol — aborting the report before any setup is graded. **Validated fix (2026-08-05, applied live):** change the guard to `if ema20 and ema20 > 0 and atr14 and atr14 > 0:` and let the `else` branch flag `"no ema20/atr supplied - extension/chase not checked"`. This also hardens the nightshift run (it shares the same gate module). Crash signature: `ZeroDivisionError: float division by zero` at `enhanced_trade_gate.py:453`. If a gate run dies there again, re-apply that guard — do NOT loosen the risk floors to dodge it. Note the gate's other H7 line at ~line 427 already guards `rps > 0`; ATR itself was the unguarded one.
 - **A near-zero GO count after the gate is a GATE-BUG SIGNAL, not a market read — inspect the gate before concluding "no setups exist".** When the user challenges the absence of setups (e.g. "out of all the metals, forex, indices, crypto you don't have a good setup?"), the correct move is to open `enhanced_setups_*_latest.json`, load each named-class candidate, and read `validation.binding_reason` / `validation.all_fails` — NOT to re-confirm the verdict counts. On 2026-08-05 a 0-GO swing / 3-GO day result was challenged and inspection showed three silent mis-rejections in `enhanced_trade_gate.py`, fixed live after the user said yes: **(1) H1 R:R floor** failed on float rounding when gross R:R landed exactly on the floor (2.00 vs 2.0) — fixed with `rr + 1e-9 >= cfg['rr_floor']`; **(2) H6 liquidity** hard-rejected FX `=X` and cash-index `^` symbols because yfinance returns `volume 0` / `$vol 0` (a data gap, not illiquidity) — fixed so `dollar_volume <= 0` passes with a "verify manually" flag; **(3) H2 stop-width** spuriously flagged cheap-asset stops as "6.5x ATR too wide" because the stop is set by the 2% min-% floor, not ATR — fixed by skipping the ATR-width check when `stop_floor_driven` is True. H8 (net R:R after broker costs) was deliberately LEFT INTACT. After the fix: 0→4 SWING GO, 3→15 DAY GO. Do NOT silently "loosen" the gate to manufacture a balanced list — audit the gate logic, fix genuine bugs, and report real risk-floor misses as findings. Exact diffs + verification in `references/gate-hardgate-fixes.md`.
 - **Backtest output of `[]` (PF all n/a) is also a BUG SIGNAL, not an edge-less book.** `backtest_go_setups.py` silently returns `None` for every symbol when its trigger checks `side == "LONG"` but callers pass `side="long"` (lowercase) — the boolean is always False, so 0 trades, so `if not trades: return None`. If `backtest_go_results.json` is empty, inject a `print("DBG trades=", len(trades))` rather than concluding the scanner has no edge; the one-char case fix (`side = side.upper()` at the top of `backtest()`) restores ~17 trades/symbol. A manual reimplementation of the loop that "works" while the function returns None means the FUNCTION has the bug. Also: raw scan symbols (USDJPY, GC, CT) 404 on yfinance 3y history unless suffixed (`=X`, `=F`, `-USD`, `^`) — the mapping lives in `references/backtest-and-liquidity-validation.md`. Full pre-ticket validation pattern there.
 - **OPTIONS are NOT in the scan universe — say so, do not silently drop them.** `ASSET_UNIVERSE` covers forex, indices, commodities, bonds, ETFs, small/micro caps, futures, and crypto, but there is **no options category**. When the user says "include options" / "options too", the scanner cannot produce option-chain setups (no IV rank / skew / gamma leg). State the gap explicitly in the report and offer to build a separate leg (yfinance `Options` chain + IV percentile). Handing back an equity/ETF/futures-only report after being asked for options reads as forgetting the request.
- **For a pure SCAN request, do NOT run the live MT5 execution phase.** `run_universal_workflow.py` Phase 4 (`--execute-only`) places GO setups on FTMO + Capital.com. A "run a scan" / "do a nightshift scan" request is analysis, not a trade order. Run scan → gate → blogwatcher → gauge → report only. The standing rule still holds: a GO validates risk mechanics, NOT edge, so no live ticket goes out before backtest validation, and PF < 1.0 = do not trade. Surface the GO list and **ask before any execution**.
- **After a NIGHTSHIFT scan, the user often wants a FOLLOW-UP full daytime universal sweep.** Recurring pattern (2026-08-05): run `nightshift_report.py` first (overnight tradeable universe), then the user asks for "regular market — stocks, ETFs, options, futures, and the rest." That second leg is `python3 run_universal_workflow.py --scan-only` (full `ASSET_UNIVERSE`: stocks/ETFs/bonds/futures/fx/commodities/indices/crypto). Options are not covered (see bullet above); skip the execute phase unless told otherwise.

