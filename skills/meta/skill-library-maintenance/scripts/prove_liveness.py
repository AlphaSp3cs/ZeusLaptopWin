#!/usr/bin/env python3
"""PROVE-LIVENESS — generic detector for dead scaffolding in a skill library.

Catches the defect class documented in SKILL.md section 1b: a skill ships a
script, the script runs, exits 0, prints nothing, and has NEVER persisted a
row. The SKILL.md describes it as a working data source. Prose-level audits
miss it entirely because the documentation is fine — the code is hollow.

Domain-agnostic. Point it at any skills root. It does not know what the
skills do; it only measures whether they produce evidence of work.

Usage:
    python3 prove_liveness.py                      # audit default skills root
    python3 prove_liveness.py --root ~/.hermes/skills
    python3 prove_liveness.py --run                # execute each first
    python3 prove_liveness.py --json

Exit 0 only when nothing is DEAD.

CAVEAT: without an explicit table map this uses a heuristic — it counts rows
across ALL tables in every bundled .db, ignoring obvious config/schema tables.
That is good enough to separate "never worked" from "works", which is the
question that matters. For a curated per-skill table map (the strongest form
of the check), see the FLEET dict pattern in the signal-provenance-audit skill.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

STALE_AFTER = timedelta(hours=26)

# Tables that fill at init and therefore prove nothing about real work.
IGNORE_TABLES = {"sqlite_sequence", "config", "settings", "schema_version",
                 "migrations", "meta"}


def stub_density(script: Path) -> tuple[int, int]:
    """Return (stub_markers, total_lines). High ratio => scaffolding."""
    try:
        text = script.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return (0, 0)
    lines = text.splitlines()
    markers = sum(
        1 for ln in lines
        if "TODO" in ln or ln.strip() == "pass" or "NotImplementedError" in ln
    )
    return (markers, len(lines))


def db_rows(db: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        tables = [r[0] for r in con.execute(
            "select name from sqlite_master where type='table'")]
        for t in tables:
            if t in IGNORE_TABLES:
                continue
            try:
                out[t] = con.execute(f'select count(*) from "{t}"').fetchone()[0]
            except sqlite3.Error:
                continue
        con.close()
    except sqlite3.Error:
        pass
    return out


def audit_skill(d: Path, run_first: bool) -> dict | None:
    dbs = sorted(d.glob("*.db"))
    scripts = [p for p in d.glob("*.py") if not p.name.startswith("_")]
    if not dbs and not scripts:
        return None  # not a code-bearing skill; nothing to prove

    res: dict = {"skill": d.name, "status": "UNKNOWN", "notes": []}

    if scripts:
        markers, total = stub_density(scripts[0])
        res["stub_markers"] = markers
        if total and markers / max(total, 1) > 0.05:
            res["notes"].append(
                f"{markers} stub markers in {scripts[0].name} — likely unimplemented")

    if run_first and scripts:
        try:
            p = subprocess.run([sys.executable, str(scripts[0])],
                               capture_output=True, text=True, timeout=180, cwd=d)
            if not (p.stdout.strip() or p.stderr.strip()):
                res["notes"].append("SILENT: produced no stdout/stderr at all")
            elif p.returncode != 0:
                res["notes"].append(f"exit {p.returncode}: {p.stderr.strip()[:160]}")
        except subprocess.TimeoutExpired:
            res["notes"].append("TIMEOUT after 180s")
        except OSError as e:
            res["notes"].append(f"could not execute: {e}")

    if not dbs:
        res["status"] = "NO-DB"
        res["notes"].append("no database — cannot prove it persists anything")
        return res

    rows: dict[str, int] = {}
    for db in dbs:
        for t, n in db_rows(db).items():
            rows[t] = rows.get(t, 0) + n
    res["rows"] = rows
    total_rows = sum(rows.values())
    res["total_rows"] = total_rows

    if total_rows == 0:
        res["status"] = "DEAD"
        res["notes"].append("every table empty — scaffolding, not a data source")
        return res

    newest = max(datetime.fromtimestamp(db.stat().st_mtime, tz=timezone.utc)
                 for db in dbs)
    age = datetime.now(timezone.utc) - newest
    res["db_age_hours"] = round(age.total_seconds() / 3600, 1)
    res["status"] = "STALE" if age > STALE_AFTER else "LIVE"
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path.home() / ".hermes" / "skills"))
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    root = Path(a.root).expanduser()
    if not root.is_dir():
        print(f"skills root not found: {root}", file=sys.stderr)
        return 2

    results = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        r = audit_skill(d, a.run)
        if r:
            results.append(r)

    if a.json:
        print(json.dumps({"generated": datetime.now(timezone.utc).isoformat(),
                          "root": str(root), "results": results}, indent=2))
        return 0 if not any(r["status"] == "DEAD" for r in results) else 1

    order = {"DEAD": 0, "NO-DB": 1, "STALE": 2, "LIVE": 3}
    interesting = [r for r in results if r["status"] != "LIVE"]
    print(f"{'STATUS':8} {'SKILL':38} ROWS")
    print("-" * 78)
    for r in sorted(interesting, key=lambda r: order.get(r["status"], 9)):
        print(f"{r['status']:8} {r['skill']:38} {r.get('total_rows', '-')}")
        for n in r["notes"]:
            print(f"{'':8} └─ {n}")
    live = sum(r["status"] == "LIVE" for r in results)
    print("-" * 78)
    print(f"{live}/{len(results)} code-bearing skills LIVE "
          f"({len(interesting)} need attention)")
    if interesting:
        print("\nA DEAD source is SILENT. Its silence is 'no data', never "
              "'no signal'. Do not count it as a passed check.")
    return 0 if not any(r["status"] == "DEAD" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
