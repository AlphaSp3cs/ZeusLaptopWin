# Nightshift / Universal Scan Pipeline Map

Machine: Windows, git-bash. All scripts live directly in the user's home
directory (`C:\Users\victo`), not in a repo.

## Orchestrator (the ONLY safe entry point)

`run_universal_workflow.py`

```bash
python3 run_universal_workflow.py --dry-run       # print the 5-phase plan
python3 run_universal_workflow.py --scan-only
python3 run_universal_workflow.py --gate-only
python3 run_universal_workflow.py --report-only
python3 run_universal_workflow.py --execute-only
python3 run_universal_workflow.py --monitor-only
python3 run_universal_workflow.py --profile swing # or day
```

Phases:
1. Universal scan — `universal_premarket_scan.py`
2. Enhanced gate — `enhanced_trade_gate.py` (as a LIBRARY)
3. Quant report — `make_universal_report.py` → Desktop + OneDrive
4. MT5 execution — `mt5_dual_executor.py` (FTMO left + Capital.com right)
5. Position monitor — trailing / breakeven / risk

## Phase scripts

| Script | Real entry point? | Notes |
|--------|-------------------|-------|
| `universal_premarket_scan.py` | yes | 110 assets, ~2-4 min. Run backgrounded. |
| `enhanced_trade_gate.py` | **NO** | `__main__` is a hardcoded single-GC test. Library only — call via orchestrator. Exposes `process_all_setups(scan_data, profile_type, account_equity)` and `setup_to_dict()`. |
| `blogwatcher_integration.py` | yes | `__main__` is a live smoke test that prints real sentiment. Safe to run directly. |
| `.hermes/gauges/danger_zone_gauge.py` | yes, but | infinite 60s loop. Wrap: `timeout 40 python3 ...` and background it. |

## Output files

| File | Written by |
|------|-----------|
| `universal_scan_results_latest.json` | phase 1 |
| `universal_scan_results_<ts>.json` | phase 1 |
| `enhanced_setups_swing_latest.json` | phase 2 |
| `enhanced_setups_day_latest.json` | phase 2 |
| `.hermes/gauges/danger_zone/latest_gauge.json` | gauge |
| `.hermes/gauges/danger_zone/history.db` | gauge (SQLite) |

`*_latest.json` is a **copy**, not a symlink — symlinks fail on Windows without
privilege (`WinError 1314`). The workflow prints "Copied X -> Y (symlink
failed...)" which is normal.

## Scan result JSON shape

```
{ scan_timestamp, categories, qualified_longs[], qualified_shorts[],
  total_assets_scanned, total_qualified_longs, total_qualified_shorts }
```

Each qualified entry: symbol, name, category, price, change_24h, change_5d,
rsi, atr, ema20/50/200, vwap, vwap_upper/lower_1/2, vwap_distance_pct, volume,
avg_volume_20, vol_ratio, above_vwap, above_ema*, trend, long_score,
long_reasons[], stop_loss, take_profit_1/2, rr, stop_atr_mult, asset_class.

## Gate result JSON shape

```
{ profile, account_equity, summary{total/go/no_go longs+shorts},
  validations{GO[],NO-GO[]}, longs[], shorts[] }
```

Each setup carries `validation`:
```
{ verdict: "GO"|"NO-GO", binding_reason, profile,
  hard: {H1_rr,H2_stop,H3_size,H4_conc,H5_earn,H6_liq,H7_ext},
  metrics: {...}, flags[], all_fails[] }
```

`verdict == "GO"` requires `all(hard.values()) and not fails`.

### The 7 hard checks

| Check | Meaning | Typical failure |
|-------|---------|-----------------|
| H1_rr | R:R to T1 at/above floor (swing 2.0, day 1.5) | FX collapses to 0.26-0.32 after slippage; exact-floor values (1.50 vs 1.5) fail |
| H2_stop | Stop width within ATR band | SHV 88x ATR; FX futures 7-12x on 5m |
| H3_size | Position size sane | rare |
| H4_conc | Concentration cap by sector | rare |
| H5_earn | Earnings blackout | always flags "no earnings_date supplied" |
| H6_liq | ADV + dollar-volume floors | **dominant blocker** — kills raw futures, cash indices |
| H7_ext | Entry not over-extended past 20-EMA | day profile, chasing |

### Sector profiles (swing / day)

`SECTOR_PROFILES` in `enhanced_trade_gate.py` keys on: crypto, forex, indices,
commodities, metals, energy, bonds, etfs, futures. Each has `rr_floor`,
`atr_stop_mult`, `risk_pct`, `concentration_cap`. `SYMBOL_SUB_CATEGORY` remaps
individual symbols (e.g. `UNG` → energy, `TLT` → bonds, `GC` → metals).

## Liquidity floor gotcha (worked example)

```
UNG    px 9.77     ADV20 8,389,131   $vol  81,961,818   -> PASSES
RB=F   px 2.86     ADV20    42,698   $vol     122,222   -> FAILS ($10M floor)
UGA    px 107.25   ADV20    55,773   $vol   5,981,697
BOIL   px 19.29    ADV20 4,626,549   $vol  89,246,131
KOLD   px 31.10    ADV20 2,200,036   $vol  68,421,108
XOP    px 171.95   ADV20 3,299,143   $vol 567,287,586
FCG    px 28.60    ADV20   680,006   $vol  19,448,163
```

Raw futures and `^`-prefixed cash indices report near-zero or literally `$0`
dollar volume in yfinance. Their ETF proxies clear the floor easily. Always
check the proxy before declaring a name untradeable.

## Known data-source limits

- **CoinGecko 429s** hard under load — only ~4 of 43 crypto assets get full
  OHLC in a full run. Re-run the crypto leg separately if crypto matters.
- yfinance `$0` dollar volume for cash indices is a data artifact, not a real
  liquidity reading.
