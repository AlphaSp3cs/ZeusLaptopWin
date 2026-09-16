"""Crypto news repetition tracker.

Finds THEMES that repeat across independent outlets and tracks whether they are
ESCALATING over time. Built after the Coldcard exploit went $88M -> $130M across
three days while each individual headline looked like old news.

What it does:
  1. Pull articles via blogwatcher (RSS) + targeted web search for known live themes
  2. Cluster into themes by keyword signature
  3. Extract any dollar figures mentioned
  4. Diff against the previous run: NEW themes, ESCALATING themes ($ figure grew,
     or outlet count grew), and FADING themes
  5. Toast only when something is new or escalating

Run:  python3 crypto_news_tracker.py
      python3 crypto_news_tracker.py --quiet   (only print if new/escalating)
"""
import argparse, json, pathlib, re, subprocess, sys
from collections import defaultdict
from datetime import datetime, timezone

HOME = pathlib.Path.home()
HIST = HOME / ".hermes" / "crypto_news_history"
STATE = HIST / "themes_state.json"

# Theme signatures: name -> (required_any, bearish/bullish lean)
THEMES = {
    "coldcard_exploit":   ([r"coldcard", r"coinkite"], "BEARISH"),
    "exchange_hack":      ([r"hacked?", r"hackers", r"exploited?", r"drained", r"stolen",
                            r"breach", r"theft"], "BEARISH"),
    "defi_exploit":       ([r"defi exploit", r"protocol exploit", r"rug ?pull",
                            r"flash ?loan"], "BEARISH"),
    "sanctions_regulatory": ([r"ofac", r"sanctions?", r"\bsec\b", r"lawsuit", r"indict\w*",
                              r"\bbanned?\b", r"regulator\w*", r"clarity act"], "BEARISH"),
    "etf_flows":          ([r"\betfs?\b", r"inflows?", r"outflows?"], "NEUTRAL"),
    "liquidations":       ([r"liquidations?", r"liquidated", r"long squeeze",
                            r"cascade"], "BEARISH"),
    "fed_macro":          ([r"\bfed\b", r"rate cuts?", r"inflation", r"jobs report",
                            r"payrolls?", r"fomc"], "NEUTRAL"),
    "institutional_adopt": ([r"crypto treasury", r"bitcoin treasury", r"institutional \w+",
                             r"adopts? bitcoin", r"buys? bitcoin", r"corporate \w+ bitcoin"],
                            "BULLISH"),
    "stablecoin":         ([r"stablecoins?", r"\busdt\b", r"\busdc\b", r"tether",
                            r"depeg\w*"], "NEUTRAL"),
    "upgrade_launch":     ([r"upgrades?", r"mainnet", r"hard fork", r"launche?s?d?\b"],
                           "BULLISH"),
    "quantum_security":   ([r"quantum", r"firmware", r"vulnerabilit\w+"], "BEARISH"),
}

MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)\s*(m|million|b|billion|k)?", re.I)


def parse_money(text):
    """Return the largest USD figure mentioned, in millions."""
    best = 0.0
    for num, unit in MONEY.findall(text or ""):
        try:
            v = float(num.replace(",", ""))
        except ValueError:
            continue
        u = (unit or "").lower()
        if u in ("b", "billion"):
            v *= 1000
        elif u in ("k",):
            v /= 1000
        elif u in ("m", "million"):
            pass
        else:
            v = v / 1e6 if v > 10000 else 0   # bare big number -> assume raw USD
        best = max(best, v)
    return round(best, 2)


def get_articles():
    try:
        from blogwatcher_integration import BlogwatcherIntegration
    except Exception as e:
        print(f"blogwatcher import failed: {e}", file=sys.stderr)
        return []
    try:
        c = BlogwatcherIntegration()
        c.scan()
        return c.get_articles(limit=300, unread_only=False) or []
    except Exception as e:
        print(f"blogwatcher error: {e}", file=sys.stderr)
        return []


def classify(articles):
    themes = defaultdict(lambda: {"headlines": [], "outlets": set(), "max_usd_m": 0.0})
    for a in articles:
        title = (a.get("title") or "")
        url = (a.get("url") or "")
        blob = (title + " " + (a.get("summary") or "")).lower()
        if not title:
            continue
        outlet = ""
        m = re.search(r"https?://(?:www\.)?([^/]+)", url)
        if m:
            outlet = m.group(1)
        for name, (keys, lean) in THEMES.items():
            if any(re.search(k, blob) for k in keys):
                t = themes[name]
                t["headlines"].append(title[:130])
                if outlet:
                    t["outlets"].add(outlet)
                t["max_usd_m"] = max(t["max_usd_m"], parse_money(title))
                t["lean"] = lean
    for t in themes.values():
        t["outlets"] = sorted(t["outlets"])
        t["n"] = len(t["headlines"])
    return dict(themes)


def toast(title, msg):
    ps = ('[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications,'
          ' ContentType=WindowsRuntime] > $null;'
          '$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(1);'
          f'$t.GetElementsByTagName("text").Item(0).AppendChild($t.CreateTextNode("{title}")) > $null;'
          f'$t.GetElementsByTagName("text").Item(1).AppendChild($t.CreateTextNode("{msg}")) > $null;'
          '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier'
          '("Hermes News").Show([Windows.UI.Notifications.ToastNotification]::new($t))')
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=25)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--min-outlets", type=int, default=2,
                    help="a theme must appear in N+ distinct outlets to count as REPEATING")
    ap.add_argument("--cooldown-min", type=int, default=180,
                    help="min minutes between repeat alerts for the SAME theme")
    args = ap.parse_args()

    HIST.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    arts = get_articles()
    if not arts:
        print("no articles fetched - blogwatcher unavailable, NOT updating state")
        return
    cur = classify(arts)

    prev = {}
    last_alert = {}
    baseline = {}
    if STATE.exists():
        try:
            _s = json.loads(STATE.read_text())
            prev = _s.get("themes", {})
            last_alert = _s.get("last_alert", {})
            baseline = _s.get("alert_baseline", {})
        except Exception:
            prev = {}

    def cooled(name):
        """True if this theme has not alerted within the cooldown window."""
        ts = last_alert.get(name)
        if not ts:
            return True
        try:
            return (now - datetime.fromisoformat(ts)).total_seconds() / 60 >= args.cooldown_min
        except Exception:
            return True

    new_t, escalating, fading = [], [], []
    for name, t in cur.items():
        p = prev.get(name)
        repeating = len(t["outlets"]) >= args.min_outlets or t["n"] >= 3
        if not repeating:
            continue
        if not p:
            if cooled(name):
                new_t.append((name, t))
            continue
        # Escalate against the BASELINE AT LAST ALERT, not the previous run.
        # At 30-min cadence, run-over-run drift would otherwise fire constantly.
        b = baseline.get(name, p)
        grew_money = t["max_usd_m"] > (b.get("max_usd_m", 0) or 0) * 1.15 and t["max_usd_m"] > 0
        grew_vol = t["n"] > (b.get("n", 0) or 0) + 2
        if (grew_money or grew_vol) and cooled(name):
            escalating.append((name, t, b))
    for name, p in prev.items():
        if name not in cur and (p.get("n", 0) or 0) >= 3:
            fading.append(name)

    L = [f"CRYPTO NEWS REPETITION TRACKER  {now:%Y-%m-%d %H:%M} UTC",
         f"articles scanned: {len(arts)}"]

    rep = sorted([(n, t) for n, t in cur.items()
                  if len(t["outlets"]) >= args.min_outlets or t["n"] >= 3],
                 key=lambda x: -x[1]["n"])
    L.append(f"\nREPEATING THEMES ({len(rep)}):")
    for n, t in rep:
        money = f"  max=${t['max_usd_m']:,.0f}M" if t["max_usd_m"] else ""
        L.append(f"  {n:22s} n={t['n']:<3} outlets={len(t['outlets'])}"
                 f"  lean={t.get('lean','?'):8s}{money}")
        for h in t["headlines"][:2]:
            L.append(f"       - {h}")

    if new_t:
        L.append("\n*** NEW THEMES (started repeating since last run):")
        for n, t in new_t:
            L.append(f"  {n} — n={t['n']} outlets={len(t['outlets'])} lean={t.get('lean')}")
            for h in t["headlines"][:2]:
                L.append(f"     - {h}")
    if escalating:
        L.append("\n*** ESCALATING:")
        for n, t, p in escalating:
            L.append(f"  {n}: n {p.get('n')}->{t['n']}, "
                     f"max ${p.get('max_usd_m',0):,.0f}M -> ${t['max_usd_m']:,.0f}M")
            for h in t["headlines"][:2]:
                L.append(f"     - {h}")
    if fading:
        L.append(f"\nfading: {', '.join(fading)}")

    bearish = sum(t["n"] for n, t in rep if t.get("lean") == "BEARISH")
    bullish = sum(t["n"] for n, t in rep if t.get("lean") == "BULLISH")
    L.append(f"\nTONE: bearish-theme headlines {bearish} vs bullish {bullish} "
             f"-> {'RISK-OFF' if bearish > bullish * 1.5 else 'MIXED'}")

    # Record alert time + freeze the baseline for anything we alerted on now,
    # so the next escalation must beat THIS level, not merely drift past it.
    alerted = [n for n, *_ in escalating] + [n for n, _ in new_t]
    for n in alerted:
        last_alert[n] = now.isoformat()
        baseline[n] = {"n": cur[n]["n"], "max_usd_m": cur[n]["max_usd_m"]}

    STATE.write_text(json.dumps({
        "updated": now.isoformat(),
        "last_alert": last_alert,
        "alert_baseline": baseline,
        "themes": {n: {"n": t["n"], "outlets": t["outlets"],
                       "max_usd_m": t["max_usd_m"], "lean": t.get("lean")}
                   for n, t in cur.items()}}, indent=1))
    # Snapshot only when something alerted; at 48 runs/day a per-run dump would
    # bloat the history dir with thousands of identical files.
    if alerted:
        (HIST / f"themes_{now:%Y%m%d_%H%M}.json").write_text(
            json.dumps({n: {k: v for k, v in t.items()} for n, t in cur.items()}, indent=1))
    for old in sorted(HIST.glob("themes_2*.json"))[:-200]:
        try:
            old.unlink()
        except Exception:
            pass

    report = "\n".join(L)
    if new_t or escalating:
        head = []
        if escalating: head.append(f"{len(escalating)} escalating")
        if new_t: head.append(f"{len(new_t)} new")
        toast("Crypto news: " + ", ".join(head),
              "; ".join([n for n, *_ in escalating] + [n for n, _ in new_t])[:170])
        print(report)
    elif not args.quiet:
        print(report + "\n\nNo new or escalating themes since last run.")


if __name__ == "__main__":
    main()
