---
name: freya-gap-scout
description: Freya (Pack Research & Intelligence / scout) competitive microstructure coverage — scans the live bar store for Wyckoff accumulation/distribution, VSA (volume spread / effort-vs-result), HVF (Hunt Volatility Funnel) and Market Profile (POC/VAH/VAL) setups the main scanner is blind to. Use when patching methodology gaps, building a "scout list", or covering competitor edge (Wyckoff/VSA/HVF/Market-Profile).
---

# FREYA GAP SCOUT — competitive microstructure coverage

Freya is the Pack's **Research & Intelligence / scout** mind. Her job: keep the
Pack sharp on competitor edge and frontier methodology, aggregate real signal,
and feed it into the strategy pipeline. This skill covers the four methodologies
the main scan engine (scan.py / universal_premarket_scan.py) was **blind** on:

1. **WYCKOFF** — accumulation/distribution footprint (selling-climax →
   secondary-test → spring → recovery). Multi-timeframe institutional structure.
2. **VSA (Volume Spread Analysis)** — effort-vs-result: big volume (effort) on
   small range (result) = absorption. Close position tells demand vs supply.
3. **HVF (Hunt Volatility Funnel)** — Francis "Freya" Hunt's contracting
   volatility funnel on a down leg, then breakout on expanding volume.
4. **MARKET PROFILE** — POC / VAH / VAL liquidity levels from intraday bars;
   flags continuation when price accepts outside the value area, or a
   liquidity-level rejection at VAL/VAH.

## Why it exists (competitive intel summary)

Benchmarked against the Pack's existing coverage:
- SMC / Order Blocks / FVG — PARTIAL (market-scan-pipeline-runs,
  market-timing-mastery). Execution-layer only, no macro context.
- Volume Profile / POC / Footprint — PARTIAL (all-sector-microstructure,
  market-microstructure-suite). Real profile math was missing though.
- Wyckoff / VSA / HVF / true Market-Profile (VAH/VAL) — **ABSENT** before this
  skill. These are the gaps Freya hunted and closed.

## How to run (real data only — no API, no keys)

The scanner reads the canonical bar store, never fabricates.

    # default: top-120 most-populated daily symbols across all sectors
    python3 freya_intel/gap_scanner.py --limit 120 --tf 1d

    # single symbol drill-down
    python3 freya_intel/gap_scanner.py --symbol BTC-USD

    # finer control
    python3 freya_intel/gap_scanner.py --tf 1d --mp-tf 1h --out /path/report.json

Outputs:
- `freya_intel/freya_gap_scan_latest.json` — machine-readable, gate-compatible
  (`results[].hits[]` carries `method`, `bias`, `confidence`, levels).
- A **SCOUT LIST** printed to stdout: `symbol  BIAS  methods`. This is the
  "scout list, not the warehouse" view — surface only names that look like live
  setups, recheck them on the next scan (per the standing re-check rule).

## Output schema (one hit)
- WYCKOFF: phase (accumulation_spring/test), climax_low, climax_vol_x, spring, bias, confidence
- VSA: signal (absorption_demand/supply), effort_x, result_ratio, close_position, bias
- HVF: signal (funnel_breakout), funnel_high/low, breakout_level, last_close, bias
- MARKET_PROFILE: poc, val, vah, value_area_pct, at_liquidity_level, bias

## Integration into the pipeline
- This is a **scout overlay**, not a trade authorizer. Run it as a value snapshot
  (like the off-hours protocol): register setups, recheck next scan, report DELTAS.
- To fold a gap-methodology hit into the main scan: a symbol flagged WYCKOFF or
  HVF with confidence >= 0.75 should be added to the main scan's watch list and
  run through `enhanced_trade_gate.py` for entry/SL/TP (the gate owns sizing).
- Do NOT treat MARKET_PROFILE alone as a trade — it is context (where the value
  area is). Confirm with Wyckoff/VSA/HVF or a main-scan setup.

## False-silence rule
If `bars.db` is missing/stale or a symbol has <120 bars, the detector returns
None and the symbol is silently skipped — that is correct, not a failure. The
scanner prints `Scanned N, signals M`; if M is implausibly high, tighten the
detector thresholds (they are deliberately conservative).
