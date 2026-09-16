#!/usr/bin/env python3
"""
NIGHTSHIFT CRYPTO LEG — separate, gate-consistent crypto scan.

Re-runs ONLY the crypto universe (yfinance '-USD', the same path the nightshift
scan uses) through scan_asset_class(), then feeds the qualified trades to the
SAME enhanced_trade_gate.process_all_setups so GO/NO-GO verdicts, sizing and R:R
match the commodities/forex/indices nightshift setups.

Writes NAMESPACED files (nightshift_crypto_*) so it NEVER touches the nightshift
scan's nightshift_setups_* or universal_scan_results_* files.
"""
import os, sys, json
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import universal_premarket_scan as ups  # noqa: E402
import enhanced_trade_gate as gate      # noqa: E402

NS_SWING = "nightshift_crypto_swing_latest.json"
NS_DAY = "nightshift_crypto_day_latest.json"


def run_crypto_scan():
    print(">>> CRYPTO LEG: fetching", len(ups.CRYPTO_YF_SYMBOLS), "yfinance -USD symbols ...")
    crypto_df = ups.fetch_yfinance_batch(ups.CRYPTO_YF_SYMBOLS, period="3mo", interval="1d")
    crypto_cat = {
        "symbols": ups.CRYPTO_YF_SYMBOLS,
        "names": [s.replace("-USD", "").replace("7083", "").replace("20947", "")
                  for s in ups.CRYPTO_YF_SYMBOLS],
        "category": "crypto",
    }
    res = ups.scan_asset_class("CRYPTO", crypto_cat, crypto_df)
    print(f"  Assets scanned: {len(res['assets'])} | "
          f"Qualified LONGs: {len(res['qualified_longs'])} | "
          f"Qualified SHORTs: {len(res['qualified_shorts'])}")
    scan_data = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "scan_mode": "nightshift_crypto_leg",
        "scan_source": "universal_premarket_scan.scan_asset_class(CRYPTO)",
        "categories": {"CRYPTO": res},
        "qualified_longs": res["qualified_longs"],
        "qualified_shorts": res["qualified_shorts"],
        "total_assets_scanned": len(res["assets"]),
    }
    # scan_asset_class returns numpy types; the main scanner runs this before
    # any json.dump. Apply it here too so the payload is JSON-safe.
    return ups.convert_to_serializable(scan_data)


def run_gate(scan_data):
    print("\n>>> CRYPTO LEG: ENHANCED TRADE GATE")
    out = {}
    for profile_type in ("swing", "day"):
        r = gate.process_all_setups(scan_data, profile_type, account_equity=100000)
        s = r["summary"]
        output = {
            "profile": profile_type,
            "account_equity": 100000,
            "scan_timestamp": scan_data.get("scan_timestamp"),
            "scan_mode": "nightshift_crypto_leg",
            "summary": s,
            "validations": r["validations"],
            "longs": [gate.setup_to_dict(x) for x in r["setups"]["longs"]],
            "shorts": [gate.setup_to_dict(x) for x in r["setups"]["shorts"]],
        }
        fname = NS_SWING if profile_type == "swing" else NS_DAY
        with open(os.path.join(HERE, fname), "w") as f:
            json.dump(output, f, indent=2)
        out[profile_type] = output
        print(f"  [{profile_type.upper()}] wrote {fname} | "
              f"LONGs GO={s['go_longs']}/{s['total_longs']} | "
              f"SHORTs GO={s['go_shorts']}/{s['total_shorts']}")
    return out


def main():
    scan_data = run_crypto_scan()
    with open(os.path.join(HERE, "nightshift_crypto_scan_latest.json"), "w") as f:
        json.dump(scan_data, f, indent=2)
    run_gate(scan_data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
