# CEREBRO cryptoweekend runbook

## One-shot run
```bash
cd /c/Users/victo
python3 cerebro_crypto_weekend.py      # CoinGecko universe + CEREBRO 1h conviction -> cerebro_crypto_weekend_<date>.json
python3 cerebro_crypto_backtest.py     # 10y daily yfinance IS/OOS -> cerebro_crypto_backtest_<date>.json
```
Scripts live at `C:\Users\victo\cerebro_crypto_weekend.py` and
`C:\Users\victo\cerebro_crypto_backtest.py` (copies also in this skill's
`scripts/`). They write dated artifacts to the home dir.

## Dependencies
`ccxt yfinance pandas numpy` (all present on this host's Python 3.13 as of 2026-08).
If `import ccxt` fails: `pip install ccxt yfinance pandas numpy`.

## Data-quality flags to report honestly
- **No Binance pair** (SKYAI, LIT, CYS): skipped — would force CEREBRO mock data.
- **Gold tokens** (XAUT/PAXG): pass liquidity filter + can backtest GREEN, but the
  edge is gold mean-reversion, NOT crypto momentum. Exclude from crypto plan.
- **Overfit fakes**: huge OOS PF with negative in-sample (BONK 2.42 IS / 0.39 OOS;
  ENA 0.61 IS / 2.9 OOS). Rejected by the 3-TEST PROOF BAR (IS>=1 AND OOS>=1 same side).
- **Quiet tape**: flat/red days yield few movers (only 14/250 moved >=2% on 2026-08-07).
  Universe is small because the market is quiet — say so, don't pad.

## Known CEREBRO quirks (do NOT call sc.scan())
`cerebro_scan.CerebroScanner.fetch_crypto_data/fetch_stock_data` swallow ALL
exceptions and return a seeded random walk (`np.random.seed(42)`). The fix used
here: fetch OHLCV yourself via `ccxt.binance().fetch_ohlcv(pair, '1h', 100)`,
inject `sc.df = df`, then call `calculate_rsi/macd/bollinger_bands/
volume_confirmation` + `determine_signal()`. Confirm the printed price is real
(live Binance) before trusting any score.

## Binance pair format
CEREBRO's crypto branch triggers on `'/' in symbol and not symbol.endswith('USD')`.
Pass `BTC/USDT` (NOT `BTC/USD`). CoinGecko base tickers (BTC, ETH, XRP) -> append `/USDT`.
