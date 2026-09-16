# Auditing a cross-pipeline integration for silent-failure gaps

Session: 2026-08-06/07. Triggered by the user asking "do a workflow analysis
make sure we covered all gaps possible" after an integration was declared done.

## Why this exists

An integration can be syntactically perfect, import cleanly, be wired into
every pipeline, and still do NOTHING in production. Four such gaps were found
in code that had already been reported as complete and working. Every one of
them would have produced a clean-looking report with an empty result section.

**AST-clean + import-clean + wired != working.** The only proof is running it
against live data and reading the actual values.

## The audit sequence

Run these in order. Each catches a different class of silent failure.

### 1. Enumerate ALL consumers, not just the ones you wired

```bash
grep -ln "<upstream_module>\|<key_function>" *.py
```

This found `gap_rvol_screener.py` and `sector_scan_comprehensive.py` were also
blogwatcher consumers and had been missed entirely. Wiring three pipelines when
five exist is a coverage gap that looks like completion.

### 2. Compare KEY SHAPES across the boundary — highest-severity check

The single worst bug found. Producer and consumer used different key formats:

- scans emit market tickers: `BTC-USD`, `GC=F`, `EURUSD=X`
- blogwatcher keys news by bare symbol: `BTC`, `ETH`, `SOL`

`news_hits.get(sym)` was an exact match that could NEVER hit. Zero candidates
forever, reported as "no qualifying setups" — indistinguishable from a genuine
quiet market.

**Always print both key sets side by side and diff them:**

```python
print('producer keys:', sorted(hits.keys())[:20])
print('consumer keys:', sorted({a['symbol'] for c in scan['categories'].values()
                                for a in c.get('assets',[])})[:20])
```

Fix: a tolerant `news_for()` / `normalize_symbol()` lookup that strips
`-USD/-USDT/=X/=F` and falls back. Never a raw `dict.get()` across a boundary
where two systems name things differently.

### 3. Check nested VALUE TYPES, not just presence

`headlines` entries were dicts (`{'headline','source','url',...}`), not
strings. The code wrote the whole dict into a text field. Presence checks pass;
the data is garbage.

```python
print(type(v['headlines'][0]).__name__, str(v['headlines'][0])[:80])
```

### 4. Run the SAME input twice and diff the output store

```python
for i in range(3):
    apply_protocol(scan, hits, 'dedupetest')
print('rows after 3 identical runs:', len(json.load(open(LOG))['trades']))
```

2 runs produced 4 rows where it should be 2. Any store written by a scheduled
job needs signature dedupe — recurring crons plus manual reruns all hit the
same day, and an inflated log silently corrupts every downstream statistic
computed from it.

### 5. Look for CONTRADICTORY output pairs

The run emitted `SOL LONG` and `SOL SHORT` simultaneously, both with neutral
sentiment. Neutral means no direction, so it should emit neither. Whenever a
system can produce both sides of the same instrument, assert that it does not.

### 6. Test degenerate inputs explicitly

```python
apply_protocol(scan, {}, 'x')   # no news
apply_protocol({},   {}, 'x')   # empty scan
```

Both must return cleanly with an explanatory message, never a traceback and
never a bare zero.

### 7. Make ZERO RESULTS EXPLAIN THEMSELVES

The most valuable design change of the session. A bare "no candidates" is
indistinguishable from a broken integration. Emit near-misses with reasons:

```
No symbol qualified under the protocol this run.
Nearest misses:
- BTC SHORT: volume 0 below 30,000,000 floor
- ETH SHORT: volume 0 below 30,000,000 floor
```

That block immediately revealed a real upstream data bug (nightshift reports
crypto volume 0.0 while the daytime scan reports 18.4B for the same assets) —
which a silent zero would have hidden indefinitely.

**Build this into every gated/filtered feature from the start.**

## Structural patterns worth reusing

- **One shared module, many consumers.** Put the logic in a single module every
  pipeline imports (`news_protocol.py`), never copy-paste per pipeline. Rules
  cannot drift apart if there is one copy.
- **Wrap every integration call site in try/except.** An add-on feature must
  never be able to kill the host scan. Print a warning, continue.
- **Adapter functions for shape drift.** Flat-list screeners vs nested-category
  scans, `vol_ratio_50d` vs `vol_ratio_50` — normalise at the boundary
  (`adapt_flat_candidates`) rather than teaching the core logic every dialect.
- **Never fabricate a missing input.** When ATR was absent, the code left it 0
  so the gate blocked with an explicit "no ATR(14)" reason, rather than
  inventing a breakeven level. Same for proxy values: flag them
  (`trigger_low_is_proxy`, rendered as `*` with a footnote) so nobody trades a
  guess believing it is measured.

## Reporting the audit

State severity honestly. Two of the four gaps would have caused permanent
silent failure of code previously reported as working — say that plainly rather
than presenting the audit as routine confirmation. List remaining known gaps
explicitly (unwired dormant consumers, upstream data bugs) instead of implying
full coverage.
