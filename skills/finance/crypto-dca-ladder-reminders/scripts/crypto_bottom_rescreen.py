"""Monthly crypto bottom re-screen.

Re-runs the top-500 universe + base-quality screen, DIFFS against the previous
snapshot, and reports only what CHANGED:
  - new names entering the <=-90% bucket
  - names whose base score crossed the >=50 "has a base" threshold
  - existing ladder names whose score degraded
  - names that fell out

Archives the prior snapshot first and ROLLS BACK if the fetch looks broken.

Run:  python3 crypto_bottom_rescreen.py
"""
import json, pathlib, shutil, subprocess, sys
from datetime import datetime, timezone

HOME = pathlib.Path.home()
ARCH = HOME / ".hermes" / "crypto_bottom_history"
UNI = HOME / "crypto_bottom_universe_v2.json"
BQ = HOME / "crypto_base_quality_v2.json"
PREV = ARCH / "prev_base_quality.json"
LADDER_SYMS = ["NEAR", "INJ"]
MIN_CANDIDATES = 5          # sanity floor; below this we assume a broken fetch


def toast(title, msg):
    ps = ('[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications,'
          ' ContentType=WindowsRuntime] > $null;'
          '$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(1);'
          f'$t.GetElementsByTagName("text").Item(0).AppendChild($t.CreateTextNode("{title}")) > $null;'
          f'$t.GetElementsByTagName("text").Item(1).AppendChild($t.CreateTextNode("{msg}")) > $null;'
          '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier'
          '("Hermes DCA").Show([Windows.UI.Notifications.ToastNotification]::new($t))')
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=25)
    except Exception:
        pass


def run(script):
    r = subprocess.run([sys.executable, str(HOME / script)],
                       capture_output=True, text=True, timeout=1800, cwd=str(HOME))
    return r.returncode == 0, (r.stdout or "") + (r.stderr or "")


def main():
    ARCH.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")

    # snapshot previous state for the diff
    prev = None
    if BQ.exists():
        prev = json.loads(BQ.read_text())
        shutil.copy(BQ, ARCH / f"base_quality_{stamp}_pre.json")
    bak_uni = ARCH / "rollback_universe.json"
    bak_bq = ARCH / "rollback_bq.json"
    if UNI.exists(): shutil.copy(UNI, bak_uni)
    if BQ.exists(): shutil.copy(BQ, bak_bq)

    print(f"RE-SCREEN {stamp} — rebuilding universe (top 500)...")
    ok, out = run("crypto_bottom_universe_v2.py")
    if not ok:
        print("universe script FAILED:\n" + out[-1500:])
        return
    try:
        u = json.loads(UNI.read_text())
    except Exception as e:
        print(f"universe json unreadable: {e}")
        return
    if u.get("n_candidates", 0) < MIN_CANDIDATES:
        print(f"!! only {u.get('n_candidates')} candidates (<{MIN_CANDIDATES}) "
              f"— assuming broken fetch, ROLLING BACK")
        if bak_uni.exists(): shutil.copy(bak_uni, UNI)
        if bak_bq.exists(): shutil.copy(bak_bq, BQ)
        toast("Crypto re-screen FAILED", "Bad fetch, rolled back. Run manually.")
        return
    print(f"  candidates={u['n_candidates']} (liquid {u['n_liquid']} of {u['n_tradable']})")

    print("scoring base quality...")
    ok, out = run("crypto_base_quality_v2.py")
    if not ok:
        print("base-quality FAILED:\n" + out[-1500:])
        if bak_bq.exists(): shutil.copy(bak_bq, BQ)
        return
    new = json.loads(BQ.read_text())
    shutil.copy(BQ, ARCH / f"base_quality_{stamp}.json")

    cur = {r["symbol"]: r for r in new["scored"]}
    old = {r["symbol"]: r for r in prev["scored"]} if prev else {}

    deep_new, base_new, degraded, gone, ladder_notes = [], [], [], [], []

    for s, r in cur.items():
        o = old.get(s)
        deep = r["ath_dd"] <= -90
        if deep and (not o or o["ath_dd"] > -90):
            deep_new.append(r)
        if r["base_score"] >= 50 and (not o or o["base_score"] < 50):
            base_new.append(r)
        if o and r["base_score"] < o["base_score"] - 10:
            degraded.append((r, o))
    for s in old:
        if s not in cur:
            gone.append(s)

    # qualified = in the only bucket with a positive base rate AND holding a base
    qualified = sorted([r for r in cur.values()
                        if r["ath_dd"] <= -90 and r["base_score"] >= 50],
                       key=lambda x: -x["base_score"])

    L = []
    L.append(f"CRYPTO BOTTOM RE-SCREEN {stamp}")
    L.append(f"universe: {u['n_tradable']} tradable -> {u['n_liquid']} liquid "
             f"-> {u['n_candidates']} candidates -> {len(cur)} validated")
    L.append(f"dropped for bad/short data: {len(new['dropped'])}")

    L.append(f"\nQUALIFIED (<=-90% from ATH AND base_score>=50) — {len(qualified)}:")
    if qualified:
        for r in qualified:
            tag = "  <-- IN LADDER" if r["symbol"] in LADDER_SYMS else ""
            L.append(f"  {r['symbol']:>8} score={r['base_score']:>5} dd={r['ath_dd']:>7.1f}% "
                     f"offLow={r['off_low_pct']:>6.1f}% low {r['low_date']}{tag}")
    else:
        L.append("  none — nothing meets both conditions. Do not force a buy.")

    if deep_new:
        L.append("\nNEW into the <=-90% bucket (the only bucket that pays):")
        for r in deep_new:
            L.append(f"  {r['symbol']:>8} dd={r['ath_dd']:.1f}% score={r['base_score']} "
                     f"low {r['low_date']} ({r['months_off_low']}mo ago)")
    if base_new:
        L.append("\nNEWLY built a base (score crossed 50):")
        for r in base_new:
            L.append(f"  {r['symbol']:>8} score={r['base_score']} dd={r['ath_dd']:.1f}%")
    if degraded:
        L.append("\nDEGRADED (score fell >10):")
        for r, o in degraded:
            tag = "  *** LADDER NAME" if r["symbol"] in LADDER_SYMS else ""
            L.append(f"  {r['symbol']:>8} {o['base_score']} -> {r['base_score']}{tag}")
    if gone:
        L.append(f"\nfell out of screen: {', '.join(gone)}")

    for s in LADDER_SYMS:
        r = cur.get(s)
        if not r:
            ladder_notes.append(f"{s} NO LONGER in screen — review the ladder")
        elif r["base_score"] < 50:
            ladder_notes.append(f"{s} base score fell to {r['base_score']} — review")
    if ladder_notes:
        L.append("\nLADDER REVIEW:")
        for n in ladder_notes:
            L.append("  ! " + n)

    L.append("\nReminder: buying the -70%..-25% band is the measured losing trade. "
             "Only <=-90% has a positive forward median.")

    report = "\n".join(L)
    (HOME / f"CRYPTO_RESCREEN_{stamp}.md").write_text(report)
    print("\n" + report)
    print(f"\nwrote {HOME / f'CRYPTO_RESCREEN_{stamp}.md'}")

    headline = []
    if deep_new: headline.append(f"{len(deep_new)} new <=-90%")
    if base_new: headline.append(f"{len(base_new)} new base")
    if ladder_notes: headline.append("LADDER REVIEW")
    if headline:
        toast("Crypto re-screen: " + ", ".join(headline),
              "; ".join(r["symbol"] for r in (deep_new + base_new))[:160] or "see report")


if __name__ == "__main__":
    main()
