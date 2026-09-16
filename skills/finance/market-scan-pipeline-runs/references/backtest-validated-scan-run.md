# Worked run: all-sector all-asset premarket scan with backtest validation

Session 2026-08-05. User asked: "all sector all assets, pre market scan for
viable setups, backtest and give me entry, stoploss, and takeprofit."

This is the reference shape for any scan request that ends in executable
tickets. The backtest step is what makes it different from a plain scan.

## Phase order actually used

1. `ls *.py | grep -iE "night|sonar|sector|universal|premarket|trade_gate|blogwatcher|gauge|backtest"`
2. `python run_universal_workflow.py --dry-run` — shows the 5-phase plan.
3. Scan backgrounded + blogwatcher foregrounded **in the same turn** (blogwatcher
   is fast and frames the report; the scan takes minutes).
4. Gate: `python3 enhanced_trade_gate.py` (has a real CLI now, safe to call).
5. Gauge: `cd ~/.hermes/gauges && timeout 60 python3 danger_zone_gauge.py`.
6. Project GO rows -> `go_setups_tmp.json` -> `scripts/backtest_go_setups.py`.
7. Write dated report `ALL_SECTOR_SCAN_<YYYYMMDD>.md` in the home dir.

## Two environment facts that cost a cycle

- `run_universal_workflow.py --scan-only` failed instantly:
  `ModuleNotFoundError: No module named 'yfinance'`. The orchestrator shells out
  to `sys.executable`, which under Hermes is
  `...\hermes-agent\venv\Scripts\python.exe`. The system `python3` (3.13) has
  yfinance 1.5.2. Fix: probe interpreters, then invoke the phase scripts
  directly with the one that resolves.
- `danger_zone_gauge.py` is NOT in the home dir. It is at
  `~/.hermes/gauges/danger_zone_gauge.py` and its JSON is at
  `~/.hermes/gauges/danger_zone/latest_gauge.json` (one level deeper than the
  script). Read the JSON rather than re-running the loop when it is recent.

## Coverage check result (all classes present — no silent drop)

```
commodities 1L/4S | crypto 5L | etfs 5L/15S | forex 4L | futures 4L/4S | indices 1L/8S
134 assets scanned, 20 qualified longs / 31 qualified shorts
```

## Regime readings

- Danger Zone **82.5/100 — EXTREME DANGER / HEDGE AGGRESSIVELY**
  (base 72.5 + 10 premarket overlay). Tech euphoria 100, consumer leverage 100,
  PM divergence 100 (PM recession odds 45% vs street 22%), profit margin 75,
  rate regime 30, hash ribbons 30.
- Blogwatcher: 100 articles, `regime_shift_risk = HIGH`, trade context for both
  BTC and AAPL longs = `HOLD_FOR_CLARITY`.

## The backtest result — the whole point of the session

3y daily bars, gate's own rule, 17 GO symbols.

Positive expectancy:

| Symbol | Side | Trades | Win% | Avg R | Total R | PF |
|---|---|---|---|---|---|---|
| XLU | LONG | 17 | 58.8 | +0.52 | +8.9 | 2.47 |
| HYG | SHORT | 28 | 46.4 | +0.22 | +6.3 | 1.55 |
| XLE | SHORT | 33 | 42.4 | +0.17 | +5.7 | 1.35 |
| XLM-USD | LONG | 41 | 46.3 | +0.05 | +2.2 | 1.13 |
| 000001.SS | LONG | 25 | 40.0 | +0.03 | +0.7 | 1.05 |
| ETC-USD | LONG | 36 | 41.7 | +0.01 | +0.2 | 1.02 |

Negative expectancy despite GO:

| Symbol | Side | Win% | Avg R | PF |
|---|---|---|---|---|
| ^GSPC | SHORT | 15.8 | -0.54 | 0.32 |
| SPY | SHORT | 16.2 | -0.46 | 0.40 |
| ^IBEX | SHORT | 23.8 | -0.43 | 0.38 |
| XLI | SHORT | 25.0 | -0.44 | 0.35 |
| QQQ | SHORT | 18.9 | -0.39 | 0.44 |
| XLF | SHORT | 27.3 | -0.31 | 0.54 |
| XLK | SHORT | 28.9 | -0.20 | 0.68 |
| DOT-USD | LONG | 40.0 | -0.13 | 0.75 |
| UNG | LONG | 36.0 | -0.16 | 0.71 |
| XLB | SHORT | 37.0 | -0.11 | 0.80 |
| XLY | SHORT | 36.0 | -0.02 | 0.96 |

**Reading:** the gate's largest and most confident block is its worst rule.
Shorting RSI>60-above-VWAP on US indices/cyclical sector ETFs is a bull-market
artifact. An 82.5 gauge is not a licence to trade a 0.32 profit factor. The
correct bearish expression was HYG (credit cracks first) and XLE — the two
shorts that actually backtest positive.

## Ticket format the user wanted

Fenced block per trade, plus a global sizing line. Half size when the gauge is
extreme and blogwatcher is HIGH.

```
LONG XLU (Utilities) — PF 2.47
Entry  : 44.11   (limit 43.95-44.20)
Stop   : 42.96   (-2.60%,  2x ATR)
TP1    : 46.40   (+5.20%,  2R)  — take 60%
TP2    : 47.55   (+7.80%,  3R)  — runner, stop to BE after TP1
Size   : 20% notional / 0.5% risk       RSI 38.3, 1.46% below VWAP
```

Plus an explicit `DO NOT TRADE` block naming every negative-expectancy GO, and a
line warning against stacking HYG + XLE + the index shorts — that is one
risk-off bet in three costumes, not diversification.
