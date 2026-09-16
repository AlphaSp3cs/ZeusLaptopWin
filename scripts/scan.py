#!/usr/bin/env python3
"""UNIFIED SCAN ROUTER — one entry point for every scan in this workspace.

    python3 scan.py <mode> [--equity N] [--no-news] [--dry-run]

Modes:
    premarket   US premarket, all sectors tradeable      universal_premarket_scan.py
    nightshift  overnight: fx/cmd/indices/crypto only    nightshift_scan.py
    allsector   full orchestrated workflow               run_all_sector_workflow.py
    crypto      CEREBRO cryptoweekend + RSI sweep        cerebro_crypto_weekend.py
    rsi         oversold/overbought sweep + backtest     crypto_rsi_sweep.py
    bottom      monthly deep-drawdown re-screen          crypto_bottom_rescreen.py
    ladder      DCA tape refresh + tranche check         dca_tape_refresh + dca_ladder_check
    news        news repetition tracker                  crypto_news_tracker.py
    recheck     ladder + news + crypto (the "check again" chain)

Every mode that produces trade candidates runs the SAME rails afterwards:
    1. danger_zone_gauge.py   -> regime risk, hedge posture
    2. blogwatcher/news       -> catalyst + repetition context
    3. enhanced_trade_gate.py -> the ONLY thing that authorises a candidate

Nothing here places an order. The gate outputs candidates; execution stays manual.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone

HOME = pathlib.Path.home()
PY = sys.executable or "python3"

# mode -> (script, args, produces_scan_json)
MODES = {
    "premarket":  ("universal_premarket_scan.py", [], "universal_scan_results_latest.json"),
    "nightshift": ("nightshift_scan.py", [], "nightshift_scan_results_latest.json"),
    "allsector":  ("run_all_sector_workflow.py", [], None),
    "crypto":     ("cerebro_crypto_weekend.py", [], None),
    "rsi":        ("crypto_rsi_sweep.py", [], None),
    "bottom":     ("crypto_bottom_rescreen.py", [], None),
    "news":       ("crypto_news_tracker.py", [], None),
    "cryptofut":  ("cryptofut_scan.py", [], None),  # perp squeeze layer; its own JSON, not the spot gate
    "theories":   ("theory_amplifier.py", ["--cached", "--json",
                                           "theory_amplifier_populated.json"], None),
    "income":     ("covered_call_scan.py", ["--save"], None),
    # Full-population sweep: SPOT + equity options + futures options + bonds.
    # The ONLY mode that honours "scan everything while market is open".
    "allpop":     ("full_population_sweep.py", [], None),
    "allscan":    ("comprehensive_scan.py", [], None),
}


def run(script, args=None, timeout=1800, quiet=False):
    """Run a workspace script, stream nothing, return (ok, tail)."""
    path = HOME / script
    if not path.exists():
        return False, f"MISSING: {script}"
    cmd = [PY, str(path)] + (args or [])
    try:
        p = subprocess.run(cmd, cwd=str(HOME), capture_output=True,
                           text=True, timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        tail = "\n".join([l for l in out.splitlines()
                          if "Deprecat" not in l and "utcnow" not in l][-25:])
        return p.returncode == 0, tail
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s: {script}"
    except Exception as e:
        return False, f"ERROR {script}: {e}"


def danger_gauge():
    g = HOME / ".hermes" / "gauges" / "danger_zone_gauge.py"
    if not g.exists():
        return None, "danger_zone_gauge.py not found"
    try:
        p = subprocess.run([PY, str(g), "--once"], cwd=str(g.parent),
                           capture_output=True, text=True, timeout=180)
        out = (p.stdout or "") + (p.stderr or "")
        # The gauge emits ANSI colour codes; float() on a coloured token fails
        # silently and the EXTREME-regime warning never fires. Strip them.
        clean = re.sub(r"\x1b\[[0-9;]*m", "", out)
        score = None
        for line in clean.splitlines():
            if "Gauge:" in line:
                m = re.search(r"([\d.]+)\s*/\s*100", line)
                if m:
                    try:
                        score = float(m.group(1))
                    except ValueError:
                        pass
                return score, line.strip()
        return score, "gauge ran, no score line"
    except Exception as e:
        return None, f"gauge error: {e}"


def gate(scan_file, equity, allow_stale=False):
    args = ["--scan-file", scan_file, "--equity", str(equity), "--profile", "both"]
    if allow_stale:
        args.append("--allow-stale")
    return run("enhanced_trade_gate.py", args, timeout=900)


def sentinel_provenance():
    """Report which sentinel data sources are actually LIVE.

    Returns a list of printable lines. Never raises - a provenance failure
    must not kill a scan, but it must never be silent either.
    """
    audit = HOME / "sentinel_audit.py"
    if not audit.exists():
        return ["\n[provenance] sentinel_audit.py missing - sentinel health UNKNOWN"]
    try:
        p = subprocess.run([PY, str(audit), "--json"],
                           capture_output=True, text=True, timeout=180)
        data = json.loads(p.stdout)
    except Exception as e:  # noqa: BLE001
        return [f"\n[provenance] audit failed ({e}) - sentinel health UNKNOWN"]

    res = data.get("results", [])
    live = [r["skill"] for r in res if r["status"] == "LIVE"]
    bad = [r for r in res if r["status"] in ("DEAD", "MISSING")]
    stale = [r["skill"] for r in res if r["status"] == "STALE"]

    out = [f"\n[provenance] {len(live)}/{len(res)} sentinels LIVE"]
    if live:
        out.append(f"  live  : {', '.join(live)}")
    if stale:
        out.append(f"  stale : {', '.join(stale)}")
    if bad:
        out.append(f"  DEAD  : {', '.join(r['skill'] for r in bad)}")
        out.append("  !! DEAD sentinels produce NO data. Their silence is not "
                   "confirmation.")
        out.append("  !! Do NOT count them toward confluence or treat them as "
                   "passing risk checks.")
    return out


BARS = pathlib.Path(r"C:\Hermes\workflow")


def bars_refresh(sectors=None, tf="1d"):
    """Refresh the D:\\Hermes bar store before a scan reads it."""
    s = BARS / "scripts" / "bars_db.py"
    if not s.exists():
        return False, f"MISSING: {s}"
    args = ["--update", "--tf", tf]
    for sec in (sectors or []):
        args += ["--sector", sec]
    try:
        p = subprocess.run([PY, str(s)] + args, cwd=str(s.parent),
                           capture_output=True, text=True, timeout=2400)
        out = (p.stdout or "") + (p.stderr or "")
        tail = "\n".join([l for l in out.splitlines()
                          if "delisted" not in l and l.strip()][-12:])
        return p.returncode == 0, tail
    except Exception as e:                                   # noqa: BLE001
        return False, f"bars refresh error: {e}"


def bars_ready():
    """Print the sector readiness board. Returns (all_ready, tail)."""
    s = BARS / "scripts" / "market_open_ready.py"
    if not s.exists():
        return False, f"MISSING: {s}"
    try:
        p = subprocess.run([PY, str(s)], cwd=str(s.parent),
                           capture_output=True, text=True, timeout=300)
        return p.returncode == 0, (p.stdout or "") + (p.stderr or "")
    except Exception as e:                                   # noqa: BLE001
        return False, f"readiness error: {e}"


def fresh_sentiment():
    """Pull a FRESH crypto sentiment reading BEFORE the scan (by-law: sentiment
    must be checked fresh and used for conviction, not stale/assumed).

    Runs the crypto-sentiment-aggregator skill, parses its printed composite,
    and writes sentiment_latest.json the scanner/gate can consume. Returns the
    parsed dict {composite, coverage, lean, confidence_ok, timestamp} or None.

    Honesty rule: if the aggregator can't run or returns no reading, we return
    None and the scanner flags LOW-COVERAGE — we NEVER synthesize a sentiment.
    """
    import shutil
    skill = pathlib.Path(r"C:\Hermes\skills\crypto-sentiment-aggregator\crypto_sentiment_aggregator.py")
    if not skill.exists():
        print("\n[sentiment] SKILL MISSING — cannot pull fresh sentiment")
        return None
    try:
        p = subprocess.run([PY, str(skill), "report"], cwd=str(skill.parent),
                           capture_output=True, text=True, timeout=120)
    except Exception as e:  # noqa: BLE001
        print(f"\n[sentiment] run error: {e}")
        return None
    out = (p.stdout or "") + (p.stderr or "")
    # Parse "SENTIMENT composite=+0.123 (LABEL)  coverage=20%"
    m = re.search(r"composite=([+-]?[\d.]+)\s*\(([^)]+)\)\s*coverage=([\d.]+)%", out)
    if not m:
        print(f"\n[sentiment] no reading returned (raw tail): {out.strip()[:200]}")
        return None
    composite = float(m.group(1))
    label = m.group(2).strip()
    coverage = float(m.group(3)) / 100.0
    lean = "SHORT" if composite < -0.1 else "LONG" if composite > 0.1 else "NEUTRAL"
    confidence_ok = coverage >= 0.6
    rec = {
        "composite": composite, "label": label, "coverage": coverage,
        "lean": lean, "confidence_ok": confidence_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (HOME / "sentiment_latest.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    flag = "" if confidence_ok else "  !! LOW COVERAGE — do NOT size off this"
    print(f"\n[sentiment] FRESH composite={composite:+.3f} ({label}) lean={lean} "
          f"coverage={coverage*100:.0f}%{flag}")
    return rec


def fresh_prediction_sentiment():
    """Pull a FRESH prediction-market sentiment reading BEFORE the scan.

    Mirrors fresh_sentiment(): runs prediction_sentiment.py (Polymarket +
    Kalshi), parses its per-asset block, and writes
    prediction_sentiment_latest.json the scanner/gate can consume. Returns the
    parsed doc or None.

    Honesty rule: if the module can't run or returns no reading, we return None
    and the scanner flags UNVERIFIED -- we NEVER synthesize a sentiment. Kalshi
    may be network-blocked; that degrades to UNVERIFIED, not a crash.
    """
    skill = HOME / "prediction_sentiment.py"
    if not skill.exists():
        print("\n[prediction-sentiment] MODULE MISSING — cannot pull PM odds")
        return None
    try:
        p = subprocess.run([PY, str(skill), "--report"], cwd=str(HOME),
                           capture_output=True, text=True, timeout=180)
    except Exception as e:  # noqa: BLE001
        print(f"\n[prediction-sentiment] run error: {e}")
        return None
    out = (p.stdout or "") + (p.stderr or "")
    # Surface the module's own summary lines (it prints a clear block).
    for line in out.splitlines():
        if line.strip().startswith(("polymarket:", "kalshi", "PMS:",
                                    "Prediction-market odds", "wrote")):
            print(f"  [pms] {line.strip()}")
    try:
        doc = json.loads((HOME / "prediction_sentiment_latest.json").read_text(
            encoding="utf-8"))
    except Exception:
        print("\n[prediction-sentiment] no reading returned")
        return None
    n_ok = sum(1 for v in doc.get("assets", {}).values() if v.get("status") == "OK")
    print(f"  [pms] {n_ok} asset(s) with live PM markets; "
          f"polymarket={doc['sources']['polymarket']['status']} "
          f"kalshi={doc['sources']['kalshi']['status']}")
    return doc


def pms_confirm_scan(populated=None, bias_map=None):
    """POST-SCAN hook: confirm the scan's populated assets against prediction
    markets (Kalshi/Polymarket) and print a bearish/bullish + price-level
    confirmation table. Called by crypto-weekend, nightshift, and all-sector
    (day) scans AFTER they populate assets.

    populated: optional explicit list of symbols or {symbol, tech_bias} dicts.
               If None, auto-discovers from the latest gate JSON
               (enhanced_setups_*_latest.json): LONG -> BULLISH, SHORT ->
               BEARISH. This keeps every scan's call to a single line while
               still respecting an explicit list when the caller has one.
    bias_map:  optional {symbol: 'BULLISH'|'BEARISH'|'NEUTRAL'} override.

    Honesty: assets with no PM market still appear (macro regime applies),
    never silently dropped. Missing/blocked source -> UNVERIFIED, not neutral.
    """
    import importlib
    try:
        pms = importlib.import_module("prediction_sentiment")
    except Exception as e:  # noqa: BLE401
        print(f"\n[pms-confirm] module unavailable: {e}")
        return None

    # Auto-discover populated assets from the latest gate JSON if not given.
    if populated is None:
        populated = []
        for pat in ("enhanced_setups_swing_latest.json",
                    "enhanced_setups_day_latest.json"):
            gf = HOME / pat
            if not gf.exists():
                continue
            try:
                gj = json.loads(gf.read_text(encoding="utf-8"))
            except Exception:
                continue
            for arr in ("longs", "shorts"):
                for su in (gj.get(arr) or []):
                    if not isinstance(su, dict):
                        continue
                    sym = su.get("symbol")
                    side = str(su.get("side", "")).upper()
                    if sym:
                        populated.append({"symbol": sym,
                                          "tech_bias": "BULLISH" if side == "LONG"
                                          else "BEARISH" if side == "SHORT"
                                          else "NEUTRAL"})
        # Focus: PM only speaks on crypto + macro anchors. Confirm those; drop
        # the long tail of equity/ETF tickers that have no PM market (their
        # confirmation would just be macro-regime CONTEXT spam).
        try:
            _uni = set(pms.DEFAULT_UNIVERSE)
        except Exception:
            _uni = set()
        if _uni:
            # Scans pass Binance pairs ("BTC/USDT"); DEFAULT_UNIVERSE is bare
            # tickers ("BTC"). Normalise the membership test to the base ticker
            # or EVERY crypto name gets whitelisted-out (PM integration dead).
            populated = [p for p in populated
                         if str(p["symbol"]).split("/")[0].upper() in _uni]
        # Dedupe by symbol (a ticker can appear in both swing + day gate JSONs).
        _seen, _dedup = set(), []
        for p in populated:
            k = str(p["symbol"]).upper()
            if k not in _seen:
                _seen.add(k)
                _dedup.append(p)
        populated = _dedup

    if not populated:
        print("\n[pms-confirm] no populated assets found to confirm")
        return None

    # Always build FRESH for the confirmation pass (post-scan second opinion).
    # Reusing a possibly-stale prediction_sentiment_latest.json would miss the
    # price_level/level_kind fields this confirmation depends on. One fetch,
    # cheap, and honest (consensus as of now, not as of pre-scan).
    try:
        doc = pms.build(pms.DEFAULT_UNIVERSE)
    except Exception as e:  # noqa: BLE401
        print(f"\n[pms-confirm] PM build failed: {e}")
        return None

    print("\n[pms-confirm] confirming populated assets against prediction markets")
    try:
        pms.print_confirm(populated, doc, bias_map)
    except Exception as e:  # noqa: BLE401
        print(f"\n[pms-confirm] confirm failed: {e}")
    return doc


def valuation(tickers, target_pct=5.0):
    """Run the equity valuation scorecard. Returns (ok, tail).

    Price/flow signals say WHEN. This says WHETHER the business is worth
    owning at all. A scan candidate with no valuation read is an unverified
    candidate - same rule as a dead sentinel: silence is not a pass.
    """
    if not tickers:
        return True, "no equity tickers to score"
    args = list(tickers) + ["--target-pct", str(target_pct),
                            "--json", "valuation_latest.json"]
    return run("valuation_scorecard.py", args, timeout=900)


UNIVERSE = HOME / "universe_master.json"
UNIVERSE_MAX_AGE_H = 24

# Which universe sector each scan mode is claiming to cover. Used only to print
# the honest denominator ("scanned N of M") so a scan can never imply that a
# 40-name hardcoded list is the whole sector.
MODE_SECTORS = {
    "crypto": ["CRYPTO"],
    "rsi": ["CRYPTO"],
    "bottom": ["CRYPTO"],
    "news": ["CRYPTO"],
    "cryptofut": ["CRYPTO"],
    "ladder": ["CRYPTO"],
    "premarket": ["US_EQUITY", "ETF", "FX", "COMMODITIES", "INDICES"],
    "nightshift": ["FX", "COMMODITIES", "INDICES", "CRYPTO"],
    "allsector": ["US_EQUITY", "ETF", "FX", "COMMODITIES", "INDICES", "CRYPTO"],
    # Full-population sweep covers every asset class INCLUDING derivatives and
    # the treasury/rates complex. No population may silently return zero.
    "allpop": ["US_EQUITY", "ETF", "FX", "COMMODITIES", "INDICES", "CRYPTO",
               "OPTIONS_EQ", "OPTIONS_FUT", "BONDS", "RATES"],
    "allscan": ["US_EQUITY", "ETF", "FX", "COMMODITIES", "INDICES", "CRYPTO",
                "OPTIONS_EQ", "OPTIONS_FUT", "BONDS", "RATES", "STABLECOINS",
                "REG_CLARITY", "FOREX_BT", "METALS_ENERGY_AI"],
}


def coverage(mode, auto_build=True):
    """Print the universe denominator + any venue we are blind to.

    Rebuilds universe_master.json when missing or stale. Returns the doc so
    downstream scanners can pull the FULL sector list instead of a stub.
    """
    import time as _t

    stale = True
    doc = None
    if UNIVERSE.exists():
        age_h = (_t.time() - UNIVERSE.stat().st_mtime) / 3600.0
        stale = age_h > UNIVERSE_MAX_AGE_H
        try:
            doc = json.loads(UNIVERSE.read_text(encoding="utf-8"))
        except Exception:
            doc, stale = None, True
    if (doc is None or stale) and auto_build:
        print("[coverage] universe missing/stale -> rebuilding from brokers...")
        run("universe_builder.py", [], timeout=900, quiet=True)
        if UNIVERSE.exists():
            doc = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    if not doc:
        print("[coverage] NO UNIVERSE FILE - cannot prove full-sector coverage")
        return None

    secs = MODE_SECTORS.get(mode, sorted(doc.get("counts", {})))
    print(f"\n[coverage] universe built {doc.get('built_at')}")
    for s in secs:
        print(f"  {s:<14} {doc['counts'].get(s, 0):>6} assets available")
    gaps = doc.get("gaps") or {}
    if gaps:
        print("  BLIND SPOTS (venues we cannot enumerate):")
        for k, v in gaps.items():
            print(f"    - {k}: {v[:110]}")

    # --- ratchet check: coverage may never silently shrink -----------------
    ok_g, tail_g = run("coverage_guard.py", ["--check"], timeout=120, quiet=True)
    if not ok_g:
        print("\n" + "!" * 66)
        print("COVERAGE REGRESSION - this scan CAN miss assets. Details:")
        print(tail_g.strip()[-1200:])
        print("!" * 66)
    else:
        run("coverage_guard.py", ["--update"], timeout=120, quiet=True)
    return doc


def income_section(symbols=None, dte=30, save=False):
    """ThetaGang-style income overlay. For every qualifying candidate (or an
    explicit list), compute covered-call + cash-secured-put setups so a scan
    surfaces 'income-able' assets alongside directional GOs.

    This is an OBSERVATION layer only -- it does NOT place trades and the
    enhanced_trade_gate remains the only authoriser of any action.
    """
    if symbols is None:
        return [], 0
    syms = [str(s).strip().upper() for s in symbols if s]
    if not syms:
        return [], 0
    try:
        from covered_call_scan import compute_income_setups, save_results
    except Exception as e:  # noqa: BLE001
        print(f"\n[income] engine unavailable ({e}) -- income setups skipped")
        return [], 0
    print(f"\n[income] computing covered-call / CSP setups for {len(syms)} "
          f"candidate(s) (DTE~{dte})...")
    rows = compute_income_setups(syms, dte=dte)
    if not rows:
        print("  [income] no option-chain setups produced for these candidates")
        return [], 0
    print(f"  [income] {len(rows)} candidate(s) have income setups:")
    for r in rows:
        call_best = max((x["annual_yield_pct"] for x in r.get("rungs", {}).values()),
                        default=0)
        csp_best = max((x["annual_yield_on_collateral_pct"]
                        for x in r.get("csp_rungs", {}).values()), default=0)
        flag = f"  !! {r['flag']}" if r.get("flag") else ""
        print(f"    {r['symbol']} spot=${r['spot']} IV={r['iv']} "
              f"bestCALLyld={call_best:.1f}% bestCSPyld={csp_best:.1f}%{flag}")
    if save:
        save_results(rows, dte)
    return rows, len(rows)


def main():  # noqa: C901
    ap = argparse.ArgumentParser(description="Unified scan router")
    ap.add_argument("mode", choices=sorted(set(list(MODES) +
                                               ["ladder", "recheck", "value",
                                                "ready", "bars"])))
    ap.add_argument("--equity", type=float, default=100000.0)
    ap.add_argument("--no-news", action="store_true")
    ap.add_argument("--no-pms", action="store_true",
                    help="skip the prediction-market sentiment (Kalshi/Polymarket) pull")
    ap.add_argument("--no-gate", action="store_true")
    ap.add_argument("--allow-stale", action="store_true")
    ap.add_argument("--no-provenance", action="store_true")
    ap.add_argument("--value", nargs="*", metavar="TICKER",
                    help="run the equity valuation scorecard on these tickers "
                         "(equity modes only)")
    ap.add_argument("--target-pct", type=float, default=5.0)
    ap.add_argument("--sector", action="append",
                    help="limit bar refresh to these sectors (repeatable)")
    ap.add_argument("--tf-bars", choices=["1d", "1h"], default="1d")
    ap.add_argument("--no-bars", action="store_true",
                    help="skip the pre-scan bar refresh")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--income", dest="income", action="store_true", default=None,
                    help="force the covered-call/CSP income overlay (on by "
                         "default for equity modes)")
    ap.add_argument("--no-income", dest="income", action="store_false",
                    help="disable the income overlay")
    ap.add_argument("--income-dte", type=int, default=30,
                    help="target days-to-expiry for income setups")
    ap.add_argument("--tickers", nargs="*", default=None,
                    help="tickers for the 'income' mode (forwarded to engine)")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap # tickers evaluated (income mode)")
    ap.add_argument("--top", type=int, default=None,
                    help="cryptofut: max ranked perps to show")
    ap.add_argument("--min-score", type=float, default=None,
                    help="cryptofut: minimum composite score to rank")
    a = ap.parse_args()

    now = datetime.now(timezone.utc)
    print("=" * 74)
    print(f"SCAN ROUTER  mode={a.mode}  {now:%Y-%m-%d %H:%M} UTC")
    print("=" * 74)

    if a.dry_run:
        print(f"would run: {MODES.get(a.mode, ('(composite)',))[0]}")
        print("then: danger gauge -> news -> enhanced_trade_gate")
        return 0

    # ---- coverage gate: prove we know the full sector before scanning it ----
    coverage(a.mode)

    # ---- data-only modes: no gauge/provenance needed, run and exit --------
    if a.mode == "ready":
        ok_r, tail_r = bars_ready()
        print(tail_r)
        return 0 if ok_r else 1

    if a.mode == "bars":
        ok_b, tail_b = bars_refresh(a.sector, (a.tf_bars or "1d"))
        print(f"\n[bars] {'OK' if ok_b else 'FAIL'}\n{tail_b}")
        ok_r, tail_r = bars_ready()
        print(tail_r)
        return 0 if (ok_b and ok_r) else 1

    # ---- regime first: it colours how everything else is read -------------
    score, gline = danger_gauge()
    print(f"\n[REGIME] {gline}")
    if score is not None and score >= 75:
        print("  !! EXTREME regime risk - size down / prefer hedges / expect gate refusals")

    ok_all = True

    # ---- provenance: which sentinels are actually alive? -------------------
    # A dead sentinel is SILENT, and silence gets misread as "no signal".
    # Print the fleet state up front so nothing downstream counts empty
    # scaffolding as a passing risk check. See skill signal-provenance-audit.
    if not a.no_provenance:
        for line in sentinel_provenance():
            print(line)

    # ---- bars first: every downstream script reads price ------------------
    # A scan run on stale bars is a scan on last week's market.
    if not a.no_bars and a.mode not in ("ready", "bars"):
        ok_b, tail_b = bars_refresh(a.sector, a.tf_bars)
        print(f"\n[bars] {'OK' if ok_b else 'FAIL'} ({a.tf_bars})")
        for line in tail_b.splitlines()[-6:]:
            print(f"  {line}")
        if not ok_b:
            print("  !! bar refresh FAILED - downstream reads may be stale")
        ok_all &= ok_b

    # ---- composite modes ---------------------------------------------------
    if a.mode == "ladder":
        for s in ("dca_tape_refresh.py", "dca_ladder_check.py"):
            ok, tail = run(s, timeout=900)
            print(f"\n[{s}] {'OK' if ok else 'FAIL'}\n{tail}")
            ok_all &= ok
        return 0 if ok_all else 1

    if a.mode == "value":
        if not a.value:
            print("\nusage: python3 scan.py value --value NTNX MSFT ...")
            return 2
        ok_v, tail_v = valuation(a.value, a.target_pct)
        print(f"\n[valuation] {'OK' if ok_v else 'FAIL'}\n{tail_v}")
        return 0 if ok_v else 1

    if a.mode == "recheck":
        for s in ("cerebro_crypto_weekend.py", "crypto_news_tracker.py",
                  "dca_tape_refresh.py", "dca_ladder_check.py"):
            ok, tail = run(s, ["--quiet"] if "news" in s else None, timeout=1200)
            print(f"\n[{s}] {'OK' if ok else 'FAIL'}\n{tail}")
            ok_all &= ok
        return 0 if ok_all else 1

    # ---- fresh sentiment BEFORE scan (by-law: check sentiment fresh, then use
    #      it for conviction). Runs before the scanner so conviction can consume
    #      the reading via sentiment_latest.json.
    if a.mode in ("premarket", "nightshift", "allsector", "allpop", "allscan", "crypto", "cryptofut", "theories"):
        fresh_sentiment()
        if not a.no_pms:
            fresh_prediction_sentiment()
        else:
            print("\n[prediction-sentiment] SKIPPED (--no-pms)")

    # ---- single-script modes ----------------------------------------------
    if a.mode == "income":
        eng_args = ["--save"]
        if a.tickers:
            eng_args += ["--tickers"] + a.tickers
        if a.limit:
            eng_args += ["--limit", str(a.limit)]
        ok, tail = run("covered_call_scan.py", eng_args, timeout=2400)
        print(f"\n[covered_call_scan.py] {'OK' if ok else 'FAIL'}\n{tail}")
        ok_all &= ok
    else:
        script, args, scan_json = MODES[a.mode]
        run_args = list(args)
        # Pass-through for cryptofut tuning (ignored by other modes' scripts).
        if a.top is not None:
            run_args += ["--top", str(a.top)]
        if a.min_score is not None:
            run_args += ["--min-score", str(a.min_score)]
        ok, tail = run(script, run_args, timeout=2400)
        print(f"\n[{script}] {'OK' if ok else 'FAIL'}\n{tail}")
        if not ok:
            # A scanner that dies mid-run has ALREADY printed partial results that
            # look like a normal scan. Make the failure impossible to skim past --
            # a truncated universe is exactly how assets go missing silently.
            print("\n" + "!" * 66)
            print(f"!! {script} EXITED NON-ZERO - the scan above is INCOMPLETE.")
            print("!! Do not treat its output as full-sector coverage.")
            print("!" * 66)
        ok_all &= ok

    # ---- news overlay ------------------------------------------------------
    if not a.no_news and a.mode in ("premarket", "nightshift", "allsector", "allpop", "allscan", "crypto", "cryptofut", "theories"):
        ok_n, tail_n = run("crypto_news_tracker.py", ["--quiet"], timeout=900)
        if tail_n.strip():
            print(f"\n[news] {tail_n}")
        else:
            print("\n[news] no new or escalating themes")

    # ---- valuation rail ----------------------------------------------------
    # Explicit tickers via --value, or auto-derived from an equity scan file.
    val_tickers = list(a.value or [])
    if not val_tickers and scan_json and a.mode in ("premarket", "allsector", "allpop"):
        fj = HOME / scan_json
        if fj.exists():
            try:
                blob = json.loads(fj.read_text(encoding="utf-8"))
                # universal_premarket_scan.py emits qualified_longs /
                # qualified_shorts. The generic names are fallbacks for other
                # producers - without the real keys the valuation rail
                # silently scored nothing and looked like it had passed.
                cands = []
                for key in ("qualified_longs", "qualified_shorts",
                            "candidates", "results", "tickers"):
                    v = blob.get(key)
                    if isinstance(v, list):
                        cands.extend(v)
                seen = set()
                # The premarket universe is macro-heavy (FX, futures, bond and
                # sector ETFs). The 6-point scorecard only means something for
                # an operating company - feeding it GLD/TLT/GC produces a
                # meaningless read. Skip known non-equities; the scorecard
                # also self-detects funds via quoteType as a second net.
                NOT_EQUITY = {
                    "GLD", "SLV", "USO", "UNG", "TLT", "IEF", "SHY", "HYG",
                    "LQD", "TIP", "SPY", "QQQ", "IWM", "DIA", "GC", "SI",
                    "PL", "PA", "HG", "CL", "BZ", "NG", "RB", "HO", "ZC",
                    "ZW", "ZS", "KC", "SB", "CT", "CC", "LE",
                    "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLB",
                    "XLRE", "XLU", "XLC",
                }
                for c in cands:
                    sym = (c.get("symbol") or c.get("ticker")
                           if isinstance(c, dict) else c)
                    if not sym:
                        continue
                    sym = str(sym).upper()
                    if not sym.isalpha() or sym in seen or sym in NOT_EQUITY:
                        continue
                    cat = (c.get("category") or "" if isinstance(c, dict)
                           else "")
                    if cat and not cat.upper().startswith(("EQUIT", "STOCK")):
                        continue
                    seen.add(sym)
                    val_tickers.append(sym)
                    if len(val_tickers) >= 10:
                        break
            except Exception as e:                            # noqa: BLE001
                print(f"\n[valuation] could not parse candidates: {e}")
    if val_tickers:
        ok_v, tail_v = valuation(val_tickers, a.target_pct)
        print(f"\n[valuation] {'OK' if ok_v else 'FAIL'} "
              f"({len(val_tickers)} tickers)\n{tail_v}")
        if not ok_v:
            print("  !! valuation UNVERIFIED - do not treat fundamentals as a "
                  "passing check")
        ok_all &= ok_v
    elif scan_json and a.mode in ("premarket", "allsector", "allpop"):
        # Say so out loud. A silent valuation section reads as "fundamentals
        # checked, nothing wrong" when in fact nothing was checked at all.
        print("\n[valuation] SKIPPED - no equities among the qualified "
              "candidates")
        print("  This universe is macro (ETFs/futures/FX/indices/crypto). The "
              "6-point")
        print("  scorecard does not apply. Fundamentals were NOT verified for "
              "these -")
        print("  judge them on structure, regime and the gate, not on value.")

    # ---- income overlay (ThetaGang-style) ---------------------------------
    # Surface every qualifying asset ALSO as a covered-call / CSP income setup,
    # so scans show "income-able" alongside directional GOs. Observation layer
    # only; the gate remains the only authoriser.
    # Default-ON for equity modes, opt-in for the rest, forced by --income.
    income_default = a.mode in ("premarket", "allsector", "income", "value")
    do_income = (a.income if a.income is not None else income_default)
    if do_income and a.mode != "income":  # income mode handled by its own script
        # candidate symbols: explicit --value, parsed scan file, or valuation set
        inc_syms = list(val_tickers)
        if not inc_syms and scan_json:
            fj = HOME / scan_json
            if fj.exists():
                try:
                    blob = json.loads(fj.read_text(encoding="utf-8"))
                    cands = []
                    for key in ("qualified_longs", "qualified_shorts",
                                "candidates", "results", "tickers"):
                        v = blob.get(key)
                        if isinstance(v, list):
                            cands.extend(v)
                    for c in cands:
                        sym = (c.get("symbol") or c.get("ticker")
                               if isinstance(c, dict) else c)
                        if sym and str(sym).isalpha():
                            inc_syms.append(str(sym).upper())
                except Exception as e:  # noqa: BLE001
                    print(f"\n[income] could not parse scan file: {e}")
        if inc_syms:
            income_rows, n_inc = income_section(inc_syms, dte=a.income_dte,
                                               save=(a.mode in ("premarket", "allsector", "allpop")))
            if n_inc:
                ok_all &= True  # income is informational; never fails the run
        else:
            print("\n[income] no candidate symbols to overlay")

    # ---- the gate is the only authoriser -----------------------------------
    if scan_json and not a.no_gate:
        f = HOME / scan_json
        if not f.exists():
            print(f"\n[gate] SKIPPED - {scan_json} not produced")
            ok_all = False
        else:
            age_h = (now.timestamp() - f.stat().st_mtime) / 3600
            print(f"\n[gate] scan file age {age_h:.1f}h")
            ok_g, tail_g = gate(scan_json, a.equity, a.allow_stale)
            print(f"[gate] {'OK' if ok_g else 'REFUSED/FAIL'}\n{tail_g}")
            # A gate refusal (stale scan, bad data) MUST fail the whole run,
            # otherwise scan.py exits 0 and a cron caller thinks it succeeded.
            ok_all &= ok_g

    print(f"\n{'=' * 74}\nRESULT: {'OK' if ok_all else 'ONE OR MORE STEPS FAILED'}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
