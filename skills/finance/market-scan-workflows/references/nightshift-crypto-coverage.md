# Nightshift Crypto Coverage — dual-path recipe & silent-drop check

Nightshift crypto is served by TWO independent paths. Running only the main scan
under-covers crypto. Run both.

## The two paths
1. **Main nightshift scan** — `nightshift_scan.py` → `_scan_crypto_yf()` inside
   `nightshift_report.py`. Covers ~13 coins (BTC, ETH, BNB, SOL, XRP, ADA, DOGE,
   AVAX, LINK, DOT, LTC, TRX, ATOM). Written to `nightshift_scan_results_latest.json`
   → `categories.CRYPTO`.
2. **Crypto leg** — `nightshift_crypto_leg.py`, a SEPARATE scan+gate over ~30 yfinance
   `-USD` symbols (adds BCH, UNI, NEAR, ICP, ETC, XLM, FIL, HBAR, VET, INJ, SUI,
   AAVE, RUNE, ALGO, XMR). Feeds the SAME `enhanced_trade_gate.process_all_setups`
   so GO/NO-GO verdicts, sizing and R:R match the other nightshift setups. Writes
   NAMESPACED `nightshift_crypto_scan_latest.json`, `nightshift_crypto_swing_latest.json`,
   `nightshift_crypto_day_latest.json` (never touches the main scan's files).

## Invocation order
```
cd <home> && python3 nightshift_report.py            # main scan + gate + blogwatcher + report
cd <home> && python3 nightshift_crypto_leg.py        # wider crypto gate, namespaced
```

## Silent-drop verification (run after both)
A low/zero crypto count is the highest-risk "success-looking" state. Cross-check:
```python
import json
main = json.load(open('nightshift_scan_results_latest.json'))['categories']['CRYPTO']['assets']
leg  = json.load(open('nightshift_crypto_scan_latest.json'))['categories']['CRYPTO']['assets']
mbtc = next(x for x in main if x['symbol']=='BTC')
lbtc = next((x for x in leg if x.get('symbol')=='BTC'), None)
print('main BTC vol', mbtc.get('volume'), '| leg BTC vol', (lbtc or {}).get('volume'))
for grp,name in ((main,'main'),(leg,'leg')):
    flat=[x['symbol'] for x in grp if x.get('volume',0)==0 and x.get('volume_ratio',1)==1.0]
    print(name,'zero-vol/flat coins:', flat or 'none')
```
Pass criteria:
- BTC volume is a REAL number in BOTH paths (e.g. ~21.6B), not 0.0.
- No coin has `volume==0 AND volume_ratio==1.0` (that flat pair = the silent-drop tell).
- Both symbol lists are non-empty.

If the main scan shows BTC volume 0.0 but the leg shows ~21.6B, the main scan's
crypto fetch broke — re-run `nightshift_report.py`, do NOT report a crypto-less
nightshift as a quiet market. Verified clean on 2026-08-07: main 13 coins / leg 28
coins, BTC 21.6B both, zero flat coins.
