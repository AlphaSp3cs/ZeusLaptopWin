#!/usr/bin/env python3
"""Re-order nightshift gate GO verdicts by asset class, not by profile.

nightshift_report.py renders setups grouped by *profile* (swing then day).
The user's standing preference is the opposite: lead with
    commodities / metals -> forex -> indices -> crypto
(the order they name the universe), NOT by profile.

This script reads the namespaced nightshift gate outputs
(nightshift_setups_day_latest.json / nightshift_setups_swing_latest.json)
from the home dir and prints the GO rows sorted by asset-class priority, then
any NO-GO / WATCH reasons. Wired to the user's home dir (expanduser("~")).

Usage:
    python3 reorder_gate_by_class.py                 # both profiles, day first
    python3 reorder_gate_by_class.py --profile day
    python3 reorder_gate_by_class.py --profile swing
"""
import json
import os
import argparse

BASE = os.path.expanduser("~")
ORDER = ["commodities", "forex", "indices", "crypto"]
RANK = {c: i for i, c in enumerate(ORDER)}


def load(p):
    with open(os.path.join(BASE, p)) as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["swing", "day", "both"], default="both")
    args = ap.parse_args()
    profiles = ["day", "swing"] if args.profile == "both" else [args.profile]

    for prof in profiles:
        data = load(f"nightshift_setups_{prof}_latest.json")
        s = data["summary"]
        print(f"\n===== {prof.upper()} PROFILE — "
              f"LONGs GO={s['go_longs']}/{s['total_longs']}  "
              f"SHORTs GO={s['go_shorts']}/{s['total_shorts']} "
              f"WATCH={s['watch_longs']+s['watch_shorts']} =====")

        gos = [t for t in data["longs"] + data["shorts"]
               if t["validation"]["verdict"] == "GO"]
        gos.sort(key=lambda t: (RANK.get(t["category"], 9), t["side"]))
        for t in gos:
            m = t["validation"]["metrics"]
            entry = m.get("real_entry") or t.get("entry_price")
            sl = t.get("stop_loss")
            t1 = m.get("real_t1") or t.get("take_profit_1")
            print(f"  {t['side']:5} {t['symbol']:10} {t['category']:11} "
                  f"{t['name']:20} entry={entry:<11} sl={sl:<11} t1={t1:<11} "
                  f"RR={m.get('rr')} size={m.get('notional_pct')}% "
                  f"risk={m.get('pct_risk')}% rsi={t.get('rsi')} "
                  f"vwap%={t.get('vwap_distance_pct')}")

        for v in data["validations"].get("NO-GO", []):
            print(f"  NO-GO {v['side']:5} {v['symbol']:10} {v['reason']}")
        for v in data["validations"].get("WATCH", []):
            print(f"  WATCH {v['side']:5} {v['symbol']:10} {v['reason']}")


if __name__ == "__main__":
    main()
