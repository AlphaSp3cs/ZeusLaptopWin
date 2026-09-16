---
name: cerebro-crypto-scan
description: Cryptoweekend / crypto screen via the CEREBRO scanner.
---

# CEREBRO Crypto Scan (cryptoweekend)

CEREBRO is the user's custom multi-asset technical scanner
(`C:\Users\victo\workspace\think-tank\scanners\cerebro_scan.py`). It scores
RSI + MACD + Bollinger convergence into a 0–100 conviction score and a signal
(STRONG_BUY / BUY / WAIT / SELL / STRONG_SELL). Crypto data comes from ccxt
Binance; stocks from yfinance.

**CRITICAL — this workspace's "cryptoweekend scan" is NOT the universal
pipeline** (`universal_premarket_scan.py` → `enhanced_trade_gate.py`). When the
user says "cryptoweekend scan" / "collect data from cerebro" they mean: run
CEREBRO on the liquid crypto universe and backtest it. Follow THIS skill, not
`market-scan-workflows`' universal chain. (That skill's cryptoweekend entry is
wrong for this workspace — patched with a pointer to here.)

## Workflow
1. **Build the universe.** CoinGecko `coins/markets` top-250, keep only
   `total_volume >= $50M` AND `|price_change_percentage_24h| >= 2%` (liquidity
   floor + must actually move). Map each base ticker to a Binance `<BASE>/USDT`
   pair.
2. **Score with CEREBRO on REAL 1h OHLCV** (see pitfalls — bypass the mock
   fallback).
3. **Backtest the movers** on 10y daily yfinance `<BASE>-USD` with honest
   next-bar bookkeeping, split in-sample / walk-forward OOS, judge vs the
   3-TEST PROOF BAR.

Reusable scripts (live in `C:\Users\victo\`, NOT a `scripts/` subfolder — the
old `scripts/...` paths are wrong): `C:\Users\victo\cerebro_crypto_weekend.py`
(steps 1–2) and `C:\Users\victo\cerebro_crypto_backtest.py` (step 3). Run order:
`cd C:\Users\victo && python3 cerebro_crypto_weekend.py` then
`python3 cerebro_crypto_backtest.py`.

**Forced coverage + CLARITY Act:** `cerebro_crypto_weekend.py` auto-injects a
`FORCE_COVER` watchlist (COMP, ACT) so regulatory-catalyst tokens are never
filtered out on a quiet tape. Each scored result carries `forced_coverage` and
`clarity_act_relation`; dropped forced tokens go to `forced_coverage_skipped`.
See `references/clarity_act_defi.md`.

## Pitfalls (learned the hard way — 2026-08-07)
- **SILENT MOCK-DATA FALLBACK.** `CerebroScanner.fetch_crypto_data()` /
  `fetch_stock_data()` catch ALL exceptions and return `_generate_mock_data()` —
  a seeded (`np.random.seed(42)`) random walk. If ccxt errors, the symbol is
  wrong, or Binance has no pair, CEREBRO emits FAKE prices/RR and prints nothing.
  NEVER trust output without confirming the price is real. Bypass by fetching
  OHLCV yourself (ccxt `fetch_ohlcv`) and injecting `sc.df = df`, then call
  `sc.calculate_rsi()` / `calculate_macd()` / `calculate_bollinger_bands()` /
  `calculate_volume_confirmation()` + `sc.determine_signal()`. Do NOT call
  `sc.scan()` — it re-hits the network and can fall back to mock.
- **Binance symbol format = `/USDT`, not `/USD`.** CEREBRO's `scan()` does
  `if '/' in symbol and not symbol.endswith('USD')` → crypto branch. `BTC/USD`
  fails pair lookup → mock fallback. Always pass `BTC/USDT`. CoinGecko returns
  base tickers (BTC, ETH, XRP) → append `/USDT`.
- **Validate the pair before scanning.** Load `ccxt.binance().load_markets()`
  and keep only `active` pairs ending `/USDT`. Names with no Binance pair
  (SKYAI, LIT, CYS) would force mock data — skip them.
- **Gold tokens are NOT crypto.** XAUT (Tether Gold) / PAXG (Paxos Gold) pass
  the numeric liquidity filter and can backtest "GREEN", but their edge is
  gold's mean-reversion. Exclude from the crypto plan; list only for
  transparency.
- **THREE exclusion classes, not one — critical once the universe is >250.**
  Strip stablecoins AND gold tokens AND wrapped/liquid-staking receipts (WBTC,
  WETH, STETH, WSTETH, WEETH, CBBTC, RETH, JITOSOL, MSOL, TBTC, BTCB...).
  Wrapped/LST names have no independent price — they are a second copy of
  BTC/ETH/SOL, so they double-count the majors in any pooled base-rate study.
  Measured effect of de-duplicating (2026-08-08): the <=-90% bucket's 12-month
  median went from +3.2% to +44.6%.
- **A big PF that clears BOTH IS and OOS can still be a random walk.** LINK
  (IS 3.07 / OOS 1.85) and BCH (IS 1.47 / OOS 1.61) both passed a two-test bar
  yet had permutation p = 0.18 and 0.33. Run the permutation test always, and
  grade AMBER_NOT_SIGNIFICANT rather than GREEN when p >= 0.05.
- **Overfit trap (3-TEST PROOF BAR).** An asset with negative in-sample PF but
  huge out-of-sample PF (BONK PF 2.42 IS / 0.39 OOS; ENA 0.61 IS / 2.9 OOS) is a
  fake edge. Require IS PF≥1.0 AND OOS PF≥1.0 on the SAME side. See the
  `trading-backtest-integrity` skill.
- **yfinance `<BASE>-USD` silently returns the WRONG asset for renamed/relisted
  tokens.** Observed 2026-08-07: UNI came back at $0.000163 (real $4.04), APT
  $0.000131 (real $0.58), POL $0.0082 (real $0.075); TIA and ARB the same. These
  are stale/squatted feeds, and an absurd "-99.99% from ATH" reading is the tell.
  ALWAYS cross-check every yfinance last close against the CoinGecko
  `current_price` for that symbol and DROP any name where
  `abs(yf_last/cg_price - 1) > 0.15`. Never rank or backtest a failed name.
- **Depth alone is a falling knife.** Ranking purely by % from ATH promotes names
  that printed a NEW low weeks ago (FIL, DOT, AVAX, LTC in Aug 2026). Pair the
  drawdown rank with a structure filter — see
  `references/crypto_bottom_research.md` for the scoring recipe and base rates.
- **ccxt was once missing** (`ModuleNotFoundError: No module named 'ccxt'`). If
  import fails: `pip install ccxt yfinance pandas numpy`. Same for yfinance under
  bare `python` on this host — the venv `python3` has it.
- **`chg_24h` / `volume_24h` can be None → TypeError crashes the run.** FORCED
  coverage names (COMP, ACT) bypass the CoinGecko mover filter and reach the
  print with no 24h fields, so `f"{r['chg_24h']:+.1f}%"` raises
  `unsupported format string passed to NoneType.__format__` and kills the
  script AFTER the JSON is written but BEFORE the leaderboard. Fixed 2026-08-08
  in BOTH places (per-symbol print ~line 210 and the leaderboard ~line 234) by
  coercing: `f"{v:+.1f}%" if isinstance(v, (int, float)) else "  n/a"`. If a
  cryptoweekend run dies with a NoneType format error, this is it.
- **Quiet-tape small universe.** On flat/red days few names move ≥2%; the mover
  list shrinks. Report the filter honestly, don't pad it. Re-run after
  volatility returns.
- **NARROW SCAN IS NOT THE UNIVERSE (workflow correction, 2026-08-08).** The
  "all crypto weekend scan" / `scan.py crypto` / `cerebro_crypto_weekend.py`
  path is a **liquid-movers filter** (min $50M vol AND min 2% move) covering
  only ~9 hot names. Answering "anything to DCA / anything oversold?" from it
  alone produced a false "nothing" — the user caught it. When the question is
  universe-scope, run the FULL rescreen: `scripts/crypto_bottom_rescreen_live.py`
  pulls top-500 from CoinGecko, filters to `<=-90% from ATH` (the only
  positive base-rate bucket), keeps liquid survivors, and computes live RSI(14)
  via ccxt to confirm genuine oversold. On 2026-08-08 that surfaced 7 oversold
  deep-from-ATH names (ALGO, IOTA, JTO, ENA + thin KMNO/COMP + death-flag SUN)
  the movers scan never saw.
- **`-100% from ATH` is a death/data flag, not a bargain.** SUN read -100.0%
  from ATH in the 2026-08-08 rescreen — exclude anything at exactly -100% (dead
  or broken ATH data), don't ladder it.
- **Deep-from-ATH can still read SELL under CEREBRO in an EXTREME regime.**
  Gauge was 82.5/100 (EXTREME DANGER) on 2026-08-08 and even quality
  `<=-90%` names (e.g. NEAR) printed SELL. That does NOT invalidate the
  `<=-90%` base-rate thesis — it means LADDER (staged, price-triggered tranches
  fire into weakness) and let time-based tranches defer, never lump-buy into an
  EXTREME gauge. See `references/crypto_dca_ladder_execution.md`.
- **Quiet tape silently drops COMP (Compound).** The universe filter
  (`total_volume >= $50M` AND `|24h%| >= 2%`) drops Compound/COMP on calm days —
  exactly when you'd want it covered for the CLARITY Act DeFi nexus.
  `cerebro_crypto_weekend.py` now merges a `FORCE_COVER` watchlist (COMP, ACT)
  AFTER the filters, so they're always scored. Each result carries
  `forced_coverage` (bool) + `clarity_act_relation` (string); any forced token
  that can't be scanned (no pair / fetch error / too few bars) lands in
  `forced_coverage_skipped` — never silently dropped. Extend `FORCE_COVER` for any
  token you never want to miss. NOTE: ACT (Act I: The AI Prophecy) is covered for
  completeness ONLY — it has NO CLARITY nexus (its relation string says so
  explicitly). Don't mistake its presence for a catalyst.

## Output shape that works for this user
Lead with REGIME (CEREBRO's tape read — e.g. "broadly weak, 0 BUYs"), then the
conviction leaderboard, then the backtest table with GREEN_PROVEN / RED, then an
explicit DO-NOT list (gold tokens, overfit fakes), then artifact paths.

Artifacts (dated `YYYYMMDD`):
- `cerebro_crypto_weekend_<date>.json` — CEREBRO conviction scores
- `cerebro_crypto_universe_<date>.json` — filtered universe
- `cerebro_crypto_backtest_<date>.json` — 10y IS/OOS backtest
- `CRYPTOWEEKEND_<date>.md` — full report

## Support files
- `C:\Users\victo\cerebro_crypto_weekend.py` — universe build + CEREBRO scoring on REAL data (has FORCE_COVER + CLARITY nexus).
- `C:\Users\victo\cerebro_crypto_backtest.py` — 10y IS/OOS backtest with 3-TEST PROOF BAR.
- `references/clarity_act_defi.md` — CLARITY Act (H.R.3633) DeFi/protocol nexus, status, and COMP mapping.
- `scripts/verify_forced_coverage.py` — deterministic probe: stubs CoinGecko, asserts FORCE_COVER tokens survive the filter. No network. Run: `python3 <skill_dir>/scripts/verify_forced_coverage.py`.
- `scripts/crypto_bottom_rescreen_live.py` — **universe-scope rescreen** (added 2026-08-08). Top-500 CoinGecko + live RSI(14) via ccxt; answers "anything oversold worth DCA across the WHOLE universe?" Use when the narrow movers scan under-reports. Run: `python3 <skill_dir>/scripts/crypto_bottom_rescreen_live.py`.
- `references/crypto_scan_runbook.md` — exact run recipe + data-quality flags.
- `references/news-repetition-tracking.md` — "watch the news constantly / does
  anything repeat" class. Theme clustering + NEW/ESCALATING/FADING diff across
  runs, the regex-boundary false positives (drug->rug, US Treasury->bullish),
  and the `BlogwatcherIntegration` interface. Script: `crypto_news_tracker.py`.
- `references/crypto_bottom_research.md` — the OTHER crypto request class:
  "which crypto has bottomed / is most undervalued, backtest a long bull buy".
  CoinGecko universe, yfinance price cross-check, base-quality score that
  separates a bottom from a falling knife, and the measured drawdown-bucket base
  rates (only <=-90% has a positive 24m median).
- `references/crypto_bottom_research_v2.md` — **the current recipe for that
  class.** Top-500 universe, the three exclusion classes, the stable
  squatted-feed list (APT/UNI/POL/SUI), the verdict ladder including the
  permutation gate, re-measured base rates on the de-duplicated pool, and the
  two-layer conclusion rule (`ath_dd<=-90 AND base_score>=50`).
- `references/crypto_dca_ladder_execution.md` — **the follow-on request class.**
  Turning a bottom thesis into an executable tranche ladder: 3 time-based + 2
  price-based tranches, weighting by base score AND MA200 slope, weekly-close
  (never daily) invalidation at the cycle low, and the reminder pattern — a CLI
  session has no message channel, so use a native Windows toast from a
  `no_agent` cron job whose script lives in `~/.hermes/scripts/`.
