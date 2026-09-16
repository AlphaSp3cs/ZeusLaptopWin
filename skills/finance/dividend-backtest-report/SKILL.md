---
name: dividend-backtest-report
description: Backtest dividend list live, rank yield, export HTML/PDF.
---

# Dividend Backtest & Presentation Report

Use when the user has a file (HTML/JSON) holding a universe of dividend tickers
and wants (a) LIVE prices/dividends, (b) a historical swing backtest, (c) a
ranking by live yield, and (d) a presentation-ready artifact — either a styled
section injected into an existing HTML report or a print-ready PDF.

Complements `dividend-income-portfolio-planning` (which orders a ticker list
into an executable buy plan). This skill adds the live-data + backtest +
presentation-export layer on top of that ordering.

## Trigger conditions
- User points at an HTML/CSV/JSON universe and says "backtest", "rank by
  dividend", "live values", "highest dividend payer", "update the report for a
  presentation", "make a deck", "export PDF".
- "do the same compound-effect thing on this file".

## Workflow
1. **Parse universe.** HTML: regex `ticker:"([A-Z0-9\.]+)"` out of the embedded
   data array; de-dup preserving order. JSON: list of tickers or
   `{"UNIVERSE":[{ticker:...}]}`. (See `scripts/backtest_universe.py`.)
2. **Fetch LIVE data** per ticker: last price, TTM dividends, 3y weekly history.
   Use the verified yfinance 1.5.2 pattern in `references/yfinance_fetch_notes.md`.
3. **Backtest:** rolling weekly-entry, 1-year hold. For each window:
   `total = p1/p0 - 1 + realized_divs_in_window/p0`. Report median total return
   and **% of windows positive** (= swing reliability). Also trailing 3y
   buy-&-hold total (price + sum dividends).
4. **Rank by live yield** (highest first). Define a "best set" = high yield AND
   reliability >=90% AND median swing >=20%.
5. **Emit JSON + MD** (raw auditable + readable).
6. **Present:** inject a styled `<div>` section before the report `<footer>`
   reusing the host's CSS; or export a standalone PDF via headless Chrome.
   (See `scripts/inject_report.py`.)

## Pitfalls
- **yfinance 1.5.2 removed `progress=` from `history()`** — passing it raises
  TypeError. Omit it.
- **Dividend index is tz-aware** (America/New_York); comparing to a naive
  datetime raises. Build tz-aware cutoffs: `now = pd.Timestamp.now(tz=divs.index.tz)`.
- **`.dividends` vs `get_dividends()`** differ across versions — try attribute,
  fall back to method.
- **Windows paths in bash/printf mangle** (`\U`, `\v`). Use `write_file`/`patch`
  or single-quoted paths.
- **Headless Chrome PDF:** `--headless --disable-gpu --no-sandbox
  --no-pdf-header-footer --print-to-pdf=out.pdf file:///...`. Force background
  colors with `@media print { * { -webkit-print-color-adjust:exact;
  print-color-adjust:exact; } }` or banners/highlights print white.
- **JS-rendered host tables:** if the report builds its main table from a
  `<script>` UNIVERSE array at runtime, static HTML->PDF (wkhtmltopdf, weasyprint)
  will NOT render it. You MUST use a real browser engine (headless Chrome).
- **3Y totals are realized, not forward** — say so in the report. The rolling 1Y
  swing stats are the forward-relevant evidence.
- **REIT/MLP payout:** don't compute GAAP payout; AFFO/FCF is correct. Flag, don't omit.
- **Open-position screenshots from a platform:** entry price / contract size are
  usually NOT shown on a watchlist view — capture only what's visible (live px,
  daily P&L, stops) and state the gap honestly; never invent entry levels.

## Verification
- Re-run scripts; assert JSON `failed: []`.
- For PDF, extract text (pypdf) and confirm each section string is present
  (e.g. "LIVE MARKET UPDATE", "Best Set", "Open Positions", ticker names).

## Support files
- `scripts/backtest_universe.py` — generalized live fetch + backtest. Arg: input
  HTML/JSON. Writes `<stem>_backtest.json` + `<stem>_backtest.md`.
- `scripts/inject_report.py` — reads a backtest JSON + target HTML, injects a
  styled section before `<footer>` (idempotent from `.bak.html`), optionally
  prints PDF via Chrome.
- `references/yfinance_fetch_notes.md` — verified yfinance 1.5.2 dividend/price
  fetch pattern + tz fix.
