---
name: sector-risk-and-52w-low-ordering
description: Extending an income buy plan with sector concentration caps, 52-week-low proximity ordering, and yfinance 1.5.x live-data fixes.
---

# Sector Risk Distribution & 52-Week-Low Entry (extension to income planning)

Use when the user wants the dividend plan to also *manage drawdown* and *time entries by
margin of safety* — e.g. "add a sector column, minimize drawdown, order by closeness to the
52-week low." This is a layer on top of the base income-ordering workflow, not a replacement.

## Sector risk distribution (minimize drawdown)
- Tag every holding with its sector (derive from the source universe; do not assume it).
- Compute per-sector realized **MaxDD** = deepest peak-to-trough decline over trailing 12m daily closes:
  `dd = (close / close.cummax() - 1).min() * 100`.
- Cap single-sector weight: base ≤20%; raise to ≤22% for low-drawdown sleeves
  (ETF dividend-growth ≈ −5%, regulated utilities ≈ −13%); cut to ≤18% (or ≤14%) for
  high-drawdown sleeves (Tech/Software/Social-AI −33% to −37%, Telecom −29%).
- Equal-weight across the represented sectors is the lowest-drawdown posture; tilt toward
  cheaper sectors (lower % above 52w low).

## 52-week-low proximity ordering (margin of safety)
- Pull live 52w low/high per ticker; compute `% above low = price/low52 - 1` and
  `Pos% = (price-low)/(high-low)` (0 = at low, 100 = at high).
- Group the list by sector; within each group sort **ascending by % above low** so the
  cheapest entry in each sector is listed first.
- Build a one-cheapest-per-sector shortlist (instant sector spread + margin-of-safety
  entries), then income-weight it.
- Caveat to state in the doc: near-52w-low ≠ future value; a name at its low can keep
  falling (value trap). Keep MaxDD and %-positive-swing columns beside it so entries
  aren't blind.

## yfinance 1.5.x live-data gotchas (reusable)
- `history()` no longer accepts `progress=` or `actions=` kwargs → drop them.
- Dividend `Series.index` is **tz-aware** (America/New_York). Comparing against
  `datetime.now()` raises `TypeError: tz-naive vs tz-aware`. Build tz-aware cutoffs:
  `tz = divs.index.tz; now = pd.Timestamp.now(tz=tz); cutoff = now - pd.Timedelta(days=365)`.
- `t.dividends` attr may be empty on newer installs; fall back to `t.get_dividends()`.
- `auto_adjust=True` already bakes dividends into `Close`, so treat `Close` as the
  adjusted/price proxy.

## Canonical artifact pattern (for this user's HTML reports)
- Keep an original `.bak.html`; rebuild the report from the backup each run so injected
  sections never duplicate.
- Inject new `<div>` sections before `<footer class="pub-footer">`; add a `<style>` block
  with `print-color-adjust:exact` so banner/highlight colors survive
  `chrome --headless --print-to-pdf`.
- Cache fetched 52w metrics to JSON, reuse if <24h old to avoid re-hitting Yahoo on every re-run.
- Verify the PDF by extracting text with `pypdf` and asserting each section heading is present
  (text extraction wraps styled headings, so match on a substring, not the full heading).
