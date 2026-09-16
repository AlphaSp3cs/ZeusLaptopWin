---
name: news-high-volume-trade-protocol
description: Use for news-driven intraday entries and exits.
category: finance
---

# News High-Volume Trade Protocol

## When to use
- Any news-driven intraday entry (stock, ETF, crypto, FX, future).
- Any market scan that surfaces a symbol with a fresh catalyst.
- Whenever the user asks "should I take this news trade".

Does NOT apply to the long-horizon dividend accumulation plan
(`C:\Users\victo\Desktop\buy_plan_tomorrow.md` buy priority table).

## Entry rule
1. Identify the news print time (ET) and its sentiment via blogwatcher RSS.
   Blogwatcher covers BTC/ETH/SOL only — for anything else state
   explicitly: "per-symbol sentiment layer unavailable".
2. Wait for the FIRST COMPLETED candle after the news.
3. Confirm that candle's volume is the HIGHEST of the session so far.
4. Confirm volume >= 30,000,000 shares/units. Below floor -> NO TRADE.
   EXCEPTION — FX: spot '=X' reports 0 volume on yfinance, and CME currency
   futures report CONTRACTS (thousands), so the absolute floor is meaningless
   for FX. FX instead uses a RELATIVE test: its CME futures proxy
   (FX_FUTURES_PROXY, e.g. EURUSD->6E=F, USDJPY->6J=F) must show
   >= RELATIVE_VOL_FLOOR (1.5x) its own 20d average. No proxy available =
   blocked with an explicit reason, never silently passed.
5. Equities additionally still face the standing STOCK hard-gate:
   >= 4x relative volume vs 50d average AND longs must gap up
   (open > prior close).
6. Enter at the CLOSE of that trigger candle. Record `trigger_low`.

## Exit rules (first to fire wins)
1. Structure stop: next candle closes below `trigger_low`
   -> exit at the OPEN of the following candle.
2. Profit protection: at +1.5 x ATR(14) from entry, move stop to breakeven.
3. Time exit: no stop/target by session end -> exit on last 5-minute close.
4. News fade: contradicting catalyst in the same session -> exit at market.

Mirror all rules for SHORTs (trigger_high, closes above, -1.5 x ATR).

## Deploy ordering
Standing rule applies: CONVICTION setups (news sentiment agrees with
direction — LONG+BULLISH / SHORT+BEARISH) deploy FIRST, always, ahead of
non-conviction. CONFLICT setups rank last. Under an extreme danger-zone
gauge, still conviction-first but inside gate size limits.

## Logging (mandatory)
Append every trade to
`C:\Users\victo\Desktop\compound_project\news_trade_log.json`
conforming to `news_trade_log.schema.json` in the same folder. Seed a new
log by copying `news_trade_log_template.json`. No log entry = the trade
does not exist for review.

Required at minimum: id, symbol, asset_class, direction, news_time_et,
trigger_candle (with is_session_high_volume), entry, trigger_low, atr14,
volume_floor_ok.

## Automation (already wired — do not re-implement)
Shared module: `C:\Users\victo\news_protocol.py`. Imported by:
- `cron_allsector_open_scan.py` -> protocol section in ALLSECTOR_OPEN_*.md
- `nightshift_report.py`        -> protocol section in NIGHTSHIFT_SCAN_*.md
- `run_universal_workflow.py`   -> writes `news_protocol_latest.json`
- `gap_rvol_screener.py`        -> appends section to gap_screener_report.md
- `sector_scan_comprehensive.py`-> writes sector_scan_news_protocol.md

Flat-list screeners (gap_rvol, sector_scan_*) go through
`adapt_flat_candidates(rows)` + `news_hits_from_flat(rows)` first, which
also reconciles `vol_ratio_50d` -> `vol_ratio_50`.

All three call `npx.apply_protocol(scan, news_hits, source)` (or
`scan_for_protocol_candidates` + `log_candidates`), which auto-appends
qualified candidates to `Desktop/compound_project/news_trade_log.json`.
Every step is exception-wrapped so a protocol failure can never break a scan.

Key API:
- `conviction_of(side, news) -> (CONVICTION|CONFLICT|NONE, weight)`
- `rank_conviction_first(trades, news_lookup=...)`
- `evaluate_candidate(asset, side, news, asset_class) -> verdict dict`
- `scan_for_protocol_candidates(scan, news_hits)` (CONFLICT sides suppressed)
- `apply_protocol(scan, news_hits, source) -> (markdown_lines, candidates)`

## Integration checklist (run every scan)
- [ ] Danger-zone gauge read: `.hermes/gauges/danger_zone/latest_gauge.json`
- [ ] Gate run via `run_universal_workflow.py --gate-only`
      (refuses on >90-min staleness)
- [ ] Blogwatcher sentiment attached, or unavailability stated
- [ ] Protocol section present in `Desktop/buy_plan_tomorrow.md`
- [ ] Trades logged to news_trade_log.json

## Pitfalls
- "Highest volume of the day" means highest SO FAR in the session, not
  highest in hindsight — evaluate at trigger time only.
- FX via yfinance reports volume 0 ('=X'); the 30M floor cannot be
  satisfied, so FX news trades need an explicit volume-proxy note or are
  skipped under this protocol.
- Never re-enter the same catalyst after a news-fade exit.
- Breakeven is a one-way ratchet; do not widen it back out.
- Daily scan payloads have NO intraday candle low, so `trigger_low` is an
  ATR-derived proxy flagged with `trigger_low_is_proxy`/`*`. Read the real
  trigger low off the actual post-news candle before executing.
- CONFLICT sides are suppressed from candidates by design — the protocol
  follows catalysts, so the news-opposing direction is a non-trade.
  NONE/NEUTRAL news is also suppressed: no direction means no trade, and
  emitting both sides would be a self-contradicting signal pair.
- SYMBOL KEY DRIFT is the highest-severity trap: scans use market tickers
  ('BTC-USD', 'GC=F') while blogwatcher keys news by bare symbol ('BTC').
  Always look news up via `news_for()` / `normalize_symbol()`, never a raw
  dict.get() — a raw lookup silently yields zero candidates forever.
- blogwatcher `headlines` entries are DICTS ({'headline','source',...}),
  not strings. Use `_first_headline()`.
- Logging is signature-deduped on (day, NORMALISED symbol, side). Normalise
  matters: nightshift emits 'BTC' and the daytime scan emits 'BTC-USD' for
  the same asset, so a raw-symbol key logs the identical signal twice per
  day. Entry price is deliberately NOT part of the key — it drifts a few
  dollars between runs and would defeat the dedupe.
- Verify files actually exist before reporting them as created.

## Data-integrity fixes applied to the scan layer (do not regress)
- `universal_premarket_scan.calculate_ema` returned `prices[-1]` when data
  was insufficient, so with a 3mo (~68 bar) fetch `ema200 == price` for
  EVERY asset and all trend tests were meaningless. Fetches are now
  `period="1y"` (~261 bars) in universal_premarket_scan.py (lines ~909,
  934) and nightshift_scan.py (lines ~78, 237). `calculate_ema(...,
  strict=True)` returns None instead of faking a value.
- `nightshift_scan._scan_crypto_yf` hardcoded `volume: 0.0` and
  `volume_ratio: 1.0`, silently disabling every overnight volume gate
  including the 30M floor. Now extracts real High/Low/Volume frames.
- Same function referenced an undefined `ema200`, raising NameError inside
  the per-coin try/except and silently skipping EVERY coin's
  qualification. Guarded with `is not None`.
- Non-crypto assets use keys `vol_ratio` / `vol_ratio_50`; crypto uses
  `volume_ratio`. Check the right key before concluding data is missing.
