# Blogwatcher symbol matching — false positives and the word-boundary fix

Session: 2026-08-06/07. Applied live to `blogwatcher_integration.py`.

## The defect

`analyze_sentiment_for_symbols()` matched symbols with a bare substring test:

```python
for sym in symbols:
    if sym.upper() in title:      # <-- WRONG
```

Titles are upper-cased before matching, so casing cannot disambiguate. Every
short ticker collided with ordinary English words inside headlines.

Live run, 100 articles, keys returned with "news":

```
ARR BTC CL CT DIA ES ETH HO KC NG PA PL RAVE RB RTY SI SOL TOPS UNG WEAT YM
```

Nearly all garbage. `CL` matched "MARKETS **CL**OSE", `ES` matched "T**ES**LA",
`SI` matched "**SI**GNAL"/"SHORT SELLERS", `HO` matched "**HO**USING",
`TOPS` matched "STOCK TOPS ESTIMATES", `RAVE` matched "B**RAVE**".

**Why it matters beyond noise:** these keys feed CONVICTION ranking. A bogus
`SI BULLISH` tag on a Silver SHORT flips it to CONFLICT and re-orders the
deploy list. Bad news matching silently corrupts trade prioritisation.

## The fix

`_symbol_in_title(sym, title)` in `blogwatcher_integration.py`, checked in this
exact order (order matters):

1. **`$TICKER` always wins.** `re.search(r"\$" + esc(s) + r"\b", title)` — an
   explicit cashtag is unambiguous at any length.
2. **Full-name aliases BEFORE the length guard.** `_SYMBOL_ALIASES` maps
   `BTC->BITCOIN`, `ETH->ETHEREUM/ETHER`, `SI->SILVER`, `CL->CRUDE OIL/WTI`,
   `GC->GOLD`, `NVDA->NVIDIA`, etc. This ordering is the subtle part: if the
   1-2 char guard runs first, `SI` never matches "SILVER" and `CL` never
   matches "CRUDE OIL". Getting this backwards silently drops real catalysts.
3. **Reject 1-2 char tickers** not in `_UNAMBIGUOUS_SHORT` (currently empty —
   they only match via `$` or alias).
4. **Reject English-word tickers** (`_ENGLISH_WORD_TICKERS`: NEAR, TOPS, LINK,
   OPEN, HIGH, LOW, GAS, CORE, BOND, RAVE, ...). Same reasoning as (3):
   upper-cased prose makes them indistinguishable. `$`-marked only.
5. Otherwise word-boundary match:
   `re.search(r"(?<![A-Z0-9])" + esc(s) + r"(?![A-Z0-9])", title)`.
   Custom lookarounds, NOT `\b` — `\b` treats `-` and `=` as boundaries, so
   `BTC-USD` would self-match on fragments.

Strip market suffixes (`-USD`, `-USDT`, `=X`, `=F`) before all of it.

## Verification

18-case unit test, all passing, covering every observed false positive:

```python
from blogwatcher_integration import _symbol_in_title as m
assert not m('CL','MARKETS CLOSE HIGHER')
assert not m('ES','TESLA SHARES JUMP')
assert not m('TOPS','STOCK TOPS ESTIMATES')
assert not m('NEAR','BITCOIN NEAR ALL-TIME HIGH')
assert     m('NEAR','$NEAR PROTOCOL UPGRADE')
assert     m('SI','SILVER RALLIES TO 12-YEAR HIGH')
assert     m('CL','CRUDE OIL SLIDES ON OPEC')
assert     m('BTC','BITCOIN ETF INFLOWS HIT RECORD')
assert     m('NVDA','NVIDIA BEATS ESTIMATES')
```

Live result after the fix, same 100 articles:

```
BTC BTC-USD ETH ETH-USD GC XRP-USD
```

## Iteration lesson

The fix took three passes against LIVE data, not one. Each pass surfaced a new
class of collision that unit tests alone would not have predicted:

- pass 1 (word boundary)  -> killed CL/ES/HO/PA/SI/RB/YM
- pass 2 (English words)  -> killed NEAR, TOPS
- pass 3 (extend wordlist)-> killed LINK ("link is unclear")

**Always re-run against the live feed after each pass and read the actual key
list.** A synthetic test suite will not enumerate the words that happen to
appear in today's headlines. Budget for several rounds.

## Maintenance

`_ENGLISH_WORD_TICKERS` is inherently incomplete — it grows as new collisions
appear. When a nonsense symbol shows up in a report's news section, add the
word to the set rather than special-casing the caller.
