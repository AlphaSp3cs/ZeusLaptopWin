"""NEAR/INJ weekly DCA ladder checker.

Reads live price, evaluates each tranche's trigger + the invalidation level,
prints a verdict, and fires a Windows toast when action is required.

Run manually:  python3 dca_ladder_check.py
Silent mode :  python3 dca_ladder_check.py --quiet   (prints ONLY if action needed)
"""
import argparse, json, pathlib, subprocess, sys, warnings
from datetime import datetime, timezone
import pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")

HOME = pathlib.Path.home()
STATE = HOME / "dca_ladder_state.json"
LEVELS = HOME / "dca_ladder_levels.json"   # written by dca_tape_refresh.py
MAX_TAPE_AGE_H = 36                        # refuse stale tape

# Scheduled (time-based) tranches defer while CEREBRO prints any of these.
# Price-triggered tranches ALWAYS stay armed - catching weakness is the point.
DEFER_SIGNALS = {"STRONG_SELL", "SELL"}

# ---- LADDER DEFINITION -------------------------------------------------
# budget_usd = total capital allocated to the speculative bottom sleeve.
LADDER = {
    "NEAR": {
        "cycle_low": 0.9607, "low_date": "2026-02-11",
        "ma200_ref": 1.5830, "atr_pct": 4.4, "weight": 0.60,
        "invalidation": 0.9607,      # weekly close below cycle low
        "warn_level": 1.1600,        # -27% from spot: thesis under stress
        "tranches": [
            {"n": 1, "pct": 0.20, "trigger": "immediate",      "level": None},
            {"n": 2, "pct": 0.20, "trigger": "week_2",         "level": None},
            {"n": 3, "pct": 0.20, "trigger": "week_3",         "level": None},
            {"n": 4, "pct": 0.20, "trigger": "price_at_below", "level": 1.3500},
            {"n": 5, "pct": 0.20, "trigger": "price_at_below", "level": 1.1500},
        ],
    },
    "INJ": {
        "cycle_low": 2.7434, "low_date": "2026-04-02",
        "ma200_ref": 4.1243, "atr_pct": 5.3, "weight": 0.40,
        "invalidation": 2.7434,
        "warn_level": 3.3000,
        "tranches": [
            {"n": 1, "pct": 0.20, "trigger": "immediate",      "level": None},
            {"n": 2, "pct": 0.20, "trigger": "week_2",         "level": None},
            {"n": 3, "pct": 0.20, "trigger": "week_3",         "level": None},
            {"n": 4, "pct": 0.20, "trigger": "price_at_below", "level": 3.8000},
            {"n": 5, "pct": 0.20, "trigger": "price_at_below", "level": 3.2000},
        ],
    },
}


def live_price(sym):
    """Return (price, ma200, weekly_close) or (None, None, None)."""
    try:
        df = yf.download(f"{sym}-USD", period="2y", interval="1d",
                         auto_adjust=False, progress=False, threads=False)
    except Exception as e:
        print(f"  [{sym}] fetch error: {e}", file=sys.stderr)
        return None, None, None
    if df is None or len(df) == 0:
        return None, None, None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    c = df["Close"].astype(float).dropna()
    if len(c) < 200:
        return None, None, None
    wk = c.resample("W").last()
    return float(c.iloc[-1]), float(c.rolling(200).mean().iloc[-1]), float(wk.iloc[-1])


def toast(title, msg):
    """Native Windows toast. Falls back silently if unavailable."""
    ps = (
        '[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications,'
        ' ContentType=WindowsRuntime] > $null;'
        '$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(1);'
        f'$t.GetElementsByTagName("text").Item(0).AppendChild($t.CreateTextNode("{title}")) > $null;'
        f'$t.GetElementsByTagName("text").Item(1).AppendChild($t.CreateTextNode("{msg}")) > $null;'
        '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier'
        '("Hermes DCA").Show([Windows.UI.Notifications.ToastNotification]::new($t))'
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=25)
    except Exception:
        pass


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"started": datetime.now(timezone.utc).isoformat(),
            "budget_usd": None, "filled": {}, "halted": {}}


def apply_live_levels(quiet=False):
    """Overlay dca_ladder_levels.json onto LADDER. Returns (ok, note).

    Refuses stale or errored tape rather than trading off hardcoded numbers.
    """
    if not LEVELS.exists():
        return False, "no live tape file - run dca_tape_refresh.py"
    try:
        d = json.loads(LEVELS.read_text())
        ts = datetime.fromisoformat(d["refreshed"])
    except Exception as e:
        return False, f"unreadable tape file: {e}"
    age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    if age_h > MAX_TAPE_AGE_H:
        return False, (f"tape is {age_h:.0f}h old (limit {MAX_TAPE_AGE_H}h) "
                       f"- run dca_tape_refresh.py")

    notes = []
    for sym, cfg in LADDER.items():
        rec = d.get("symbols", {}).get(sym)
        if not rec or "error" in rec:
            notes.append(f"{sym}: tape error ({rec.get('error') if rec else 'missing'})")
            cfg["_stale"] = True
            continue
        cfg["cycle_low"] = rec["invalidation"]
        cfg["invalidation"] = rec["invalidation"]
        cfg["warn_level"] = rec["warn_level"]
        cfg["ma200_ref"] = rec["ma200"]
        cfg["atr_pct"] = rec["atr_pct"]
        cfg["low_date"] = rec["low_date"]
        cfg["base_score"] = rec["base_score"]
        cfg["cerebro"] = rec.get("cerebro", {})
        for t in cfg["tranches"]:
            if t["n"] == 4:
                t["level"] = rec["tranche4_level"]
            elif t["n"] == 5:
                t["level"] = rec["tranche5_level"]
        cfg["_stale"] = False
    return True, (f"live tape {ts:%Y-%m-%d %H:%M}Z ({age_h:.1f}h old)"
                  + ("; " + "; ".join(notes) if notes else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true",
                    help="print only when a tranche is due or invalidation hit")
    ap.add_argument("--budget", type=float, default=None,
                    help="set total sleeve budget in USD")
    ap.add_argument("--fill", type=str, default=None,
                    help="mark a tranche filled, e.g. NEAR:1")
    args = ap.parse_args()

    st = load_state()
    if args.budget:
        st["budget_usd"] = args.budget
    if args.fill:
        s, n = args.fill.split(":")
        st.setdefault("filled", {}).setdefault(s.upper(), [])
        if int(n) not in st["filled"][s.upper()]:
            st["filled"][s.upper()].append(int(n))
        STATE.write_text(json.dumps(st, indent=1))
        print(f"marked {args.fill} filled")
        return

    budget = st.get("budget_usd")
    weeks = (datetime.now(timezone.utc)
             - datetime.fromisoformat(st["started"])).days // 7 + 1

    tape_ok, tape_note = apply_live_levels()

    actions, lines = [], []
    lines.append(f"DCA LADDER CHECK  {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC"
                 f"   (week {weeks} of ladder)")
    lines.append(f"tape: {tape_note}")
    if not tape_ok:
        lines.append("  *** LEVELS NOT REFRESHED - all buys BLOCKED until tape updates")
    if budget:
        lines.append(f"sleeve budget: ${budget:,.0f}")
    else:
        lines.append("sleeve budget: NOT SET -- run with --budget <usd>")

    for sym, cfg in LADDER.items():
        px, ma200, wkclose = live_price(sym)
        if px is None:
            lines.append(f"\n[{sym}] DATA UNAVAILABLE - no action taken")
            continue
        filled = st.get("filled", {}).get(sym, [])
        halted = st.get("halted", {}).get(sym, False)
        alloc = budget * cfg["weight"] if budget else None

        lines.append(f"\n[{sym}] px=${px:,.4f}  MA200=${ma200:,.4f} "
                     f"({(px/ma200-1)*100:+.1f}%)  cycle_low=${cfg['cycle_low']:,.4f} "
                     f"({(px/cfg['cycle_low']-1)*100:+.1f}%)")

        cb = cfg.get("cerebro") or {}
        cb_block = False
        if cb and "error" not in cb:
            lines.append(f"  CEREBRO: {cb.get('signal')} conviction={cb.get('conviction')} "
                         f"RSI={cb.get('rsi')} vol_conf={cb.get('volume_confirmed')}")
            if cb.get("signal") in DEFER_SIGNALS:
                cb_block = True
                lines.append(f"  ! CEREBRO {cb.get('signal')} - scheduled buys deferred "
                             "(price-triggered tranches still allowed)")
        if cfg.get("base_score") is not None:
            lines.append(f"  base_score={cfg['base_score']}  "
                         f"low {cfg.get('low_date')}  ATR={cfg.get('atr_pct')}%")

        # --- invalidation: WEEKLY close under cycle low ---
        if wkclose < cfg["invalidation"]:
            st.setdefault("halted", {})[sym] = True
            msg = (f"{sym} INVALIDATED - weekly close ${wkclose:,.4f} "
                   f"below cycle low ${cfg['invalidation']:,.4f}. STOP DCA. "
                   f"Thesis broken, do not average further.")
            lines.append("  *** " + msg)
            actions.append(msg)
            continue
        if halted:
            lines.append(f"  HALTED previously - manual reset required in {STATE.name}")
            continue
        if px < cfg["warn_level"]:
            lines.append(f"  ! stress: below warn level ${cfg['warn_level']:,.4f} "
                         f"- thesis intact but weakening, do NOT upsize")

        for t in cfg["tranches"]:
            if t["n"] in filled:
                lines.append(f"  tranche {t['n']}  {t['pct']*100:.0f}%  FILLED")
                continue
            amt = f"${alloc*t['pct']:,.0f}" if alloc else f"{t['pct']*100:.0f}% of {sym} alloc"
            due = False
            if t["trigger"] == "immediate":
                due = True
                why = "start now"
            elif t["trigger"].startswith("week_"):
                wk_needed = int(t["trigger"].split("_")[1])
                due = weeks >= wk_needed
                why = f"week {wk_needed} scheduled" if due else f"waits until week {wk_needed}"
            else:  # price_at_below
                due = px <= t["level"]
                why = (f"price <= ${t['level']:,.4f}" if due
                       else f"waits for <= ${t['level']:,.4f}")
            tag = ">>> BUY NOW" if due else "    pending "
            if due and not tape_ok:
                tag = "    BLOCKED"; why = "stale tape - refresh first"; due = False
            elif due and cb_block and t["trigger"] != "price_at_below":
                tag = "    DEFERRED"; why = f"CEREBRO {cb.get('signal')}"; due = False
            lines.append(f"  tranche {t['n']}  {t['pct']*100:.0f}%  {amt:>10}  {tag}  ({why})")
            if due:
                actions.append(f"{sym} tranche {t['n']}: buy {amt} @ ~${px:,.4f} ({why})")

    STATE.write_text(json.dumps(st, indent=1))
    out = "\n".join(lines)

    # Re-arm alert: a fully-deferred ladder is silent under --quiet, so tell the
    # user the moment CEREBRO clears and scheduled buys become live again.
    prev_def = set(st.get("deferred_last", []))
    now_def = {s for s, c in LADDER.items()
               if (c.get("cerebro") or {}).get("signal") in DEFER_SIGNALS}
    rearmed = sorted(prev_def - now_def)
    st["deferred_last"] = sorted(now_def)
    STATE.write_text(json.dumps(st, indent=1))
    if rearmed:
        msg = ("RE-ARMED: " + ", ".join(rearmed)
               + " no longer SELL/STRONG_SELL - scheduled tranches live again")
        out += "\n\n*** " + msg
        toast("DCA ladder re-armed", msg[:180])

    if actions:
        out += "\n\nACTION REQUIRED:\n" + "\n".join("  - " + a for a in actions)
        out += (f"\n\nAfter buying, record it:\n"
                f"  python3 dca_ladder_check.py --fill NEAR:1")
        toast("DCA ladder: action required", actions[0][:180])
        print(out)
    elif not args.quiet:
        print(out + "\n\nNo action required this check.")


if __name__ == "__main__":
    main()
