#!/usr/bin/env python3
"""
nvidia_llm.py — Thin client for the NVIDIA hosted inference API.

The key (NVAKEY env var) is an OpenAI-compatible chat-completions endpoint:
    https://integrate.api.nvidia.com/v1/chat/completions

WHY THIS EXISTS / WHAT IT ACCELERATES
------------------------------------
Your scan->gate->gauge pipeline (nightshift_scan.py, enhanced_trade_gate.py,
blogwatcher_integration.py) is 100% numeric JSON. There is no LLM step in it,
so a text API cannot make the yfinance fetches or the gate math faster.

What the LLM *can* do is offload the slow, token-heavy INTERPRETATION layer:
turning the gate JSON + danger-zone gauge + blogwatcher sentiment into a
plain-English regime read and per-setup rationale. We batch every GO/WATCH
setup into ONE call (instead of reasoning about each separately) and the call
runs in parallel with the rest of the report assembly.

MODELS THAT RESOLVE ON THIS ACCOUNT (verified 2026-08-05):
    meta/llama-3.1-8b-instruct        ~1s/trivial -> FAST default
    nvidia/llama-3.3-nemotron-super-49b-v1  ~30s -> use for quality, not speed
    (openai/gpt-oss-120b timed out; others 404 -> not in this account's catalog)

USAGE
    export NVAKEY="nvapi-..."
    from nvidia_llm import synthesize_nightshift
    narrative = synthesize_nightshift(scan_data, gate_results, catalysts, gauge)
"""

import os
import json
import time
import hashlib
import urllib.request
from typing import Optional, Dict, Any, List

ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"

# Default model = the FAST one. Override with NVIDIA_MODEL if you want quality.
DEFAULT_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")

# Cache synthesized narratives so re-runs of the same dataset are instant.
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         ".nvidia_llm_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _api_key() -> str:
    k = os.environ.get("NVAKEY") or os.environ.get("NVAPI")
    if not k:
        raise RuntimeError(
            "Set NVAKEY (or NVAPI) env var. Usage: export NVAKEY='nvapi-...'")
    return k


def chat(prompt: str,
         system: str = "You are a concise financial analyst. Output markdown only.",
         model: str = DEFAULT_MODEL,
         temperature: float = 0.2,
         max_tokens: int = 900) -> str:
    """Single chat-completion call. Returns the assistant text."""
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    elapsed = time.time() - t0
    text = data["choices"][0]["message"]["content"].strip()
    return text, elapsed


def _compact_setup(t: Dict[str, Any]) -> Dict[str, Any]:
    """Pull only the fields an analyst needs; drop noisy internals."""
    v = t.get("validation", {})
    return {
        "symbol": t.get("symbol"),
        "name": t.get("name"),
        "category": t.get("category"),
        "side": t.get("side"),
        "entry": t.get("entry_price"),
        "stop": t.get("stop_loss"),
        "tp1": t.get("take_profit_1"),
        "rr1": t.get("rr_1"),
        "rsi": t.get("rsi"),
        "conviction": t.get("conviction_score"),
        "verdict": v.get("verdict"),
        "binding_reason": v.get("binding_reason"),
    }


def _build_context(scan_data, gate_results, catalysts, gauge) -> Dict[str, Any]:
    ctx = {}
    # Gauge
    if gauge:
        ctx["gauge"] = {
            "value": gauge.get("gauge_value"),
            "base": gauge.get("base_gauge"),
            "interpretation": str(gauge.get("interpretation", ""))[:400],
        }
    # Catalysts / blogwatcher
    if catalysts:
        ctx["regime_shift_risk"] = catalysts.get("regime_shift_risk")
        ctx["total_articles"] = catalysts.get("total_articles")
        # blogwatcher only covers BTC/ETH/SOL per standing instruction
        sym_news = catalysts.get("symbol_news", {})
        ctx["crypto_news_count"] = len(sym_news)
    # Setups: only GO + WATCH (NO-GO needs no narrative)
    go_watch = []
    if gate_results:
        for prof, out in gate_results.items():
            for side in ("longs", "shorts"):
                for t in out.get(side, []):
                    v = t.get("validation", {}).get("verdict")
                    if v in ("GO", "WATCH"):
                        s = _compact_setup(t)
                        s["profile"] = prof
                        go_watch.append(s)
    ctx["go_watch_setups"] = go_watch
    # Headline counts
    ctx["counts"] = {}
    if gate_results:
        for prof, out in gate_results.items():
            s = out.get("summary", {})
            ctx["counts"][prof] = {
                "go_longs": s.get("go_longs"),
                "go_shorts": s.get("go_shorts"),
                "watch_shorts": s.get("watch_shorts"),
                "no_go_longs": s.get("no_go_longs"),
                "no_go_shorts": s.get("no_go_shorts"),
            }
    return ctx


def synthesize_nightshift(scan_data, gate_results, catalysts, gauge,
                          model: str = DEFAULT_MODEL) -> str:
    """
    Produce a plain-English narrative for a nightshift scan.
    Cached by content hash so identical inputs return instantly.
    """
    ctx = _build_context(scan_data, gate_results, catalysts, gauge)
    h = hashlib.sha256(json.dumps(ctx, sort_keys=True, default=str).encode()).hexdigest()[:16]
    cache_file = os.path.join(CACHE_DIR, f"{h}.txt")
    if os.path.exists(cache_file):
        return open(cache_file).read()

    prompt = f"""You are writing the 'READ THIS FIRST' section of an overnight
market scan report for a long-horizon dividend/income investor who also runs
technical swing/day setups on forex, commodities, indices and crypto.

Given this structured scan context, write a tight markdown brief with exactly
these sections:

## REGIME READ
- One paragraph: what the danger-zone gauge value implies for risk appetite,
  plus the blogwatcher regime-shift-risk flag.
- CRITICAL DIRECTION RULE: higher gauge value = MORE danger / LOWER risk
  appetite (hedge, reduce size, fewer GOs). Gauge ~82-100 means EXTREME DANGER
  -> suppress risk, do NOT say 'high risk appetite'. Gauge <35 means low danger
  / higher risk appetite. State the implication correctly.
- Note explicitly: blogwatcher's per-symbol sentiment layer covers only
  BTC/ETH/SOL, so for other assets the per-symbol layer is unavailable.

## GO / WATCH SETUP RATIONALES
- One bullet per GO or WATCH setup (symbol, side, profile): why it qualifies in
  plain English, referencing entry/stop/RR where useful. If none, say 'None'.

## CAVEATS
- 1-3 lines on what to watch (gauge elevated, all swing NO-GO, etc.).

CONTEXT:
{json.dumps(ctx, indent=2, default=str)}

Be specific and concise. No preamble. Use the data; do not invent setups.
"""
    text, _ = chat(prompt, model=model)
    with open(cache_file, "w") as f:
        f.write(text)
    return text


if __name__ == "__main__":
    # Load the latest real artifacts and synthesize, timing the call.
    import nightshift_report as nr  # reuse its loaders if available
    scan = json.load(open(nr.NS_SCAN))
    gr = {}
    for prof, fname in (("swing", nr.NS_SWING), ("day", nr.NS_DAY)):
        if os.path.exists(fname):
            gr[prof] = json.load(open(fname))
    gauge = None
    if os.path.exists(nr.GAUGE_JSON):
        gauge = json.load(open(nr.GAUGE_JSON))
    try:
        catalysts = nr.run_blogwatcher()
    except Exception:
        catalysts = {"regime_shift_risk": "UNKNOWN", "total_articles": 0}

    t0 = time.time()
    out = synthesize_nightshift(scan, gr, catalysts, gauge)
    dt = time.time() - t0
    print(f"[nvidia_llm] synthesized in {dt:.1f}s (incl. cache write)\n")
    print(out)
