# Instrument Selection & Actionable Deliverables

Companion to `references/backtest-validated-scan-run.md`, which already covers
the backtest-before-tickets rule and the 2026-08-05 GO-list results. This file
covers **which instrument you quote** and **what shape the deliverable takes**
— both corrected by the user on 2026-08-05.

---

## 1. Verify the instrument is the one the user asked for

The user was given `CL=F` levels and asked: *"can we make sure you are giving
me values for us crude oil spot"*. `CL=F` is the front-month NYMEX **futures**
contract. `GC=F` is COMEX futures. Neither is spot. The challenge was correct
and the check had not been done.

### Yahoo/yfinance spot ticker resolution matrix (verified 2026-08-05)

| Ticker | Result |
|---|---|
| `XAUUSD=X` | 404 — delisted. No gold spot. |
| `WTICOUSD=X` | 404 |
| `USOIL` | 404 |
| `CL1!` | 404 (TradingView syntax, not Yahoo) |
| `WTI` | Resolves to a **$3.42 NYQ equity** — wrong instrument entirely |
| `^SPGSCL` | Works, but is an S&P GSCI index level (415.27), not $/bbl |
| `CL=F` `BZ=F` `GC=F` | Work — but are **futures**; label them as such |

**There is no free spot feed for gold or WTI in this stack.** The dangerous
case is not the 404s, it is `WTI` — a ticker that silently *resolves* to a
valid quote for an unrelated asset. Check `fast_info['exchange']` and
sanity-check price magnitude before trusting any symbol you have not used
before. A wrong-instrument number is worse than an error because it looks right.

### What to do when the user asks for spot

1. Say plainly the scanner has no spot feed and that what you gave was futures.
2. Cross-check an independent source for the real spot print: oilpriceapi.com
   live WTI, EIA Cushing FOB (`eia.gov/dnav/pet/hist/rwtcw.htm`), FRED
   `DCOILWTICO`.
3. Quote the **basis** so the levels transfer. 2026-08-05: WTI Cushing spot
   $76.50 vs CL=F 76.36 = **+$0.14**, inside noise, levels transfer ~1:1.
   Gold spot runs a few dollars *under* COMEX carry — flag anything derived
   that way as an estimate, not a quote, and tell the user to pull their own
   platform's XAUUSD bid and shift by the difference.

---

## 2. ETFs frequently carry the edge the futures do not

Same rule, same 60-day window, both commodities, both directions:

| Instrument | Side | PF |
|---|---|---|
| USO | LONG | **1.52** |
| CL=F | LONG | 1.00 |
| GLD | SHORT | **1.42** |
| GC=F | SHORT | 1.02 |

The futures' wider ATR chops through the same ATR-multiple stop and rounds the
expectancy to breakeven. When both exist and the user has not demanded a
vehicle, recommend the ETF and **show the paired profit factors** so the choice
is visibly evidence-driven rather than asserted. (Companion to the existing
pitfall that a liquidity failure on a futures symbol says nothing about its ETF
proxy — same lesson, opposite direction.)

Related directional split from the same window, worth **re-deriving rather than
inheriting**: fade gold rallies (every gold LONG negative — GLD 0.84, GC=F 0.81,
GDX 0.75) and buy oil dips (every oil SHORT negative — BZ=F 0.81, CL=F 0.87,
USO 0.94). That was measured during an active Hormuz war.

---

## 3. Re-pull prices before restating an actionable entry

Quotes go stale inside a single conversation. Between two answers GC=F moved
4213.10 → 4221.80, taking a proposed short entry from $12 away to $3 away —
materially changing the trade and its stop distance. Re-fetch the last bars
before repeating any level the user is about to act on, and tell them it moved.

---

## 4. Intraday scan harness

`C:\Users\victo\gold_oil_intraday_scan.py` — 15m/60d bars, **session-anchored**
VWAP (grouped by date, expanding, TWAP fallback on zero-volume feeds), opening
range, prior-day H/L, plus a VWAP-reversion backtest (RSI15<35 & >0.5 ATR below
VWAP long / RSI>65 & >0.5 ATR above short, 1.5×ATR stop, 1.5R target, 26-bar
timeout). Writes `gold_oil_intraday.json`.

Use `prepost=True` for intraday fetches; 60d is the yfinance limit at 15m.
Fewer than ~25 trades per symbol is noise — say so.

---

## 5. Deliverable format: the sequenced execution file

The user asked: *"give me a file that tells me exactly buy this first then when
done buying sell all this next all in order entry, stop loss and take profit."*
A markdown report is not that. Write a **plain-text `.txt`** — it is read in a
terminal and printed, so no markdown tables or fenced blocks.

Shape that worked (`EXECUTION_ORDER_20260805.txt`):

- Numbered `STEP 1 of N` in a **single mandatory sequence**, phase-separated
  (`PHASE 1 — BUY THESE`, `PHASE 2 — NOW SELL/SHORT THESE`), with hard gate
  lines between steps:
  `>>> DO NOT PROCEED TO STEP 2 UNTIL XLU IS FILLED AND THE STOP IS LIVE. <<<`
- Order steps by **backtest quality descending**, so a user who runs out of
  capital automatically drops the weakest names. State that logic explicitly.
- Per step: ACTION / ORDER TYPE / ENTRY with acceptable fill range / STOP /
  TP1 with % to close / TP2 with % to close / SIZE / RISK / where the stop moves
  after TP1 / a one-paragraph "why" citing the backtest numbers / and a **kill
  trigger** naming the specific headline that invalidates it.
- A blank `Account size: $______` at the top plus the shares formula, since
  sizes are expressed as % of account.
- Totals: capital deployed, and total risk if every stop hits.
- An explicit **DO NOT TRADE** section listing rejected names *with the numbers
  that disqualified them* — the user wants the diff, not the verdict.
- Standing rules: never widen a stop, no naked positions overnight, do not chase
  a gapped entry (thin edges are erased by a bad fill).
- A **FILL LOG** table with blanks for planned / filled / shares / stop-set / time.

For intraday variants add a per-position **TIME STOP** line and an explicit
"flat by HH:MM ET, no overnight" — the user trades a headline-driven tape where
gap risk exceeds stop risk.

---

## 6. Answer direct factual questions first, plainly

Alongside a scan the user may ask something factual: *"is the war resolved yet
with hormuz?"* Answer it **first, in plain prose, with dated events** — do not
bury it beneath tables. Lead with the verdict ("NO. Not resolved. Not even a
ceasefire. It escalated this week."), then a dated bullet timeline, then the
trading read that follows from it.

`hormuzstraitmonitor.com/crisis-timeline/` carries a maintained dated timeline;
pair it with a news search scoped to the current week. Fold the result into
position design as **kill triggers**, not atmosphere: name the exact headline
that invalidates each leg.

---

## 7. Pair opposite-signed setups as a hedge, and say which you mean

Short-gold + long-oil during a Middle East conflict is not two independent bets
— a confirmed ceasefire dumps both, an escalation lifts both. Presented as a
pair with explicit kill triggers it is a hedged structure that survives the
binary. Presented as two rows in one table it implies stacked conviction.
Always state which. Same principle as the yen-cross/short-equity contradiction
pitfall in the main skill.

---

## 8. Blogwatcher has no commodity ticker coverage

`blogwatcher_integration.py` per-symbol sentiment tracks only BTC/ETH/SOL. It
has no XAU or CL ticker. For a gold/oil scan its `regime_shift_risk` and macro
event feed still apply (and the standing rule still requires running it), but
say plainly that the commodity read came from the macro feed plus a web pull,
**not** from a quantified per-symbol score. Do not imply coverage that isn't
there.
