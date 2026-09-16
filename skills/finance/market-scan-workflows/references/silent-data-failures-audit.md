# Silent data failures in the scan pipeline (audit findings)

Real bugs found by auditing rather than trusting the pipeline's own output.
Every one of these produced a *plausible-looking* report while being wrong.
That is the defining trait: none of them raised an error to the user.

## The audit method that found them

Do not verify a scan integration by reading the code. Run it against real
data and check the values against a second, independent source in the same
codebase. Concretely:

1. Run the module standalone on the real latest scan JSON.
2. Compare the same symbol's metrics across two pipelines (e.g. nightshift
   crypto vs universal daytime crypto). Divergence on the SAME asset at the
   SAME time is the tell.
3. Run the step twice and diff the persisted output (catches dedupe bugs).
4. Feed empty / malformed input and confirm graceful degradation.
5. Write a table of expected-vs-actual cases and assert on it.

A "0 results" outcome is the highest-risk success-looking state. Always ask
"could this be 0 because the lookup can never match?" before accepting it.

## 1. Symbol key drift (silent zero forever)

Scans emit market tickers (`BTC-USD`, `GC=F`, `EURUSD=X`); blogwatcher keys
news by bare symbol (`BTC`). An exact `news_hits.get(sym)` never matches, so
the news layer reports "no catalysts" permanently and looks healthy.

Fix: normalise by stripping `-USD` / `-USDT` / `=X` / `=F` and fall back.
Verify with a live fetch and print BOTH key sets side by side.

## 2. Substring symbol matching (false catalysts)

`if sym.upper() in title` tags unrelated headlines. Live run produced
`CL, CT, ES, HO, PA, PL, RB, SI, YM` — all incidental letter pairs inside
ordinary words (MARKETS **CL**OSE, T**ES**LA, S**HO**RT).

Fix, in this precedence order:
1. `$TICKER` regex — always unambiguous, check first.
2. Full-name aliases (BITCOIN→BTC, SILVER→SI, CRUDE OIL→CL) — check BEFORE
   any length guard, otherwise 2-char tickers can never match their own
   asset name.
3. Reject tickers <= 2 chars on bare word match.
4. Reject tickers identical to English words (NEAR, TOPS, LINK, OPEN, GAS)
   unless `$`-marked. Titles are upper-cased before matching, so casing
   cannot disambiguate them.
5. Word-boundary regex `(?<![A-Z0-9])SYM(?![A-Z0-9])`.

Result: 21 junk keys → 6 real ones.

## 3. Hardcoded zero volume (nightshift crypto)

`_scan_crypto_yf()` in `nightshift_scan.py` downloaded full OHLCV but only
extracted the Close frame, then wrote a literal `"volume": 0.0,
"volume_ratio": 1.0`. Consequences:
- every volume gate dead overnight (30M news-protocol floor unreachable)
- the "High volume (x)" scoring bonus silently never fired
- `volume_ratio` was a fake constant, not a measurement

Tell: the same asset showed 18.3B volume in the daytime universal scan and
0.0 in nightshift at the same timestamp.

Fix: extract `High`/`Low`/`Volume` frames from the MultiIndex (and the
non-MultiIndex fallback), compute today volume + 20d ratio.

## 4. NameError swallowed by a per-item try/except

`ema200` was referenced in the crypto scoring block but never assigned. The
per-coin `except` caught the NameError and `continue`d, so EVERY coin was
silently dropped from qualification — crypto never produced setups overnight
and nobody saw an error. Visible only as a terse
`[crypto TRX] skip: name 'ema200' is not defined` line.

Fix: compute it; set `None` when history is too short (3mo of dailies is
< 200 bars) and guard with `is not None`. Do NOT default it to `0.0` — that
makes `price > ema200` trivially true and hands out a free uptrend bonus.

Lesson: broad per-item try/except around scoring turns logic errors into
silent data loss. When an item count looks low, grep the skip messages.

## 5. Close-only ATR

`calculate_atr(px, px, px)` understates true range, which shrinks every
1.5xATR stop derived from it. Use real High/Low with a close-only fallback.

## 6. Non-idempotent logging

Appending scan candidates to a JSON log duplicated entries on every re-run.
The 09:37 and 14:37 crons plus manual runs all hit the same day, so any
win-rate review computed off the log would be wrong.

Fix: signature dedupe on `(day, symbol, side, entry)`, not just on id.

## Cross-pipeline consistency

Shape drift between scan payloads is a recurring source of silent misses:
- universal scan: nested `{"categories": {cls: {"assets": [...]}}}`,
  key `vol_ratio_50`
- gap_rvol_screener: FLAT candidate list, key `vol_ratio_50d`, NO atr field

Normalise via an adapter rather than duplicating logic. When a required
input is genuinely absent (no ATR), leave it 0 so the evaluator BLOCKS with
an explicit reason — never synthesise a value to make the row pass.
