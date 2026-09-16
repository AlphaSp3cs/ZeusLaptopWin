#!/usr/bin/env python3
"""
verify_scan_memory.py — confirm the standing "remember last scan" memory layer
actually attached last-scan deltas to populated assets.

Run AFTER a scan (or after the full cron_allsector_open_scan.py pipeline) to
prove the memory layer worked — i.e. that universal_scan_results_latest.json
carries last_scan + *_chg_since_last on the assets, and that the persisted
snapshot file exists and round-trips.

Usage:
    python3 verify_scan_memory.py
    python3 verify_scan_memory.py --scan-file universal_scan_results_latest.json
    python3 verify_scan_memory.py --snapshot universal_scan_last_snapshot.json

Exit code 0 = memory present and consistent; 1 = something is stale/broken.
This is a diagnostic probe, not a phase of the pipeline.
"""
import json
import os
import sys

HOME = os.path.expanduser("~")


def load(path):
    with open(path) as f:
        return json.load(f)


def main():
    scan_file = sys.argv[sys.argv.index("--scan-file") + 1] if "--scan-file" in sys.argv else \
        os.path.join(HOME, "universal_scan_results_latest.json")
    snap_file = sys.argv[sys.argv.index("--snapshot") + 1] if "--snapshot" in sys.argv else \
        os.path.join(HOME, "universal_scan_last_snapshot.json")

    problems = []

    # 1) Snapshot exists and has symbols
    if not os.path.exists(snap_file):
        problems.append(f"snapshot missing: {snap_file}")
        snap_syms = 0
    else:
        snap = load(snap_file)
        snap_syms = len(snap.get("symbols", {}))
        print(f"[snapshot] {snap_file}")
        print(f"  symbols: {snap_syms}  scan_ts: {snap.get('scan_timestamp', '?')[:19]}")

    # 2) Scan latest.json exists and assets carry last_scan
    if not os.path.exists(scan_file):
        problems.append(f"scan file missing: {scan_file}")
        return 1

    d = load(scan_file)
    total = 0
    attached = 0
    with_delta = 0
    is_new = 0
    ex = None
    for cat in d.get("categories", {}).values():
        for a in cat.get("assets", []):
            total += 1
            ls = a.get("last_scan")
            if ls is not None:
                attached += 1
                if ex is None:
                    ex = a
            if a.get("price_chg_pct_since_last") is not None:
                with_delta += 1
            if a.get("is_new_since_last"):
                is_new += 1

    print(f"[scan] {scan_file}")
    print(f"  scan_ts: {d.get('scan_timestamp', '?')[:19]}")
    print(f"  assets: {total}")
    print(f"  with last_scan attached: {attached}")
    print(f"  with numeric price_chg_pct_since_last: {with_delta}")
    print(f"  flagged is_new_since_last: {is_new}")

    if attached == 0:
        problems.append("0 assets have last_scan attached — memory layer did NOT run "
                        "(stale latest.json or snapshot not loaded)")
    if snap_syms and attached and (abs(attached - total) > max(5, 0.1 * total)):
        problems.append(f"attached {attached} vs total {total} — many symbols lacked a "
                        f"prior reading despite snapshot having {snap_syms}")

    # 3) Show one concrete example with real deltas
    if ex:
        print("\n[example]")
        print(f"  {ex['symbol']:10} class={ex['category']}")
        print(f"    now ${ex.get('price')}  last ${ex['last_scan'].get('price')}")
        print(f"    chg% {ex.get('price_chg_pct_since_last')}  rsi {ex.get('rsi')} "
              f"(was {ex['last_scan'].get('rsi')})")
        print(f"    vwap_dist {ex.get('vwap_distance_pct')} (was {ex['last_scan'].get('vwap_distance_pct')})")

    print()
    if problems:
        print("FAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK — last-scan memory layer verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
