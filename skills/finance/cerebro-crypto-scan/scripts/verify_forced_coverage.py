#!/usr/bin/env python3
"""Verify FORCE_COVER tokens survive cerebro_crypto_weekend.build_universe().

Stubs ONLY the CoinGecko network call; exercises the REAL forced-merge logic so
we can assert COMP/ACT are injected even when few names move. No network,
no Binance. Mirrors the quiet-tape scenario that previously dropped COMP.

Run:  python3 C:\Users\victo\AppData\Local\hermes\skills\finance\cerebro-crypto-scan\scripts\verify_forced_coverage.py
"""
import importlib.util
from pathlib import Path

SPEC = Path(r"C:\Users\victo\cerebro_crypto_weekend.py")
spec = importlib.util.spec_from_file_location("ccw", SPEC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# Quiet tape: BTC/ETH move >=2% (pass filter) but few others do.
m.coingecko_top = lambda per_page=250: [
    {"symbol": "btc", "name": "Bitcoin", "id": "bitcoin", "current_price": 60000,
     "market_cap": 1e12, "total_volume": 5e10,
     "price_change_percentage_24h_in_currency": 3.1,
     "price_change_percentage_7d_in_currency": 1.0},
    {"symbol": "eth", "name": "Ethereum", "id": "ethereum", "current_price": 3000,
     "market_cap": 3e11, "total_volume": 2e10,
     "price_change_percentage_24h_in_currency": -2.5,
     "price_change_percentage_7d_in_currency": -1.0},
]

u = m.build_universe()
syms = [r["symbol"] for r in u]
assert "COMP" in syms and "ACT" in syms, f"forced tokens missing from universe: {syms}"
comp = next(r for r in u if r["symbol"] == "COMP")
assert comp.get("forced") is True, "COMP should be flagged forced_coverage"
assert m.clarity_relation("COMP").startswith("Compound"), "COMP CLARITY note missing"
assert m.clarity_relation("ACT").startswith("Act I"), "ACT CLARITY note missing"
assert m.clarity_relation("BTC") == "", "non-watchlist token must have empty relation"
print("FORCED_COVERAGE_OK ->", syms)
