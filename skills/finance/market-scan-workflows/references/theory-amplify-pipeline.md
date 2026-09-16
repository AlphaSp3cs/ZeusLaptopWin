# Theory Amplify Pipeline — technique detail (2026-08-08)

Companion to the AMPLIFY section in SKILL.md. Reusable whenever the user says
"amplify our theories" / "use the theories in all-sector scans".

## theory_amplifier.py — confluence scorer (0-100, no future leak)
Each sub-score 0..1 from data available AT bar k ONLY:
- T1 technical: RSI(14) in reversion sweet-spot (30-58)=0.4, price>MA50=0.3,
  price>MA200=0.3.
- T2 drawdown base-rate: `<=-90%` from ATH = 1.0 (measured +109%/72% @24m);
  -80..-90% = 0.55; -70..-80% = 0.15; -25..-70% = 0.0 (INCINERATOR); shallow = 0.30.
- T11 breadth/regime: above MA200 (0.5) + MA200 slope>0 (0.5) = master gate.
- T10 funding (crypto only): live ccxt funding rate. Deeply negative = squeeze
  bullish (0.9); extreme positive = froth (0.1); ~0 = 0.5.
- Composite = weighted sum over AVAILABLE scores (missing => 0 weight, never fabricated).
- Verdict: >=70 ACCUMULATE | 45-69 WATCH | <45 AVOID.
- REGIME GATE: if T11 RED, cap at WATCH (never ACCUMULATE); AVOID if T2 doesn't pay.

## ccxt funding fix (T10) — DO NOT skip
`ex.fetch_funding_rate("BTC/USDT")` raises
`NotSupported('supports linear and inverse contracts only')`. Use the SWAP symbol:
`"BTC/USDT:USDT"`. Same for `fetch_open_interest`. Roots are mapped in the `T10_SWAP`
dict inside theory_amplifier.py. Cache to `theory_funding_cache.json` with an offline
fallback (TTL 1800s) so a network failure degrades to n/a instead of crashing a scan.

## Look-ahead-free backtest (theory_backtest.py)
- For every bar k with >=200d history AND a forward 24m window: compute amplifier
  confidence from `df.iloc[:k+1]` (data through k); record the TRUE forward return
  1m/6m/12m/24m from `close[k]` — this is the LABEL, genuinely future.
- Pool across coins; bucket by verdict band; report median forward return + win%.
- Compare to the UNCONDITIONAL baseline (all windows pooled).
- Edge = MONOTONIC band ordering (top>mid>bottom) AND top band beats baseline.
- LIMITATION: rolling daily windows overlap => n inflated; treat as a directional
  base-rate, same caution as the original T2 study.
- RESULT on 14 cached coins / 28,430 windows: 24m ACCUMULATE +22.8%/58w, WATCH
  +12.6%/54w, AVOID -31.9%/39w, baseline -1.7%/49w => GREEN-ish DIRECTIONAL edge,
  but ONLY at 24m (1m/6m/12m mostly negative) => it is an ACCUMULATION signal, not a
  trade-timing signal. Do NOT dress a 24m edge up as a swing system.

## Data reality on this machine (verify before re-running)
- yfinance LIVE fetch is BROKEN (TypeError on `df['Close']` float cast). Backtest on
  the cached REAL bars instead of fresh pulls: `crypto_px.pkl` (14 coins, 2016-2026
  daily) and `crypto_dd_baserates.csv` (171k rows of historical dd->forward return).
  Cached bars are genuine, not synthetic.
- 14 cached coins: DASH FIL BCH NEAR DOT AVAX LTC LINK DOGE ADA XLM AAVE INJ WLD.
- `numpy.bool_` is NOT JSON-serializable — cast `bool(...)` before json.dump.
