# Worked Example — Nightshift Scan (2026-08-04)

A complete nightshift run, start to finish, as a reference for pacing and shape.

## Invocation order actually used

```bash
# 1. Long scan — background, notify on complete
cd <home> && python3 universal_premarket_scan.py 2>&1 | tail -60
#    -> background=true, notify_on_complete=true

# 2. Blogwatcher in parallel, foreground (fast)
cd <home> && python3 blogwatcher_integration.py 2>&1 | tail -40

# 3. Trade gate, after scan JSON lands
cd <home> && python3 enhanced_trade_gate.py 2>&1 | tail -45

# 4. Extract ONLY the GO verdicts (critical — see below)
python3 -c "
import json
for p in ['swing','day']:
    d=json.load(open(f'enhanced_setups_{p}_latest.json'))
    for side in ['longs','shorts']:
        for t in d[side]:
            v=t.get('validation',{})
            if v.get('verdict')=='GO':
                m=v.get('metrics',{})
                print(side, t['symbol'], m.get('real_entry'), t.get('stop_loss'),
                      m.get('real_t1'), m.get('rr'), m.get('notional_pct'),
                      m.get('pct_risk'), t.get('rsi'))
"

# 5. Gauge — MUST be timeout-wrapped, it loops forever
cd <home> && timeout 40 python3 .hermes/gauges/danger_zone_gauge.py 2>&1 | head -25
#    -> background=true, then process(action='wait')
```

## The context-flood mistake to avoid

Printing every setup with its full `validation` object returned roughly 20,000
characters of JSON for 34 candidates — hard-gate booleans, per-setup metrics
dicts, `flags`, and `all_fails` arrays for each. Almost all of it was NO-GO rows
that only needed a one-line aggregate summary.

The corrected one-liner above returned 12 lines and was all that the report
needed. **Filter on `verdict == 'GO'` at the extraction step, never after.**

## Readings from this run (shape reference, not current data)

- Danger Zone Gauge: 82.5/100, base 72.5 + PM overlay 10 = EXTREME DANGER.
  Signal breakdown: Tech Euphoria 100, Consumer Leverage 100, PM Divergence 100,
  Profit Margin 75, Rate Regime 30, Hash Ribbons 30.
- Blogwatcher: 100 articles, regime shift risk HIGH, ETH BEARISH/HIGH,
  SOL BEARISH/HIGH, BTC NEUTRAL/MEDIUM.
- Universe: 110 assets scanned. Pre-gate 15 LONG / 27 SHORT.
- Post-gate swing: 7 GO (2 long, 5 short). Post-gate day: 4 GO (0 long).

## The cross-asset pattern worth naming

Every major global equity index came back simultaneously RSI 65-68 **and**
3.7-5.5% above VWAP: DAX 67.0, FTSE 65.1, CAC 65.1, HSI 67.9, Nifty 66.8,
SPX 66.3, DJI 66.7.

The insight to state plainly: when everything is extended at once there is no
rotation left to absorb a shock. This kind of cross-asset synchrony is the single
highest-value observation a scan can surface — hunt for it explicitly rather than
reporting each index in isolation.

Companion tell in the same run: SHV (short-duration Treasury) at RSI 92.8 —
cash maximally crowded — mirroring TLT at RSI 35.2 on the long-duration end.
Two ends of the same trade.

## Convergence is the conviction filter

The highest-conviction name was ETH short, because it was the only setup where
the **technical gate and the news sentiment engine independently agreed**.
Blogwatcher flagged BEARISH/HIGH on institutional rotation news while the gate
passed the short on clean R:R. When ranking GO setups, promote the ones with
technical + sentiment convergence.

Conversely note divergence: Hash Ribbons read Normal (30, no miner capitulation)
while crypto sentiment deteriorated. Sentiment moving faster than fundamentals
*is* the trade thesis — say so.

## Gate rejections in this run, grouped

- **Liquidity floor (H6)** — dominant blocker. Killed all futures, commodities,
  and cash-index setups. `^`-prefixed indices report $0 dollar-volume in
  yfinance; a data artifact, not a real tradeability verdict.
- **R:R at floor (H1)** — day-profile names computing exactly 1.50 against a 1.5
  floor; FX names collapsing to 0.26-0.32 R:R once slippage was applied.
- **Stop width (H2)** — SHV at 88x ATR, FX futures 7-12x ATR on the 5m.
- **CoinGecko 429** — only 4 of 43 crypto assets got full OHLC. Reported as a
  partial-coverage caveat with an offer to re-run just the crypto leg.

The two deepest-oversold names in the whole universe (UNG -11.25% vs VWAP /
RSI 33.7, RB -11.39% / RSI 33.6) passed every hard check **except** the liquidity
floor. Surface these as a watch list with a liquid-proxy suggestion rather than
dropping them silently.
