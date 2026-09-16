# SCAN ROUTER — one entry point for every scan

    python3 scan.py <mode> [--equity N] [--no-news] [--no-gate] [--dry-run]

## Modes

| mode | what it scans | tradeable set |
|---|---|---|
| `premarket`  | US premarket, all sectors | equities, etfs, fx, commodities, indices, crypto |
| `nightshift` | overnight US-evening session | fx, commodities, indices, crypto (equities = context only) |
| `allsector`  | full orchestrated workflow | scan -> gate -> quant report -> SEPS |
| `crypto`     | CEREBRO cryptoweekend | liquid crypto movers |
| `rsi`        | oversold/overbought sweep + per-name backtest | 43 validated crypto |
| `bottom`     | monthly deep-drawdown re-screen | CoinGecko top 500 |
| `ladder`     | DCA tape refresh + tranche check | NEAR/INJ |
| `news`       | news repetition tracker | all crypto news |
| `recheck`    | the "check again" chain | crypto + news + tape + ladder |

## Every mode runs the same three rails

1. **Danger gauge first** — `.hermes/gauges/danger_zone_gauge.py`. Prints regime
   score before anything else, because it changes how every candidate is read.
   `>=75` prints an EXTREME warning and you should expect gate refusals.
2. **News overlay** — `crypto_news_tracker.py --quiet`. Silent unless a theme is
   NEW or ESCALATING (3h cooldown + baseline freeze).
3. **The gate is the only authoriser** — `enhanced_trade_gate.py`. A scan
   produces candidates; ONLY the gate produces GO. Never trade a raw scan row.

Nothing in this router places an order.

## Why nightshift is the template

`nightshift_scan.py` imports `universal_premarket_scan` and reuses its
indicators/fetchers, then strips closed-market instruments from the tradeable
lists while KEEPING them scored as correlation context. It emits the identical
JSON shape (`nightshift_scan_results_latest.json`), so the gate, the report
generator, blogwatcher and the danger gauge all consume it unchanged.

Any new session scan should follow that pattern: reuse the universal machinery,
restrict the tradeable set, emit the same shape. Do NOT fork a new scanner.

## Archived 2026-08-08

22 dead scanners moved to `.archive/scanners_20260808/` — 20 `ourotaurus_*` /
`ouroboros_*` one-off duplicates, a dated `market_scan_20260721.py`, and
`run_trade_gate_fixed.py`. Verified with an AST import sweep that NOTHING in the
workspace imported any of them before moving. Re-run that check before archiving
more:

```python
# walk every *.py, collect Import/ImportFrom, intersect with archive stems
```

Entry-point count went 62 -> 29. If you find yourself writing
`ourotaurus_<something>_scan_v3.py`, add a mode to `scan.py` instead.

## Pitfalls

- **`danger_zone_gauge.py` is an INFINITE LIVE MONITOR by default.** Its `main()`
  is `while True: ... time.sleep(60)`. Calling it from a script without `--once`
  hangs until the subprocess timeout — it only ever "worked" interactively
  because callers wrapped it in `timeout 60`. Added `--once` 2026-08-08
  (compute, print, write `latest_gauge.json`, exit). Runs in ~2s. Any scripted
  caller MUST pass `--once`.
- **The gauge prints ANSI colour codes inside the score token.** The raw line is
  `'  Gauge: \x1b[91m\x1b[1m\x1b[5m 82.5/100\x1b[0m ...'`, so a naive
  `float(line.split("Gauge:")[1].split("/")[0])` raises, gets swallowed by a
  bare `except`, and `score` stays `None` — meaning the EXTREME-regime warning
  silently never fires while the line still LOOKS right on screen. Strip with
  `re.sub(r"\x1b\[[0-9;]*m", "", out)` then regex `([\d.]+)\s*/\s*100`.
  Verify by asserting the parsed score is not None, not by eyeballing output.

- **A gate REFUSAL must fail the caller's exit code.** Found 2026-08-08: the
  router printed `[gate] REFUSED/FAIL` but never folded `ok_g` into `ok_all`,
  so `scan.py` exited 0 on a stale-scan refusal. A cron caller would record
  "ok" for a run that authorised nothing. Always `ok_all &= ok_g`. Verified by
  aging `scan_timestamp` 6h and asserting the returned flag is False — not by
  reading the printed line.
- **`ourotaurus_*` proliferation was the actual problem.** Twenty near-identical
  scanners meant nobody knew which one was authoritative. One router, one gate.
- **Gate refusals on stale scans are correct.** `--allow-stale` exists but using
  it defeats the 90-minute staleness protection. Re-scan instead.
- **Nightshift equities are context, not candidates.** They are scored but
  stripped from tradeable lists. Don't "rescue" them into a trade.
