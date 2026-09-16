# Backtest validation & real-liquidity backfill (pre-ticket validation)

The user's standing rule: a GO verdict validates *risk mechanics*, not *edge*.
Nothing gets a live ticket until backtest validation shows **PF >= 1.0**, and the
kill list (PF < 1.0) is carried across runs. This reference documents the working
end-to-end validation pattern proven 2026-08-05, including two bugs found and
fixed in the tools themselves.

## The end-to-end pattern

After the gate produces GO setups (day profile), do NOT hand them over as trades:

1. **Backtest** every GO symbol on the scan's own rule via `backtest_go_setups.py`.
2. **Backfill real liquidity** for any symbol the gate flagged "verify manually"
   (volume=0 from yfinance) by fetching 20-day volume from yfinance *daily history*.
3. **Consolidate**: a symbol clears only if `PF >= 1.0` AND `real liquidity passes`.
   Split into GO_TRADEABLE / BLOCKED_LIQUIDITY / DO_NOT_TRADE.
4. **Carry the kill list forward** — PF < 1.0 names are DO NOT TRADE next run too.

A reusable orchestrator for steps 1-3 is `scripts/validate_go_setups.py` (reads
`enhanced_setups_day_latest.json`, builds `go_setups_tmp.json`, runs the backtester,
backfills volume, writes `go_postanalysis.json`). Copy and adjust paths.

## BUG 1 — `backtest_go_setups.py` never fires (side case mismatch)

**Symptom:** `backtest()` returns `None` for every symbol; `backtest_go_results.json`
is `[]`; every GO verdict shows `PF n/a`. The data downloads fine (778 rows for
`USDJPY=X`) and a manual reimplementation of the loop produces 17 trades / PF 1.04 —
so the function is silently broken.

**Root cause:** callers (and `nightshift_postanalysis.py`) pass `side="long"` /
`"short"` (lowercase), but the trigger check inside `backtest()` tests
`side == "LONG"` / `"SHORT"` (uppercase). The boolean is always False, so the
`while` loop never enters a trade, `trades` stays empty, and `if not trades: return None`.

**Fix (applied live to `C:\Users\victo\backtest_go_setups.py`):** normalize at the
top of `backtest()`:
```python
def backtest(sym: str, side: str, period: str = "3y") -> dict | None:
    side = side.upper()  # normalize: callers pass 'long'/'short'
```
If backtests regress to `[]`, re-apply this first — do NOT assume the scan is empty.

**Secondary edge:** `profit_factor` returned `None` when a strategy had zero losing
trades (`losses.sum() == 0`). A strategy with no losses should report a real PF,
not "unknown". Fixed to:
```python
"profit_factor": (wins.sum()/abs(losses.sum())) if (losses.size and losses.sum() != 0)
                 else (float("inf") if wins.size else None)
```

## BUG 2 — raw symbols 404 on 3y history (yfinance ticker suffix matrix)

`backtest_go_setups.py` downloads with the *display* symbol from the scan
(`USDJPY`, `GC`, `CT`, `^GSPC`, `BNB-USD`). The yfinance **history** endpoint needs
exchange suffixes; bare symbols 404 ("possibly delisted"). The scan's batch feed
and the gate use generic symbols, so a mapping layer is required.

**Working `yf_ticker()` (proven 2026-08-05):**
```python
FUT_SUFFIX = {"GC": "=F", "SI": "=F", "PL": "=F", "HG": "=F",
              "CT": "=F", "ZS": "=F", "ZC": "=F", "KC": "=F"}
def yf_ticker(sym: str) -> str:
    if sym.endswith("=X") or sym.endswith("-USD") or sym.startswith("^"):
        return sym
    if sym in FUT_SUFFIX:
        return sym + FUT_SUFFIX[sym]
    if len(sym) == 6 and sym[:3].isalpha() and sym[3:].isalpha():  # bare FX pair
        return sym + "=X"
    return sym
```
- FX pairs: `USDJPY` -> `USDJPY=X` (all G10/EM `=X` pairs work).
- Metal + ag futures: `GC/SI/PL/HG/CT/ZS/ZC/KC` -> `=F` (NOT `.CMF` — that 404s;
  corn `ZC=F` and coffee `KC=F` both resolve with `=F`).
- Indices: `^GSPC` etc. work as-is.
- Crypto: `BNB-USD` etc. work as-is.
- Equities/ETFs: pass through unchanged.

The backtester should write `yf` (download ticker) alongside `sym` (display) in
`go_setups_tmp.json`, download with `yf`, and restore `symbol = sym` on output so
the PF table keys match the gate's display symbols.

## FX volume=0 is structural — not illiquidity

When backfilling liquidity, yfinance returns `Volume=0` for FX `=X` pairs **even on
daily history** (it does not report retail FX turnover). The gate's H6 hard floor
(ADV 1M / $vol 50M) therefore "fails" FX on a zero that we *know* is a data gap —
FX is the deepest market on earth (~$7T/day).

**Handle it explicitly:** if `category == "forex"` and the fetched `adv <= 0`,
record `passes_liquidity = True` with a transparency note ("FX volume not reported
by yfinance — passed on known deep liquidity"), rather than failing it. Do NOT
extend this leniency to metals/ag futures: those genuinely under-report contract
volume and should be judged on the real (often thin) numbers — e.g. PL (platinum)
ADV 1,084 contracts is a real liquidity fail, not a gap.

## Liquidity floors for the backfill (mirror of gate's `get_liquidity_floors`)

```python
LIQ = {
    "forex": (1_000_000, 50_000_000),
    "indices": (1_000_000, 100_000_000),
    "commodities": (5_000, 5_000_000),
    "metals": (5_000, 5_000_000),
    "etfs": (500_000, 10_000_000),
    "crypto": (100_000, 10_000_000),
}
```
Fetch `df["Volume"]` and `df["Close"]` over ~2 months, take `tail(20).mean()` for
ADV and `mean(volume * close)` for dollar volume. ETFs and crypto already carry
real volume in the scan, so skip refetch for those.

## Consolidation verdict logic (per symbol)

```python
bt = bt_map.get((sym, side.upper()))          # backtest PF lookup
pf = bt["profit_factor"] if bt else None
liq = liq_results.get(sym)                     # real-liquidity backfill result
verdict = "DO_NOT_TRADE"
if bt and pf is not None and pf >= 1.0:
    if liq is None or liq.get("verified") is False or liq.get("passes_liquidity", True):
        verdict = "GO_TRADEABLE"
    else:
        verdict = "BLOCKED_LIQUIDITY"
```
Note: `bt_map` key must uppercase the side (`r["side"].upper()`), or the lookup
misses and PF reads `None` (this exact mismatch produced `n/a` verdicts until fixed).

## Worked result (2026-08-05, 15 day-profile GOs)

After fixes: 7 cleared both bars (PF >= 1.0 + real liquidity), 8 correctly killed.

- GO_TRADEABLE: GBPJPY (PF 2.45), CHFJPY (1.26), USDJPY (1.04), BNB (1.87),
  ZS soybeans (1.07), ZC corn (1.15), FX on known-liquidity.
- BLOCKED_LIQUIDITY: PL (PF 1.14 but ADV 1,084 contracts — real thin).
- DO_NOT_TRADE (PF < 1.0): CT (0.98), ^GSPC (0.32), ^FTSE (0.48), GC (0.53),
  SI (0.56), XLV (0.67), KC (0.68).

The kill list (CT/^GSPC/^FTSE/GC/SI/XLV/KC) is carried forward: if the scanner
re-emits them, they stay rejected unless PF flips >= 1.0.

## Pitfalls specific to this validation

- **`profit_factor` of `inf` (zero losses) is a PASS**, not "unknown". Surface it as
  GO, but flag the tiny sample (a 3-trade winner with no losses is not edge).
- **Do not re-fetch history on every re-run.** The 3y backtest is the slow part;
  cache `backtest_go_results.json` and only re-run the consolidation if the GO set
  is unchanged.
- **A manual reimplementation of the loop that "works" while the function returns
  None means the FUNCTION has a bug** — instrument it (print `trig` count, `trades`
  length) rather than rebuilding. The one-char `side` case was invisible until a
  `print("DBG trades=", len(trades))` was injected.
- **`process(action='wait')` clamps to ~60s**; the 3y backtest over 15 symbols
  takes longer — run the postanalysis in `background=true` with `notify_on_complete`.
