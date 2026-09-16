# Gap-Up + Relative-Volume Screener (cross-asset)

Built 2026-08-06 from the request: "gapping up stocks, relative volume, higher
trade volume, any price any market, with our news and all we filter with."

## What it is

`gap_rvol_screener.py` (C:\Users\victo) scans the FULL universal universe for
gap-ups + relative volume + higher-session volume, ANY price, ANY market, then
folds in the blogwatcher RSS news layer (per-symbol alignment + regime-shift
risk) plus RSI/EMA-trend/VWAP context. It reuses
`universal_premarket_scan.ASSET_UNIVERSE` + `CRYPTO_YF_SYMBOLS` and
`blogwatcher_integration.fetch_live_catalysts`, so it tracks universe changes
and honors the standing blogwatcher rule automatically.

## Run

```
python3 gap_rvol_screener.py                          # all 22 groups + news, gap>=1%
python3 gap_rvol_screener.py --classes STOCKS CRYPTO  # alias filter
python3 gap_rvol_screener.py --min-gap 3 --require-news bullish
python3 gap_rvol_screener.py --exclude-bearish-news --top 25
python3 gap_rvol_screener.py --no-news                 # skip blogwatcher
```
Flags: `--min-gap`, `--min-rvol`, `--min-vol-vs-prev`, `--classes`
(STOCKS/CRYPTO/FOREX/COMMODITIES/BONDS/INDICES/FUTURES or raw group keys),
`--require-news` (bullish/bearish/neutral/none/any), `--exclude-bearish-news`,
`--no-news`, `--top`.
Outputs `gap_screener_results_latest.json` + `gap_screener_report.md`.

## KEY TECHNIQUE — intraday provisional volume (reuse for ANY volume-gated daily scan)

yfinance's live daily bar is PARTIAL while the session is open: today's volume
is a fraction of the day's total. Gating RVOL mid-session silently kills every
name (true gaps are only ~1% on a normal open). The gap (open vs prior close) is
FIXED at the open, but the volume "liquidity event" the STOCK SCAN HARD-GATE
describes can only be confirmed at session close.

Pattern (in `evaluate`):
```
in_progress = vols[-1] < 0.4 * vols[-2]          # live bar far below prior day
session_complete = not in_progress
prior = vols[:-1]                                # complete bars only
avg_vol20 = np.mean(prior[-20:]); avg_vol50 = np.mean(prior[-50:])
today_vol = float(vols[-1])                       # live or last complete bar
```
- Gap gate is ALWAYS enforced (gap_up_pct >= floor).
- Volume gates (RVOL floor, vol_vs_prevday) are enforced ONLY when
  `session_complete`. Intraday names are reported with `volume_provisional=True`
  and a `Vol?` column = `partial` in the report.
- Re-run at/after the US close for final, confirmed volume readings.

Without this, the scan returns 0 candidates on a live session and looks broken.

## Blogwatcher news-token mapping (non-equity classes)

`blogwatcher_integration.analyze_sentiment_for_symbols` matches tokens by
SUBSTRING in headline text. For equities/ETFs/small/micro caps the token is the
ticker itself, but indices/commodities/FX need translation dicts so the symbol
resolves to the word that appears in headlines:

```
_INDEX_NEWS = {"^GSPC":"S&P","^IXIC":"NASDAQ","^DJI":"DOW","^RUT":"RUSSELL",
               "^VIX":"VIX","^GDAXI":"DAX","^FCHI":"CAC","^FTSE":"FTSE", ...}
_COMMODITY_NEWS = {"GC=F":"GOLD","SI=F":"SILVER","CL=F":"OIL","BZ=F":"BRENT",
                   "NG=F":"NATURAL GAS","ZW=F":"WHEAT","ZC=F":"CORN", ...}
_FX_NEWS = {"EURUSD=X":"EURO","GBPUSD=X":"STERLING","USDJPY=X":"YEN",
            "USDCHF=X":"FRANC","USDCAD=X":"LOONIE", ...}   # else "DOLLAR"
```
Crypto maps to the bare ticker (`BTC-USD` -> `BTC`). If no headline token maps,
the candidate gets `alignment: NO_NEWS` (sparse coverage for small/micro caps —
NOT a neutral signal). Build the de-duplicated token list, call
`fetch_live_catalysts(top_symbols=...)`, then map results back per candidate.

## PITFALL — class-filter alias matching is case-sensitive and silent

`build_universe()` filters `ASSET_UNIVERSE` by a `--classes` arg. A lowercase
ALIASES value (`{"STOCKS": {"small_cap","micro_cap","etfs"}}`) compared against
`v["category"].upper()` (`"SMALL_CAP"`) yields 0 groups with NO error — the scan
"runs" and reports 0 candidates. Cost many wasted cycles. Fix: uppercase
EVERYTHING on both sides — ALIASES values uppercase, and compare
`k.upper() in wanted or v["category"].upper() in wanted`.

## STOCK SCAN HARD-GATE wiring

Honors `universal_premarket_scan.STOCK_CATEGORIES` / `VOL_RATIO_FLOOR=4.0` /
`GAP_UP_MIN_PCT=1.0`: equities require gap-up >= 1% (always gated) and, at
session close, RVOL >= 4.0x vs 50d avg. No price/market-cap floor. Volume gate
deferred intraday per the technique above.

## Verified run (2026-08-06, live mid-session)

Full universe -> 19 candidates (17 volume-provisional). Gold (GC=F) topped:
gap +1.44%, RVOL 18x, news BULLISH, regime-shift risk HIGH. `--classes STOCKS`
-> 15 equity candidates (hard-gate applied). `--require-news bullish` narrowed
to gold; `--exclude-bearish-news` dropped TOPS (Bitcoin ETF / Western Digital
bearish). `--no-news` ran clean.
