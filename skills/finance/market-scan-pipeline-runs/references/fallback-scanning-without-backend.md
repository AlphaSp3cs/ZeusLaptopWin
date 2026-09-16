# Fallback scanning when the search/scrape backend dies

When Firecrawl/Nous billing is exhausted (HTTP 402, `insufficient_funds`),
`web_search()` and `web_extract()` both fail. The scan pipeline has the same
single point of failure: `fresh_sentiment()` in `scan.py` relies on
`D:\Hermes\skills\crypto-sentiment-aggregator\crypto_sentiment_aggregator.py`
which itself scrapes news/RSS. If the billing dies, the entire news overlay
dies.

**Symptoms**: every `web_search` call returns `"success": false` with a
`BILLING_ERROR` code. `web_extract` does the same. `fresh_sentiment()` returns
`None` and the scan flags `LOW-COVERAGE`.

**Fallback: direct Yahoo Finance chart API for price-only scans.**
No API key needed. Works for ~50 symbols per batch before rate-limiting:

```python
import urllib.request, json

def fetch_yahoo_chart(symbol, timeout=15):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1mo"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    meta = data["chart"]["result"][0]["meta"]
    return {
        "symbol": symbol,
        "price": meta.get("regularMarketPrice", 0),
        "change_pct": meta.get("regularMarketChangePercent", 0),
    }
```

**When to use it**:
- User asks for a bullish/bearish read across all sectors but D: drive is
  missing AND backend billing is dead. The full gate pipeline is unavailable;
  a direct price+change scan is the only live data path.
- User asks for "what's green today" and you need a fast answer without the
  10+ minute full scan pipeline.

**Limitations**:
- Only price and % change. No fundamentals, no news sentiment, no technical
  indicators (RSI, ATR, VWAP, EMA) from this endpoint alone.
- Not a replacement for the full scan->gate pipeline when it's available.
- For a full technical scan without D: drive, you would need to compute
  indicators from the raw bars returned by the chart API (it provides
  `timestamp`, `indicators` arrays) — but the range is capped at ~30 days
  for daily data.

**Pattern from 2026-09-14 session**: `bullish_scan.py` in the home dir is a
standalone script that fetches ~35 symbols across US equity, bonds,
commodities, indices, FX, and crypto, filters for `change_pct > 0.5`, and
writes `~/bullish_scan_latest.json`. It runs in ~30s vs. the 10+ minute full
pipeline. Use it as a starting point for future fallback scans.

## Also: PowerShell scripts for system automation

When bash eats `$` variables in PowerShell commands (MSYS path translation),
write `.ps1` files and execute them directly:

```bash
pwsh.exe -ExecutionPolicy Bypass -File C:/Users/victo/Desktop/script.ps1
```

This is the reliable way to run PowerShell automation (cleanup, uninstall,
service management) from a Hermes terminal session. The `skill_manage
write_file` action with `file_path` works for creating the `.ps1` files.

## Checklist when a scan fails

1. Is D: drive present? `ls /d 2>/dev/null`
2. Is backend billing alive? `web_search` test call
3. If both dead -> use direct Yahoo chart API for price-only reads
4. If D: dead but billing alive -> scan runs but `bars_refresh()` fails;
   use `--no-bars` flag, but warn user that technicals may be stale
5. If billing alive but D: present -> full pipeline available
