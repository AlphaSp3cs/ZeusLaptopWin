WORKFLOW MANUAL: C:\Users\victo\Desktop\HERMES_TRADING_OPERATING_MANUAL.md — single source of truth. Scan router `python3 ~/scan.py <mode>`, bt engine `~/bt/bt_store.py`+`bt_runner.py`, `~/sentinel_audit.py`, all standing rules. Code masters on C:.
§
UNIVERSAL RULE: NO auto/cron/scheduled runs — only on explicit ask. Broker creds: C:\Users\victo\Desktop\allapi2026.txt (FTMO, Coinbase, Binance, Kraken, Hyperliquid, Polymarket, Alpaca, eToro, Capital.com, Kalshi). NEVER print secrets.
§
User trades FTMO/Kraken/Binance. FX+metals+ENERGY same sheet. Casual, brutal honesty. DRIP: PEP/KO/SCHD/VYM/O. Chases 100x.
§
FX+METALS setups BROAD: include ENERGY (Brent/WTI/NatGas) same sheet. VERIFY geopolitical supply-shock claims vs LIVE price. On 'explain in English'/'why': 1-sentence bottom line first, no jargon.
§
DCA LADDER: ALWAYS run `python3 "C:/Users/victo/AppData/Local/hermes/scripts/dca_ladder_cron.py"` (wrapper refreshes tape THEN checks). Standalone check = stale + 36h gate blocks all buys. Covered: PEP/KO/SCHD/VYM/O. ON-DEMAND RECHECK: `python3 ~/scan.py recheck`, report only DELTAS.
§
ON-DEMAND RE-CHECK (standing): on 'check'/'scan again', run `python3 ~/scan.py recheck`, report only DELTAS. User chases 100x but accepts base-rate pushback when shown data.
§
WireGuard VPN bravo: kjbnet.ddns.net:51820, client 10.1.0.3/24, remote 10.0.188.0/24. Cell phone + Omarchy.
§
AUTONEOUS EXECUTION LAW: When user asks to work, execute pipeline WITHOUT waiting: 1) News (fetch_news_direct.py), 2) Market scan ALL sectors (download_comprehensive_universe.py + scan_comprehensive_setups.py — NEVER small watchlist), 3) Backtest (backtest_priority.py), 4) Report. Save to C:\Hermes\workflow\data\. CRITICAL: User was frustrated when scan only showed ETFs — ALWAYS use comprehensive universe (1200+ assets from yfinance/binance/coingecko) so ALL sectors appear.
§
ZeusNews: news_tape.db (1,203 articles, tradability_score, sentiment, symbols), sector_scan (15 sectors w/ tradable_setups JSON), freya_signals, backtest_v2 (7-rule crypto), atr (ATR expansion), forex_backtest (8 strat x 5 horizon x 16 pairs). 13F Buffett: 138 articles. 60 sources, 12 news live. ~/ZeusNews/.