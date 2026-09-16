#!/usr/bin/env python3
"""
Enhanced Trade Gate - Sector-Specific Position Sizing & Risk Management
=======================================================================
Applies Trade Gate validation rules with sector-specific parameters:
- Swing profile: 2.0R floor, 1.5x ATR stop min
- Day profile: 1.5R floor, 0.75-2.0x ATR stop band
- Sector-specific ATR multipliers and risk parameters
"""

import json
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - fallback if tzdata missing
    ZoneInfo = None
from typing import Dict, List, Optional

# Broker-aware cost model (eToro for small/micro caps, Capital.com for the rest).
# Routes setups to the real broker and adjusts R:R for spread/commission/FX/overnight.
try:
    import broker_costs as bc
except Exception:
    bc = None

# =============================================================================
# SECTOR-SPECIFIC PROFILES
# =============================================================================

SECTOR_PROFILES = {
    # Crypto - High volatility
    "crypto": {
        "swing": {"rr_floor": 2.0, "atr_stop_mult": 2.0, "risk_pct": 0.01, "concentration_cap": 0.15},
        "day": {"rr_floor": 1.5, "atr_stop_mult": 1.0, "risk_pct": 0.005, "concentration_cap": 0.10},
    },
    # Forex - Lower volatility, higher leverage
    "forex": {
        "swing": {"rr_floor": 2.0, "atr_stop_mult": 1.5, "risk_pct": 0.01, "concentration_cap": 0.25},
        "day": {"rr_floor": 1.5, "atr_stop_mult": 0.75, "risk_pct": 0.005, "concentration_cap": 0.20},
    },
    # Indices - Medium volatility
    "indices": {
        "swing": {"rr_floor": 2.0, "atr_stop_mult": 1.5, "risk_pct": 0.01, "concentration_cap": 0.20},
        "day": {"rr_floor": 1.5, "atr_stop_mult": 1.0, "risk_pct": 0.005, "concentration_cap": 0.15},
    },
    # Commodities - Varies by type
    "commodities": {
        "swing": {"rr_floor": 2.0, "atr_stop_mult": 1.5, "risk_pct": 0.01, "concentration_cap": 0.20},
        "day": {"rr_floor": 1.5, "atr_stop_mult": 1.0, "risk_pct": 0.005, "concentration_cap": 0.15},
    },
    # Metals (Gold/Silver) - Specific
    "metals": {
        "swing": {"rr_floor": 2.0, "atr_stop_mult": 1.5, "risk_pct": 0.01, "concentration_cap": 0.25},
        "day": {"rr_floor": 1.5, "atr_stop_mult": 0.75, "risk_pct": 0.005, "concentration_cap": 0.20},
    },
    # Energy - High volatility
    "energy": {
        "swing": {"rr_floor": 2.0, "atr_stop_mult": 2.0, "risk_pct": 0.01, "concentration_cap": 0.15},
        "day": {"rr_floor": 1.5, "atr_stop_mult": 1.25, "risk_pct": 0.005, "concentration_cap": 0.10},
    },
    # Bonds/Rates - Low volatility
    "bonds": {
        "swing": {"rr_floor": 2.0, "atr_stop_mult": 1.0, "risk_pct": 0.01, "concentration_cap": 0.30},
        "day": {"rr_floor": 1.5, "atr_stop_mult": 0.5, "risk_pct": 0.005, "concentration_cap": 0.25},
    },
    # ETFs - Sector dependent
    "etfs": {
        "swing": {"rr_floor": 2.0, "atr_stop_mult": 1.5, "risk_pct": 0.01, "concentration_cap": 0.20},
        "day": {"rr_floor": 1.5, "atr_stop_mult": 1.0, "risk_pct": 0.005, "concentration_cap": 0.15},
    },
    # US small-cap equities - higher idiosyncratic risk, wider stops
    "small_cap": {
        "swing": {"rr_floor": 2.0, "atr_stop_mult": 2.0, "risk_pct": 0.01, "concentration_cap": 0.10},
        "day": {"rr_floor": 1.5, "atr_stop_mult": 1.25, "risk_pct": 0.005, "concentration_cap": 0.10},
    },
    # US micro-cap / penny equities - very high idiosyncratic + liquidity risk
    "micro_cap": {
        "swing": {"rr_floor": 2.0, "atr_stop_mult": 2.5, "risk_pct": 0.01, "concentration_cap": 0.03},
        "day": {"rr_floor": 1.5, "atr_stop_mult": 1.5, "risk_pct": 0.005, "concentration_cap": 0.03},
    },
    # Generic equity/stocks alias
    "equity": {
        "swing": {"rr_floor": 2.0, "atr_stop_mult": 1.5, "risk_pct": 0.01, "concentration_cap": 0.15},
        "day": {"rr_floor": 1.5, "atr_stop_mult": 1.0, "risk_pct": 0.005, "concentration_cap": 0.10},
    },
    # Futures - Leveraged
    "futures": {
        "swing": {"rr_floor": 2.0, "atr_stop_mult": 1.5, "risk_pct": 0.01, "concentration_cap": 0.15},
        "day": {"rr_floor": 1.5, "atr_stop_mult": 0.75, "risk_pct": 0.005, "concentration_cap": 0.10},
    },
    # MOONSHOT / 100x asymmetric profile - for microcaps that can 100x.
    # Goodman's rule: tiny size, let winners run, wide stop. NO liquidity floor
    # (microcaps are low-volume by definition). Requires HIGH R:R to justify the
    # low hit-rate. Use ONLY in moonshot scan mode (not the default gate).
    "moonshot": {
        "swing": {"rr_floor": 3.0, "atr_stop_mult": 2.5, "risk_pct": 0.005, "concentration_cap": 0.01,
                  "no_liquidity_floor": True, "min_bars": 60, "trailing": True},
        "day": {"rr_floor": 2.0, "atr_stop_mult": 1.5, "risk_pct": 0.002, "concentration_cap": 0.01,
                "no_liquidity_floor": True, "min_bars": 60, "trailing": True},
    },
}

# Default fallback
DEFAULT_PROFILE = {
    "swing": {"rr_floor": 2.0, "atr_stop_mult": 1.5, "risk_pct": 0.01, "concentration_cap": 0.20},
    "day": {"rr_floor": 1.5, "atr_stop_mult": 1.0, "risk_pct": 0.005, "concentration_cap": 0.15},
}

# Symbol to sub-category mapping for finer control
SYMBOL_SUB_CATEGORY = {
    # Metals
    "GC": "metals", "SI": "metals", "PL": "metals", "PA": "metals", "HG": "metals",
    "GLD": "metals", "SLV": "metals", "PPLT": "metals", "PALL": "metals",
    # Energy
    "CL": "energy", "BZ": "energy", "NG": "energy", "HO": "energy", "RB": "energy",
    "USO": "energy", "UNG": "energy", "XLE": "energy",
    # Bonds
    "TLT": "bonds", "IEF": "bonds", "SHY": "bonds", "LQD": "bonds", "HYG": "bonds", "TIP": "bonds", "SHV": "bonds",
    "ZB": "bonds", "ZN": "bonds", "ZF": "bonds", "ZT": "bonds",
    # FX Futures
    "6E": "forex", "6J": "forex", "6B": "forex", "6A": "forex", "6C": "forex",
}

def get_sector_profile(category: str, symbol: str = "", profile_type: str = "swing") -> dict:
    """Get sector-specific profile for risk management"""
    # Check symbol-specific sub-category first
    for key, sub_cat in SYMBOL_SUB_CATEGORY.items():
        if symbol.startswith(key) or symbol == key:
            if sub_cat in SECTOR_PROFILES and profile_type in SECTOR_PROFILES[sub_cat]:
                return SECTOR_PROFILES[sub_cat][profile_type]
    
    # Fall back to category
    if category in SECTOR_PROFILES and profile_type in SECTOR_PROFILES[category]:
        return SECTOR_PROFILES[category][profile_type]
    
    return DEFAULT_PROFILE.get(profile_type, DEFAULT_PROFILE["swing"])


# Asset class specific liquidity floors (ADV shares, Dollar Volume)
LIQUIDITY_FLOORS = {
    "crypto": {"adv": 100_000, "dollar_volume": 10_000_000},  # High volume but in tokens
    "forex": {"adv": 1_000_000, "dollar_volume": 50_000_000},  # Notional volume
    "indices": {"adv": 1_000_000, "dollar_volume": 100_000_000},  # Index futures/ETFs
    "commodities": {"adv": 5_000, "dollar_volume": 5_000_000},  # Futures contracts
    "metals": {"adv": 5_000, "dollar_volume": 5_000_000},
    "energy": {"adv": 5_000, "dollar_volume": 10_000_000},
    "bonds": {"adv": 10_000, "dollar_volume": 10_000_000},  # Bond ETFs/futures - lowered
    "etfs": {"adv": 500_000, "dollar_volume": 10_000_000},  # ETFs
    "small_cap": {"adv": 250_000, "dollar_volume": 2_000_000},  # Thin small caps - lower floor
    "micro_cap": {"adv": 50_000, "dollar_volume": 200_000},  # Penny stocks - minimal floor
    "equity": {"adv": 500_000, "dollar_volume": 10_000_000},  # Generic equities
    "futures": {"adv": 1_000, "dollar_volume": 1_000_000},  # Futures - much lower ADV in contracts
    "rates": {"adv": 1_000, "dollar_volume": 1_000_000},  # Rate futures
}

DEFAULT_LIQUIDITY = {"adv": 100_000, "dollar_volume": 10_000_000}


# =============================================================================
# SCAN-TIME RTH + MACRO-EVENT EMBARGO GATES  (Part 1.1 / 4.4 / 3.6)
# These are SCAN-ONLY downgrade checks: they turn a candidate into NO-GO but
# never abort the scan. We are a scan/setup desk, not an execution desk.
# =============================================================================

# Equities & ETFs must only be traded inside US Regular Trading Hours.
# Premarket signals are gated OUT (guide: equities entry quality issues
# premarket -> RTH gating adopted). 9:30-16:00 ET.
_RTH_WINDOW_UTC = (13, 30, 20, 0)

# Macro events where the firm STOPS DRAFTING ENTRIES (embargo: entries blocked,
# exits never gated). This is the calendar-class macro set. Per-symbol earnings
# embargo is supplied via the `embargo_dates` kwarg / scan file.
_MACRO_EMBARGO_LABELS = {
    (1, 27): "FOMC", (3, 17): "FOMC", (4, 28): "FOMC", (6, 9): "FOMC",
    (7, 28): "FOMC", (9, 15): "FOMC", (10, 27): "FOMC", (12, 8): "FOMC",
}


def _parse_ts(scan_timestamp):
    """Return a timezone-aware UTC datetime from a scan stamp, or None."""
    if not scan_timestamp:
        return None
    try:
        s = str(scan_timestamp).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _in_rth_utc(dt: datetime) -> bool:
    """True if dt (UTC) falls inside US Regular Trading Hours (9:30-16:00 ET),
    DST-correct via zoneinfo. Absent a timestamp -> True (cannot judge; do not
    block)."""
    if dt is None:
        return True
    if dt.weekday() >= 5:  # Sat/Sun: no RTH
        return False
    try:
        et = dt.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        # Fallback to the fixed standard-time window if tz data is missing.
        t = dt.hour * 60 + dt.minute
        open_h, open_m, close_h, close_m = _RTH_WINDOW_UTC
        return (open_h * 60 + open_m) <= t < (close_h * 60 + close_m)
    minutes = et.hour * 60 + et.minute
    return (9 * 60 + 30) <= minutes < (16 * 60)


def _stat_verdict_ok(symbol: str, stat: dict) -> tuple:
    """H11: statistical-significance gate (Part 5.2/5.3).

    Returns (ok, note). `stat` (optional per-candidate key, e.g. from a Colossus
    / grading verdict store) must carry either an absolute t-stat or a verdict
    string. We treat the guide's funding bar |t| >= 2.5 as authoritative.

    When NO statistical evidence is attached for the symbol, we do NOT block the
    scan (scan-only desk) — we downgrade the candidate and flag it so a human sees
    "not yet validated," matching the guide's NO-MAGIC-DUST / prove-before-trust
    discipline without silently authorizing unvalidated setups.
    """
    if not stat:
        return None, "no statistical verdict attached for symbol (NO-MAGIC-DUST: unvalidated)"
    # Accept either a numeric t-stat or a textual verdict.
    t = stat.get("abs_t") if "abs_t" in stat else stat.get("t_stat")
    try:
        t = float(t)
    except (TypeError, ValueError):
        t = None
    verdict = str(stat.get("verdict", "")).upper()
    if t is not None:
        if t >= 2.5:
            return True, f"|t|={t:.2f} >= 2.5 (validated)"
        return False, f"|t|={t:.2f} < 2.5 funding bar (not validated)"
    if verdict in ("CONFIRMED", "ESTABLISHED", "GO"):
        return True, f"verdict={verdict} (validated)"
    if verdict in ("NOT ESTABLISHED", "NULL", "NO-GO", "REJECT"):
        return False, f"verdict={verdict} (not validated)"
    # verdict present but unrecognized -> treat as unvalidated, flag only
    return None, f"verdict={verdict!r} unrecognized (NO-MAGIC-DUST: unvalidated)"


def _macro_embargo_active(dt: datetime, embargo_dates=None) -> str:
    """Return an embargo label if the scan time is inside a macro blackout."""
    if dt is None:
        return ""
    embargo_dates = embargo_dates or []
    for d in embargo_dates:
        try:
            ev = datetime.fromisoformat(str(d)).astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
        if ev.date() == dt.date():
            return "EARNINGS/EMBARGO"
    key = (dt.month, dt.day)
    if key in _MACRO_EMBARGO_LABELS:
        return _MACRO_EMBARGO_LABELS[key]
    return ""


def get_liquidity_floors(category: str, symbol: str = "") -> dict:
    """Get asset-class specific liquidity floors"""
    # Check symbol-specific sub-category first
    for key, sub_cat in SYMBOL_SUB_CATEGORY.items():
        if symbol.startswith(key) or symbol == key:
            if sub_cat in LIQUIDITY_FLOORS:
                return LIQUIDITY_FLOORS[sub_cat]
    
    if category in LIQUIDITY_FLOORS:
        return LIQUIDITY_FLOORS[category]
    
    return DEFAULT_LIQUIDITY


@dataclass
class TradeSetup:
    """Complete trade setup with entry, stop, targets, position size"""
    symbol: str
    name: str
    category: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    risk_per_share: float
    reward_1: float
    reward_2: float
    reward_3: float
    rr_1: float
    rr_2: float
    rr_3: float
    atr: float
    atr_stop_mult: float
    position_size_pct: float  # % of account
    shares_per_account: float  # shares per $1 of account
    dollar_risk_per_account: float  # $ risk per $1 of account
    conviction_score: float
    vwap_distance_pct: float
    rsi: float
    ema20: float
    ema50: float
    trend: str
    profile_used: str
    sector_profile: dict
    validation: dict  # Trade Gate validation result
    sentiment_conviction: str = ""     # fresh-sentiment conviction adjustment note
    pms_conviction: str = ""         # prediction-market (Kalshi/Polymarket) conviction note
    conviction_rails: str = ""       # COMBINED tech+news+social+PM confluence (1 line)
    confluence_score: float = None    # signed aggregate of the 4 rails (-4..+4)
    base_score: float = None         # conviction before sentiment adjustment


def _load_pms_doc():
    """Load prediction_sentiment_latest.json (cached). Returns dict or {}.

    Readiness: if the file is missing (it is NOT auto-refreshed by every scan
    orchestrator -- only the post-scan confirm + a manual --report write it),
    BUILD A FRESH PM doc on the fly so the gate's 5th-rail PM contribution is
    never silently empty at the authoritative gate moment. Honesty: a build
    failure still returns {} (PM rail = n/a, never a fake)."""
    import pathlib as _pl
    p = _pl.Path.home() / "prediction_sentiment_latest.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Missing or unreadable -> build fresh so the PM rail is populated.
    try:
        import prediction_sentiment as _pms
        return _pms.build(_pms.DEFAULT_UNIVERSE)
    except Exception:
        return {}


_PMS_DOC = None  # module-level cache, set on first gate run


def conviction_rails(symbol, side, news_bias="NEUTRAL", social_lean="NEUTRAL",
                     category="CRYPTO"):
    """Compute the 5-rail conviction (tech + news + social + prediction-market)
    for ONE asset. Returns (score:int|None, rails_str:str, pms_note:str).

    Display-only -- never auto-bumps a gate tier. Used by both
    calculate_trade_setup (forex/metals/cron-allsector scans) AND
    run_trade_gate_resilient (the day/all-sector scan) so every gate verdict
    carries the news + PM correlation, not just the technical read.

    Order is fixed: tech (side) -> news (bias) -> social (lean) -> PM (lean),
    with PM LAST as the confirming/conflict layer. Unknown rails count as 0
    (not a pass); conflicts shown explicitly. Honesty: if the PM doc can't load,
    returns (None, '[?] rails unavailable', ...) -- never a neutral fake.
    """
    try:
        def _sign(v):
            return {"LONG": 1, "UP": 1, "CONSTRUCTIVE": 1,
                    "SHORT": -1, "DOWN": -1, "CAUTION": -1}.get(v, 0)

        _side = str(side).upper()
        _news = str(news_bias).upper()
        _social = str(social_lean).upper()
        _rails = [_sign(_side), _sign(_news), _sign(_social)]
        _tags = [f"tech={_side}", f"news={_news}", f"social={_social}"]
        # PM contribution: per-symbol lean, else book-level macro regime.
        global _PMS_DOC
        if _PMS_DOC is None:
            _PMS_DOC = _load_pms_doc()
        assets = (_PMS_DOC or {}).get("assets", {})
        macro = (_PMS_DOC or {}).get("macro_regime")
        pms_sig = assets.get(symbol.upper()) or assets.get(symbol)
        if not pms_sig:
            pms_sig = {"symbol": symbol, "status": "NO_MARKET", "lean": "NONE",
                       "prob": None, "raw": None, "note": "no per-symbol market",
                       "confidence": "NONE"}
        _pm_sign = 0
        _pm_tag = "pms=n/a"
        if pms_sig.get("status") == "OK" and pms_sig.get("lean") in ("UP", "DOWN"):
            _pm_sign = _sign(pms_sig["lean"])
            _pm_tag = f"pms={pms_sig['lean']}"
        elif macro:
            _ml = [mv.get("lean") for mv in macro.values()
                   if mv.get("lean") in ("UP", "DOWN")]
            if _ml:
                _pm_sign = 1 if _ml.count("UP") >= _ml.count("DOWN") else -1
                _pm_tag = f"pms=macro({_ml.count('UP')}L/{_ml.count('DOWN')}S)"
        _rails.append(_pm_sign)
        _tags.append(_pm_tag)
        _conflict = (_side in ("LONG", "SHORT") and _pm_sign
                     and _sign(_side) != _pm_sign
                     and pms_sig.get("confidence") in ("HIGH", "MED"))
        _score = sum(_rails)
        _confluence = f"[{_score:+d}] " + " ".join(_tags)
        if _conflict:
            _confluence += " CONFLICT"
        _pms_note = (f"PMS: {symbol} Yes={pms_sig['prob']:.2f} "
                     f"({pms_sig['lean']}, conf={pms_sig.get('confidence')})"
                     if pms_sig.get("prob") is not None
                     else f"PMS: {symbol} ({pms_sig.get('status')})")
        return _score, _confluence, _pms_note
    except Exception:
        return None, "[?] rails unavailable", "PMS: unavailable (error)"


def calculate_trade_setup(
    trade_data: dict,
    profile_type: str = "swing",
    account_equity: float = None,
    scan_timestamp=None,
    embargo_dates=None,
    stat=None,
) -> TradeSetup:
    """
    Calculate complete trade setup using sector-specific Trade Gate rules
    """
    symbol = trade_data.get("symbol", "")
    name = trade_data.get("name", "")
    category = trade_data.get("asset_class", trade_data.get("category", "unknown"))
    side = trade_data.get("type", trade_data.get("side", "LONG")).upper()
    price = trade_data.get("price", trade_data.get("entry_price", 0))
    atr = trade_data.get("atr", 0)
    rsi = trade_data.get("rsi", 50)
    vwap_dist = trade_data.get("vwap_distance_pct", 0)
    ema20 = trade_data.get("ema20", 0)
    ema50 = trade_data.get("ema50", 0)
    trend = trade_data.get("trend", "neutral")
    conviction = trade_data.get("long_score", trade_data.get("short_score", trade_data.get("conviction", 0.5)))

    # --- prediction-market sentiment (Kalshi/Polymarket) as a conviction input --
    # Mirrors sentiment_conviction: DISPLAY-ONLY. We correlate the asset's live
    # PM odds against the technical side + (best-effort) news/social bias, and
    # attach a note. It never auto-bumps a gate tier -- agreement/conflict is
    # shown so the human can weigh it. Honesty: no market -> "PMS: NO MARKET".
    pms_conv_note = ""
    try:
        global _PMS_DOC
        if _PMS_DOC is None:
            _PMS_DOC = _load_pms_doc()
        assets = (_PMS_DOC or {}).get("assets", {})
        macro = (_PMS_DOC or {}).get("macro_regime")
        pms_sig = assets.get(symbol.upper()) or assets.get(symbol)
        if not pms_sig:
            # No per-symbol market. Still surface the book-level macro regime.
            pms_sig = {"symbol": symbol, "status": "NO_MARKET", "lean": "NONE",
                       "prob": None, "raw": None, "note": "no per-symbol market"}
        news_bias = str(trade_data.get("news_bias", "NEUTRAL"))
        social_lean = str(trade_data.get("social_lean", "NEUTRAL"))
        corr = __import__("prediction_sentiment").correlate(
            side, news_bias, social_lean, pms_sig, macro)
        pms_conv_note = corr.get("text", "")
    except Exception:
        pms_conv_note = "PMS: unavailable (import/parse error)"

    # --- COMBINED conviction rails (5th aggregation column) ---------------
    # Aggregates the four conviction inputs into ONE signed score + one line:
    #   tech (side) + news (bias) + social (lean) + prediction-market (lean).
    # Display-only (never auto-bumps a gate tier). Honesty: unknown rails count
    # as 0, not as a pass; conflicts are shown explicitly.
    try:
        def _sign(v):
            return {"LONG": 1, "UP": 1, "CONSTRUCTIVE": 1,
                    "SHORT": -1, "DOWN": -1, "CAUTION": -1}.get(v, 0)

        _news = str(trade_data.get("news_bias", "NEUTRAL"))
        _social = str(trade_data.get("social_lean", "NEUTRAL"))
        _rails = [_sign(side), _sign(_news), _sign(_social)]
        _rail_tags = [f"tech={side}", f"news={_news}", f"social={_social}"]
        # PM contribution: per-symbol lean, else book-level macro regime.
        _pm_sign = 0
        _pm_tag = "pms=n/a"
        if pms_sig and pms_sig.get("status") == "OK" and pms_sig.get("lean") in ("UP", "DOWN"):
            _pm_sign = _sign(pms_sig["lean"])
            _pm_tag = f"pms={pms_sig['lean']}"
        elif macro:
            _ml = [mv.get("lean") for mv in macro.values()
                   if mv.get("lean") in ("UP", "DOWN")]
            if _ml:
                _pm_sign = 1 if _ml.count("UP") >= _ml.count("DOWN") else -1
                _pm_tag = f"pms=macro({_ml.count('UP')}L/{_ml.count('DOWN')}S)"
        _rails.append(_pm_sign)
        _rail_tags.append(_pm_tag)
        _conflict = (side in ("LONG", "SHORT") and _pm_sign
                     and _sign(side) != _pm_sign
                     and pms_sig.get("confidence") in ("HIGH", "MED"))
        _score = sum(_rails)
        _confluence = f"[{_score:+d}] " + " ".join(_rail_tags)
        if _conflict:
            _confluence += " CONFLICT"
    except Exception:
        _confluence = "[?] rails unavailable"
        _score = None
    # Get sector-specific profile
    sector_profile = get_sector_profile(category, symbol, profile_type)
    
    rr_floor = sector_profile["rr_floor"]
    atr_stop_mult = sector_profile["atr_stop_mult"]
    risk_pct = sector_profile["risk_pct"]
    concentration_cap = sector_profile["concentration_cap"]
    no_liquidity_floor = sector_profile.get("no_liquidity_floor", False)
    moonshot_min_bars = sector_profile.get("min_bars", 250)
    trailing = sector_profile.get("trailing", False)
    
    # Calculate stop distance (ATR-based with minimum %)
    min_stop_pct = 0.02 if category != "bonds" else 0.005  # 2% min, 0.5% for bonds
    stop_dist_atr = atr * atr_stop_mult
    stop_dist_pct = price * min_stop_pct
    stop_dist = max(stop_dist_atr, stop_dist_pct)
    
    # Calculate stop and targets based on side
    if side == "LONG":
        stop_loss = price - stop_dist
        # TP1 at rr_floor * risk, TP2 at 1.5 * rr_floor * risk, TP3 at 2.5 * rr_floor * risk
        tp1 = price + (stop_dist * rr_floor)
        tp2 = price + (stop_dist * rr_floor * 1.5)
        tp3 = price + (stop_dist * rr_floor * 2.5)
    else:  # SHORT
        stop_loss = price + stop_dist
        tp1 = price - (stop_dist * rr_floor)
        tp2 = price - (stop_dist * rr_floor * 1.5)
        tp3 = price - (stop_dist * rr_floor * 2.5)
    
    # Risk/reward calculations
    risk_per_share = abs(price - stop_loss)
    reward_1 = abs(tp1 - price)
    reward_2 = abs(tp2 - price)
    reward_3 = abs(tp3 - price)
    rr_1 = reward_1 / risk_per_share if risk_per_share > 0 else 0
    rr_2 = reward_2 / risk_per_share if risk_per_share > 0 else 0
    rr_3 = reward_3 / risk_per_share if risk_per_share > 0 else 0
    
    # Position sizing (account-agnostic - fractions of account)
    # Risk notional fraction = (risk_pct * entry) / risk_per_share
    risk_notional_frac = (risk_pct * price) / risk_per_share if risk_per_share > 0 else 0
    deploy_frac = min(risk_notional_frac, concentration_cap)
    binding = "risk" if risk_notional_frac <= concentration_cap else "concentration"
    max_loss_frac = (deploy_frac * risk_per_share) / price
    shares_per_acct = deploy_frac / price
    
    # Live share count if account provided
    shares = dollar_risk = notional = notional_pct = pct_risk = None
    if account_equity and account_equity > 0:
        shares = math.floor((deploy_frac * account_equity) / price)
        dollar_risk = shares * risk_per_share
        notional = shares * price
        pct_risk = dollar_risk / account_equity
        notional_pct = notional / account_equity
    
    # Trade Gate style validation
    validation = validate_trade_gate(
        symbol=symbol,
        side=side.lower(),
        entry=price,
        stop=stop_loss,
        targets=[tp1, tp2, tp3],
        atr14=atr,
        atr_timeframe="1d" if profile_type == "swing" else "5m",
        stop_floor_driven=(stop_dist_pct >= stop_dist_atr),
        adv=trade_data.get("avg_volume_20", 1_000_000),
        # NOTE: the nightshift/scan producers emit `volume` in UNITS (tokens /
        # shares / contracts), NOT dollar volume. Derive dollar volume as
        # price * volume when the scan did not supply an explicit `dollar_volume`,
        # so the liquidity floor compares like-for-like (the gate's H6 floor is
        # expressed in dollars). Avoids spurious liquidity fails on crypto.
        # MOONSHOT OVERRIDE: when no_liquidity_floor is set (microcaps that can
        # 100x are low-volume by definition), pass huge adv/dollar_volume so the
        # H6 liquidity hard-check is bypassed. The risk is managed by the tiny
        # concentration_cap (1%) instead — Goodman's small-size rule.
        dollar_volume=(10**18 if no_liquidity_floor else
                       (trade_data.get("dollar_volume")
                        if trade_data.get("dollar_volume") else
                        round(price * float(trade_data.get("volume", 0) or 0), 2))),
        ema20=ema20,
        structure_level=trade_data.get("structure_level", price - atr if side == "LONG" else price + atr),
        structure_type="oversold pullback support" if side == "LONG" else "overbought resistance",
        catalyst=f"Sector scan {side} setup; RSI {rsi:.1f}, VWAP {vwap_dist:+.2f}%",
        accurate_structure=f"Price {'below' if side == 'LONG' else 'above'} VWAP ({vwap_dist:+.2f}%), RSI {rsi:.1f}, entering on {'oversold flush' if side == 'LONG' else 'overbought extension'}",
        profile=profile_type,
        account_equity=account_equity,
        conviction_tier=trade_data.get("conviction_tier", "watch"),
        horizon=profile_type,
        category=category,
        scan_timestamp=scan_timestamp,
        embargo_dates=trade_data.get("embargo_dates", embargo_dates),
        stat=trade_data.get("stat_verdict") or (stat.get(symbol) if isinstance(stat, dict) else stat),
    )
    
    return TradeSetup(
        symbol=symbol,
        name=name,
        category=category,
        side=side,
        entry_price=price,
        stop_loss=stop_loss,
        take_profit_1=tp1,
        take_profit_2=tp2,
        take_profit_3=tp3,
        risk_per_share=risk_per_share,
        reward_1=reward_1,
        reward_2=reward_2,
        reward_3=reward_3,
        rr_1=rr_1,
        rr_2=rr_2,
        rr_3=rr_3,
        atr=atr,
        atr_stop_mult=atr_stop_mult,
        position_size_pct=deploy_frac * 100,
        shares_per_account=shares_per_acct,
        dollar_risk_per_account=max_loss_frac,
        conviction_score=conviction,
        vwap_distance_pct=vwap_dist,
        rsi=rsi,
        ema20=ema20,
        ema50=ema50,
        trend=trend,
        profile_used=profile_type,
        sector_profile=sector_profile,
        validation=validation,
        sentiment_conviction=trade_data.get("sentiment_conviction", ""),
        pms_conviction=pms_conv_note,
        conviction_rails=_confluence,
        confluence_score=_score,
    )


def validate_trade_gate(
    symbol: str,
    side: str,
    entry: float,
    stop: float,
    targets: list,
    atr14: float,
    atr_timeframe: str,
    adv: float,
    dollar_volume: float,
    ema20: float,
    structure_level: float,
    structure_type: str,
    catalyst: str,
    accurate_structure: str,
    profile: str = "swing",
    account_equity: float = None,
    conviction_tier: str = "watch",
    horizon: str = "swing",
    category: str = "unknown",
    stop_floor_driven: bool = False,
    scan_timestamp=None,
    embargo_dates=None,
    stat=None,
) -> dict:
    """
    Run Trade Gate validation (mirrors validate_gate.py logic)
    """
    # Profile configs
    PROFILES = {
        "swing": {
            "rr_floor": 2.0, "atr_stop_mult_min": 1.5, "atr_stop_mult_max": None,
            "risk_pct_target": 0.01, "risk_pct_ceiling": 0.02, "concentration_cap": 0.25,
            "ext_atr_mult": 2.0,
        },
        "day": {
            "rr_floor": 1.5, "atr_stop_mult_min": 0.75, "atr_stop_mult_max": 2.0,
            "risk_pct_target": 0.01, "risk_pct_ceiling": 0.02, "concentration_cap": 0.20,
            "ext_atr_mult": 2.0,
            "slippage_tiers": [(0.50, 0.05), (1.00, 0.02), (3.00, 0.010), (5.00, 0.005)],
        },
    }
    
    cfg = PROFILES.get(profile, PROFILES["swing"])
    fails = []
    flags = []
    
    # Get asset-class specific liquidity floors
    liq_floors = get_liquidity_floors(category, symbol)
    min_adv = liq_floors["adv"]
    min_dollar_vol = liq_floors["dollar_volume"]
    
    t1 = targets[0] if targets else entry
    
    # Slippage adjustment (day profile only)
    slip = 0.0
    if profile == "day" and cfg.get("slippage_tiers"):
        for price_ceiling, pct in cfg["slippage_tiers"]:
            if entry <= price_ceiling:
                slip = pct
                break
    
    if slip:
        if side == "long":
            real_entry, real_t1 = entry * (1 + slip), t1 * (1 - slip)
        else:
            real_entry, real_t1 = entry * (1 - slip), t1 * (1 + slip)
    else:
        real_entry, real_t1 = entry, t1
    
    rps = abs(real_entry - stop)
    reward = abs(real_t1 - real_entry)
    quoted_rps = abs(entry - stop)
    quoted_reward = abs(t1 - entry)
    
    if rps <= 0:
        return {"verdict": "NO-GO", "binding_reason": "risk per share is zero", "hard": {}, "metrics": {}}
    
    rr = reward / rps
    quoted_rr = quoted_reward / quoted_rps if quoted_rps > 0 else 0
    
    # H1: R:R floor (epsilon-tolerant so a gross R:R that lands exactly on the
    # floor — e.g. 2.00 vs 2.0 — clears instead of failing on float rounding)
    h1 = rr + 1e-9 >= cfg["rr_floor"]
    if not h1:
        msg = f"R:R to T1 is {rr:.2f}, floor is {cfg['rr_floor']:.1f}"
        if slip:
            msg += f" (after {slip*100:.1f}% slippage/side; quoted {quoted_rr:.2f})"
        fails.append(msg)
    
    # Tier target check
    tier_targets = {"overweight": 3.0, "watch+": 2.5, "watch": 2.0, "watch-": 2.0,
                    "prime": 2.5, "strong": 2.0, "good": 1.5}
    if conviction_tier in tier_targets and rr < tier_targets[conviction_tier]:
        flags.append(f"R:R {rr:.2f} below {conviction_tier} target {tier_targets[conviction_tier]:.1f} (above floor)")
    
    # H2: Stop band
    atr_mult = rps / atr14 if atr14 > 0 else 0
    h2 = rps >= cfg["atr_stop_mult_min"] * atr14 - 1e-9
    if not h2:
        fails.append(f"stop is {atr_mult:.2f}x ATR, needs >= {cfg['atr_stop_mult_min']:.2f}x ({atr_timeframe} ATR — inside the noise)")
    if cfg.get("atr_stop_mult_max") and not stop_floor_driven and rps > cfg["atr_stop_mult_max"] * atr14 + 1e-9:
        h2 = False
        fails.append(f"stop is {atr_mult:.2f}x ATR, exceeds {cfg['atr_stop_mult_max']:.2f}x ({atr_timeframe} ATR — too wide)")
    
    # H3/H4: Sizing (account-agnostic)
    risk_notional_frac = (cfg["risk_pct_target"] * real_entry) / rps if rps > 0 else 0
    deploy_frac = min(risk_notional_frac, cfg["concentration_cap"])
    binding = "risk" if risk_notional_frac <= cfg["concentration_cap"] else "concentration"
    max_loss_frac = (deploy_frac * rps) / real_entry if real_entry > 0 else 0
    shares_per_acct = deploy_frac / real_entry if real_entry > 0 else 0
    
    h3 = max_loss_frac <= cfg["risk_pct_ceiling"] + 1e-12
    h4 = deploy_frac <= cfg["concentration_cap"] + 1e-9
    if not h3:
        fails.append(f"max loss {max_loss_frac*100:.2f}% exceeds {cfg['risk_pct_ceiling']*100:.0f}% ceiling")
    if not h4:
        fails.append(f"deploy {deploy_frac*100:.0f}% exceeds {cfg['concentration_cap']*100:.0f}% cap")
    
    # H5: Earnings (placeholder - would need earnings calendar)
    h5 = True
    flags.append("no earnings_date supplied — verify before entry")
    
    # H6: Liquidity (using asset-class specific floors)
    # yfinance does not report volume for some instrument classes (FX '=X'
    # pairs return volume 0; cash indices '^' return 0 dollar volume). A zero
    # reading is a DATA GAP, not evidence of illiquidity — failing the trade on
    # a missing field would wrongly kill the most liquid markets. Treat 0 as
    # "not reported" (flag + pass) and let a manual liquidity check decide.
    # For futures/contract classes (metals, commodities, energy, bonds) yfinance
    # understates contract volume; if the floor is missed there, flag for
    # verification on the real contract rather than hard-rejecting the signal.
    if dollar_volume <= 0:
        h6 = True
        flags.append("liquidity not reported by data source (yfinance volume=0) — verify manually")
    elif category in ("metals", "commodities", "energy", "bonds") and (adv < min_adv or dollar_volume < min_dollar_vol):
        h6 = True
        flags.append(f"liquidity floor missed on likely-understated yfinance volume (ADV {adv:,.0f}; $vol {dollar_volume:,.0f}) — verify on real contract")
    else:
        h6 = adv >= min_adv and dollar_volume >= min_dollar_vol
        if not h6:
            fails.append(f"liquidity below {profile} floor for {category} (ADV {adv:,.0f} need {min_adv:,.0f}; $vol {dollar_volume:,.0f} need {min_dollar_vol:,.0f})")
    
    # H7: Extension (anti-chase)
    h7 = True
    ext = None
    if ema20 and ema20 > 0 and atr14 and atr14 > 0:
        ext = (real_entry - ema20) / atr14 if side == "long" else (ema20 - real_entry) / atr14
        h7 = ext <= cfg["ext_atr_mult"] + 1e-9
        if not h7:
            fails.append(f"entry is {ext:.2f}x ATR beyond the 20-EMA, max {cfg['ext_atr_mult']:.1f}x ({atr_timeframe} — chasing/extended)")
    else:
        flags.append(f"no ema20/atr supplied - extension/chase not checked")

    # H8: broker-cost NET R:R (eToro for small/micro caps, Capital.com otherwise)
    h8 = True
    net_rr = None
    broker = sess = None
    if bc is not None:
        broker = bc.broker_for(category)
        sess = bc.session_for(category)
        cost_demo = {
            "price": float(entry),
            "stop_loss": float(stop),
            "stop_loss_short": float(stop),
            "take_profit_1": float(targets[0]) if targets else float(entry),
            "take_profit_1_short": float(targets[0]) if targets else float(entry),
            "take_profit_2": float(targets[1]) if len(targets) > 1 else float(entry),
            "take_profit_2_short": float(targets[1]) if len(targets) > 1 else float(entry),
            "rr": rr,
            "rr_short": rr,
        }
        bc.adjust_setup(cost_demo, side.upper(), category, profile)
        net_rr = cost_demo.get("net_rr")
        if net_rr is not None and net_rr < cfg["rr_floor"]:
            h8 = False
            fails.append(
                f"net R:R after {broker} costs is {net_rr:.2f}, floor {cfg['rr_floor']:.1f} "
                f"(gross {rr:.2f}; spread {cost_demo.get('spread_frac',0)*100:.2f}%)"
            )

    # H9: RTH gate for equities/ETFs (Part 1.1 / 4.4). Scan-only desk: this
    # downgrades a candidate to NO-GO outside US regular hours; it never aborts
    # the scan. Absent a scan timestamp we cannot judge, so it passes (do not
    # silently block on a missing field).
    h9 = True
    _scan_dt = _parse_ts(scan_timestamp)
    if category in ("equity", "etfs", "small_cap", "micro_cap"):
        if _scan_dt is not None and not _in_rth_utc(_scan_dt):
            h9 = False
            fails.append(
                f"equity/ETF candidate outside RTH "
                f"({_scan_dt:%Y-%m-%d %H:%M}Z) — entry gated; re-scan in 13:30-20:00 ET"
            )

    # H10: Macro-event embargo (Part 3.6). Entries are barred through scheduled
    # macro prints (FOMC/CPI) and per-symbol earnings dates; exits are never
    # gated. Scan-only: downgrade to NO-GO, never abort the run.
    h10 = True
    _embargo = _macro_embargo_active(_scan_dt, embargo_dates)
    if _embargo:
        h10 = False
        fails.append(f"macro-event embargo active ({_embargo}) — entries blocked, exits unaffected")

    # H11: Statistical-significance gate (Part 5.2/5.3). When a verdict/t-stat is
    # attached for the symbol we enforce the |t|>=2.5 funding bar. When NONE is
    # attached we do NOT block the scan (scan-only desk) — we mark the candidate
    # UNVALIDATED and downgrade it to NO-GO so unvalidated setups are never
    # silently authorized (NO-MAGIC-DUST). A validated pass is required for GO.
    h11 = True
    _stat_ok, _stat_note = _stat_verdict_ok(symbol, stat)
    if _stat_ok is False:
        h11 = False
        fails.append(f"statistical significance: {_stat_note}")
    elif _stat_ok is None:
        # Unvalidated (no evidence on file): downgrade to NO-GO, but record it
        # in `fails` so binding_reason works and the scan never crashes. Keep the
        # human-readable flag too. Never abort the scan.
        h11 = False
        fails.append(f"UNVALIDATED: {_stat_note}")
        flags.append(f"UNVALIDATED: {_stat_note}")

    hard = {
        "H1_rr": h1, "H2_stop": h2, "H3_size": h3, "H4_conc": h4,
        "H5_earn": h5, "H6_liq": h6, "H7_ext": h7, "H8_net_cost": h8,
        "H9_rth": h9, "H10_embargo": h10, "H11_stat": h11,
    }
    
    # Live shares if account provided
    shares = dollar_risk = notional = notional_pct = pct_risk = None
    if account_equity and account_equity > 0:
        shares = math.floor((deploy_frac * account_equity) / real_entry)
        dollar_risk = shares * rps
        notional = shares * real_entry
        pct_risk = dollar_risk / account_equity
        notional_pct = notional / account_equity
        if shares == 0:
            fails.append("computed size is 0 shares at the supplied account")
    
    metrics = {
        "rr": round(rr, 2), "quoted_rr": round(quoted_rr, 2), "slippage_pct": round(slip * 100, 2),
        "atr_mult": round(atr_mult, 2),
        "risk_pct": round(cfg["risk_pct_target"] * 100, 2),
        "deploy_pct": round(deploy_frac * 100, 2),
        "binding": binding,
        "max_loss_pct": round(max_loss_frac * 100, 2),
        "shares_per_acct": round(shares_per_acct, 6),
        "shares_formula": f"{deploy_frac:.2f} × Acct ÷ ${real_entry:.2f}",
        "rps": round(rps, 4), "reward_to_t1": round(reward, 4),
        "real_entry": round(real_entry, 4), "real_t1": round(real_t1, 4),
        "ext_atr": round(ext, 2) if ext is not None else None,
        "broker": broker,
        "trade_session": sess,
        "net_rr_after_costs": round(net_rr, 3) if net_rr is not None else None,
        "shares": shares,
        "dollar_risk": round(dollar_risk, 2) if dollar_risk else None,
        "notional": round(notional, 2) if notional else None,
        "notional_pct": round(notional_pct * 100, 1) if notional_pct else None,
        "pct_risk": round(pct_risk * 100, 2) if pct_risk else None,
    }
    
    passed = all(hard.values()) and not fails

    # WATCH tier: every risk check passed and the ONLY blocker is the liquidity
    # floor (H6). This matters for futures/commodities/cash-indices, where the
    # feed reports contract counts or zero dollar-volume against an equity-style
    # dollar threshold — a data-shape mismatch, not a risk failure. These are
    # surfaced rather than silently dropped, but are NOT tradeable as-is: size
    # them manually or trade a liquid proxy.
    verdict = "GO" if passed else "NO-GO"
    if not passed:
        non_liq_hard_fail = any(
            not v for k, v in hard.items() if k != "H6_liq"
        )
        non_liq_fails = [f for f in fails if "liquidity" not in f]
        if hard.get("H6_liq") is False and not non_liq_hard_fail and not non_liq_fails:
            verdict = "WATCH"

    return {
        "verdict": verdict,
        "binding_reason": "" if passed else fails[0],
        "profile": profile,
        "hard": hard,
        "metrics": metrics,
        "flags": flags,
        "all_fails": fails
    }


def process_all_setups(scan_data: dict, profile_type: str = "swing", account_equity: float = None,
                        scan_timestamp=None, embargo_dates=None, stat=None) -> dict:
    """Process all qualified trades into complete setups"""
    longs = scan_data.get("qualified_longs", [])
    shorts = scan_data.get("qualified_shorts", [])
    
    all_setups = {"longs": [], "shorts": []}
    all_validations = {"GO": [], "WATCH": [], "NO-GO": []}

    # Guard: drop degenerate rows (zero / missing / non-numeric price) BEFORE
    # sizing math. Zero-price dust tokens caused ZeroDivisionError (2026-08-09).
    def _tradeable(t):
        try:
            p = float(t.get("price", t.get("entry_price", 0)) or 0)
        except (TypeError, ValueError):
            return False
        return p > 0

    skipped = [t.get("symbol", "?") for t in (longs + shorts) if not _tradeable(t)]
    longs = [t for t in longs if _tradeable(t)]
    shorts = [t for t in shorts if _tradeable(t)]
    if skipped:
        logging.warning("gate: skipped %d untradeable zero-price rows: %s",
                        len(skipped), ", ".join(skipped[:20]))

    # Process LONGs
    for trade in longs:
        trade["type"] = "LONG"
        trade["side"] = "LONG"
        setup = calculate_trade_setup(trade, profile_type, account_equity,
                                      scan_timestamp, embargo_dates, stat)
        all_setups["longs"].append(setup)
        all_validations[setup.validation["verdict"]].append({
            "symbol": setup.symbol,
            "side": setup.side,
            "verdict": setup.validation["verdict"],
            "reason": setup.validation.get("binding_reason", ""),
            "rr": setup.validation["metrics"].get("rr", 0),
            "deploy_pct": setup.validation["metrics"].get("deploy_pct", 0),
        })
    
    # Process SHORTs
    for trade in shorts:
        trade["type"] = "SHORT"
        trade["side"] = "SHORT"
        setup = calculate_trade_setup(trade, profile_type, account_equity,
                                      scan_timestamp, embargo_dates, stat)
        all_setups["shorts"].append(setup)
        all_validations[setup.validation["verdict"]].append({
            "symbol": setup.symbol,
            "side": setup.side,
            "verdict": setup.validation["verdict"],
            "reason": setup.validation.get("binding_reason", ""),
            "rr": setup.validation["metrics"].get("rr", 0),
            "deploy_pct": setup.validation["metrics"].get("deploy_pct", 0),
        })
    
    return {
        "setups": all_setups,
        "validations": all_validations,
        "summary": {
            "total_longs": len(all_setups["longs"]),
            "total_shorts": len(all_setups["shorts"]),
            "go_longs": len([s for s in all_setups["longs"] if s.validation["verdict"] == "GO"]),
            "go_shorts": len([s for s in all_setups["shorts"] if s.validation["verdict"] == "GO"]),
            "no_go_longs": len([s for s in all_setups["longs"] if s.validation["verdict"] == "NO-GO"]),
            "no_go_shorts": len([s for s in all_setups["shorts"] if s.validation["verdict"] == "NO-GO"]),
            "watch_longs": len([s for s in all_setups["longs"] if s.validation["verdict"] == "WATCH"]),
            "watch_shorts": len([s for s in all_setups["shorts"] if s.validation["verdict"] == "WATCH"]),
        }
    }


def setup_to_dict(setup: TradeSetup) -> dict:
    """Convert TradeSetup to dictionary for JSON serialization"""
    return {
        "symbol": setup.symbol,
        "name": setup.name,
        "category": setup.category,
        "side": setup.side,
        "entry_price": round(setup.entry_price, 6),
        "stop_loss": round(setup.stop_loss, 6),
        "take_profit_1": round(setup.take_profit_1, 6),
        "take_profit_2": round(setup.take_profit_2, 6),
        "take_profit_3": round(setup.take_profit_3, 6),
        "risk_per_share": round(setup.risk_per_share, 6),
        "reward_1": round(setup.reward_1, 6),
        "reward_2": round(setup.reward_2, 6),
        "reward_3": round(setup.reward_3, 6),
        "rr_1": round(setup.rr_1, 2),
        "rr_2": round(setup.rr_2, 2),
        "rr_3": round(setup.rr_3, 2),
        "atr": round(setup.atr, 6),
        "atr_stop_mult": round(setup.atr_stop_mult, 2),
        "position_size_pct": round(setup.position_size_pct, 2),
        "shares_per_account": round(setup.shares_per_account, 6),
        "dollar_risk_per_account": round(setup.dollar_risk_per_account, 4),
        "conviction_score": round(setup.conviction_score, 2),
        "sentiment_conviction": setup.sentiment_conviction,
        "pms_conviction": setup.pms_conviction,
        "conviction_rails": setup.conviction_rails,
        "confluence_score": setup.confluence_score,
        "base_score": setup.base_score,
        "vwap_distance_pct": round(setup.vwap_distance_pct, 2),
        "rsi": round(setup.rsi, 1),
        "ema20": round(setup.ema20, 6),
        "ema50": round(setup.ema50, 6),
        "trend": setup.trend,
        "profile_used": setup.profile_used,
        "sector_profile": setup.sector_profile,
        "validation": setup.validation,
    }


SCAN_LATEST = "universal_scan_results_latest.json"
STALE_AFTER_MINUTES = 90


def _staleness_minutes(scan_path, scan_data):
    """Minutes between the scan's own timestamp and now. None if unparseable."""
    import datetime as _dt

    ts = scan_data.get("scan_timestamp")
    if not ts:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    now = _dt.datetime.now(_dt.timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return (now - parsed).total_seconds() / 60.0


def run_gate(scan_file=SCAN_LATEST, account_equity=100000.0, profiles=("swing", "day"),
             write=True, allow_stale=False, embargo_dates=None, stat=None):
    """Load a scan file, validate every candidate, write <profile>_latest.json.

    This is the real entry point. Running this module directly used to execute a
    hardcoded single-trade demo that wrote nothing, which silently left stale
    enhanced_setups_*_latest.json files on disk while appearing to succeed.
    """
    import os
    import sys as _sys

    if not os.path.exists(scan_file):
        print(f"ERROR: scan file not found: {scan_file}")
        print("Run universal_premarket_scan.py first.")
        return None

    with open(scan_file, "r") as f:
        scan_data = json.load(f)

    age = _staleness_minutes(scan_file, scan_data)
    stamp = scan_data.get("scan_timestamp", "unknown")
    print(f"Scan file : {scan_file}")
    print(f"Scan stamp: {stamp}" + (f"  ({age:.0f} min old)" if age is not None else ""))

    if age is not None and age > STALE_AFTER_MINUTES and not allow_stale:
        print(f"\nREFUSING TO RUN: scan is {age:.0f} minutes old "
              f"(limit {STALE_AFTER_MINUTES}).")
        print("Re-run universal_premarket_scan.py, or pass --allow-stale to override.")
        return None

    n_long = len(scan_data.get("qualified_longs", []))
    n_short = len(scan_data.get("qualified_shorts", []))
    if n_long == 0 and n_short == 0:
        print("WARNING: scan contains zero candidates — nothing to validate.")

    results = {}
    for profile_type in profiles:
        print(f"\n--- {profile_type.upper()} profile ---")
        result = process_all_setups(scan_data, profile_type, account_equity,
                                    stamp if stamp != "unknown" else None,
                                    embargo_dates, stat)
        s = result["summary"]

        output = {
            "profile": profile_type,
            "account_equity": account_equity,
            "scan_timestamp": stamp,
            "scan_source": scan_file,
            "summary": s,
            "validations": result["validations"],
            "longs": [setup_to_dict(x) for x in result["setups"]["longs"]],
            "shorts": [setup_to_dict(x) for x in result["setups"]["shorts"]],
        }

        if write:
            out_path = f"enhanced_setups_{profile_type}_latest.json"
            with open(out_path, "w") as f:
                json.dump(output, f, indent=2)
            print(f"  wrote {out_path}")

        print(f"  LONGs : {s['total_longs']:3d}  (GO {s['go_longs']}, WATCH {s.get('watch_longs',0)}, NO-GO {s['no_go_longs']})")
        print(f"  SHORTs: {s['total_shorts']:3d}  (GO {s['go_shorts']}, WATCH {s.get('watch_shorts',0)}, NO-GO {s['no_go_shorts']})")

        for verdict_tier in ("GO", "WATCH"):
            for side in ("longs", "shorts"):
                for t in output[side]:
                    v = t["validation"]
                    if v["verdict"] != verdict_tier:
                        continue
                    m = v["metrics"]
                    tag = "GO   " if verdict_tier == "GO" else "WATCH"
                    print(f"    {tag} {side[:-1].upper():5} {t['symbol']:10} "
                          f"{t.get('category',''):11} "
                          f"entry={m.get('real_entry')} SL={t.get('stop_loss')} "
                          f"T1={m.get('real_t1')} RR={m.get('rr')} "
                          f"size={m.get('notional_pct')}% risk={m.get('pct_risk')}% "
                          f"| {t.get('conviction_rails','')}")

        results[profile_type] = output

    return results


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Enhanced trade gate — validate scan candidates")
    ap.add_argument("--scan-file", default=SCAN_LATEST, help="scan JSON to validate")
    ap.add_argument("--equity", type=float, default=100000.0, help="account equity")
    ap.add_argument("--profile", choices=["swing", "day", "both"], default="both")
    ap.add_argument("--allow-stale", action="store_true",
                    help=f"run even if the scan is older than {STALE_AFTER_MINUTES} min")
    ap.add_argument("--dry-run", action="store_true", help="validate without writing files")
    ap.add_argument("--embargo-dates", nargs="*", metavar="DATE",
                    help="ISO dates (YYYY-MM-DD) to add to the macro/earnings embargo "
                         "blackout (entries blocked; exits unaffected)")
    ap.add_argument("--stat-file", default=None,
                    help="JSON verdict store: {SYMBOL: {abs_t|t_stat|<verdict>}}. "
                         "When present, H11 enforces |t|>=2.5 / CONFIRMED per symbol; "
                         "missing symbols are flagged UNVALIDATED (never silently GO).")
    args = ap.parse_args()

    stat = None
    if args.stat_file:
        try:
            import json as _json
            with open(args.stat_file, "r") as _f:
                stat = _json.load(_f)
        except Exception as _e:
            print(f"WARN: could not load --stat-file {args.stat_file}: {_e}")

    profs = ("swing", "day") if args.profile == "both" else (args.profile,)
    res = run_gate(scan_file=args.scan_file, account_equity=args.equity,
                   profiles=profs, write=not args.dry_run,
                   allow_stale=args.allow_stale, embargo_dates=args.embargo_dates,
                   stat=stat)
    raise SystemExit(0 if res else 1)