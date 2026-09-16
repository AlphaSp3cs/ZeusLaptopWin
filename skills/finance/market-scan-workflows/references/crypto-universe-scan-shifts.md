# Crypto Universe & Scan-Shift Coverage (condensed knowledge bank)

Source of truth: `C:\Users\victo\crypto_universe.py` (import `CRYPTO_YF_SYMBOLS`,
`current_session`, `crypto_session_coverage`). Both `nightshift_scan` and
`universal_premarket_scan` draw from it — edit that one file to change coverage.

## Why this exists
The legacy crypto path was a hard-coded 15-coin list (nightshift) and a list
with delisted/mangled tickers (`UNI7083-USD`, `SUI20947-USD`, `MATIC-USD`) on
the universal side. Those silently collapsed coverage and the mangled tickers
returned no data. As of 2026-08-07 the universe is validated and unified at 43.

## Validated 43-coin yfinance `-USD` universe (real bars confirmed 2026-08-07)
BTC, ETH, BNB, SOL, XRP, DOGE, ADA, AVAX, TRX, LINK, DOT, LTC, BCH, NEAR, ICP,
ETC, XLM, ATOM, FIL, HBAR, VET, INJ, AAVE, RUNE, ALGO, XMR, EGLD, THETA, AXS,
SAND, MANA, CRV, MKR, AR, OP, TIA, SEI, WIF, FLOKI, DYDX, KAVA, ZEC, DASH.

## Delisted / renamed on yfinance — DO NOT add (silently shrinks coverage)
- `UNI-USD` (Uniswap — not carried on yfinance `-USD`)
- `MATIC-USD` -> renamed to POL (Polygon)
- `SUI-USD`, `APT-USD` (Sui / Aptos — no yfinance `-USD` series)
- `RNDR-USD` -> renamed to RENDER
- `GRT-USD` (The Graph), `STX-USD` (Stacks), `PEPE-USD`, `IMX-USD` (Immutable X),
  `FTM-USD` -> renamed to SONIC
- Legacy-mangled: `UNI7083-USD`, `SUI20947-USD`

## Session ("shift") map — crypto populates in ALL four (trades 24/7)
| Session   | UTC window | Notes |
|-----------|------------|-------|
| ASIA      | 00:00-07:00| Tokyo / Sydney / Hong Kong |
| LONDON    | 07:00-13:00| London / Zurich / Frankfurt |
| NEW_YORK  | 13:00-21:00| US cash + futures session |
| OVERNIGHT | 21:00-24:00| US evening; FX + crypto + metals trade |

`current_session(utc_dt)` -> primary session. `crypto_session_coverage()` -> all 4.
Both reports now print "crypto populates in: ASIA, LONDON, NEW_YORK, OVERNIGHT".

## ET <-> UTC cron mapping (user is US-Eastern; EDT = UTC-4 in summer, EST = UTC-5 winter)
The session map is in UTC. Convert before picking the cron minute/hour. A job
created at 20:37 UTC fires at 16:37 EDT = NEW_YORK session, NOT Asia.

| Session   | ET local | Summer UTC cron (`37 m * * *`) | Winter UTC cron |
|-----------|----------|-------------------------------|-----------------|
| Asia open | 20:37 ET | `37 20 * * *`                 | `37 21 * * *` |
| London    | 05:37 ET | `37 09 * * *`                 | `37 10 * * *` |
| NY premarket | 09:37 ET | `37 13 * * *`              | `37 14 * * *` |
| Overnight | 18:37 ET | `37 22 * * *`                 | `37 23 * * *` |

**Rule:** after creating any TZ-bound cron job, re-read its `next_run_at` and
confirm the local hour falls inside the intended session. This session initially
mis-set two jobs (14:37 UTC labeled "London" but was NY; 02:37 UTC labeled "Asia"
but was overnight) and had to retime them — verify, don't assume.

## Smoke test after any universe edit
```bash
python3 -c "import nightshift_scan as ns; print(len(ns._scan_crypto_yf()['assets']))"
```
Must print **43**. (Verified 2026-08-07: 43 assets, 6 longs + 7 shorts, ~2.3s.)

## Use yfinance `-USD`, not CoinGecko
CoinGecko's per-coin path 429-rate-limits and its OHLC loop is slow. yfinance
batches the whole list in one call and returns real volume. Do NOT revert to the
old 15/13-coin hard-coded lists or the CoinGecko path.
