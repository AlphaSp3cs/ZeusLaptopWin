---
name: valuation-scorecard
description: Use before any equity buy or accumulate call.
---

# Equity Valuation Scorecard

Price/flow scans say WHEN. This says WHETHER the business is worth owning.
No equity accumulate call goes out without it. DCF fair value, justified P/E,
6-point scorecard, narrative layer, ownership/accumulation math.

## Run it

    python3 ~/valuation_scorecard.py NTNX [MORE...] [--target-pct 5] [--json out.json]
    python3 ~/scan.py value --value NTNX MSFT        # via the router
    python3 ~/scan.py premarket --value NTNX          # bolted onto a scan

`scan.py premarket|allsector` auto-derives up to 10 tickers from the scan JSON
when `--value` is omitted. Output JSON lands at `~/valuation_latest.json`.

## The 6-point scorecard

| # | Check | Passes when |
|---|-------|-------------|
| 1 | valuation  | price <= DCF fair value (positive margin of safety) |
| 2 | fair_ratio | trailing P/E <= justified P/E (Gordon), not raw peer P/E |
| 3 | growth     | revenue growth > 0 AND FCF positive |
| 4 | quality    | gross margin > 35% AND (ROE > 10% OR FCF margin > 10%) |
| 5 | balance    | net debt/EBITDA < 3, or net cash |
| 6 | ownership  | institutional 40-90% (sponsored, not captured) |

**4-6 accumulate | 2-3 mixed | 0-1 avoid**

## Hard rules

- **`n/a` is NOT a pass.** Missing data downgrades confidence; the report prints
  an explicit UNVERIFIED count. Same doctrine as signal-provenance-audit —
  silence is never confirmation.
- **The scorecard authorises research and DCA sizing, never an order.** Trade
  entries still route through `enhanced_trade_gate.py`.
- **DCF assumptions are clamped on purpose**: discount = 4.3% RF + beta x 5.0%
  ERP, floored 8% / capped 15%; growth clamped [-5%, +20%] and faded linearly to
  a 2.5% terminal over 10 years. If you widen these, say so in the writeup.
- **Justified P/E assumes 35% payout** when the company pays no dividend. The
  report flags `[payout assumed 35%]` — for hyper-growth no-payout names this
  check is structurally harsh; read it as "rerate room", not a verdict.
- **DCA REMINDER RULE applies**: if a name scores 4-6, say it outright —
  "DCA [TICKER] now!" — never buried in a table.

## Narrative layer (mandatory before sizing)

Fill all four or the scorecard is incomplete:
1. price drivers -> what actually moves the quote
2. financial path -> which line item those drivers land in
3. ownership behavior -> who is accumulating/distributing and why
4. catalyst + date -> the dated event that forces a re-rate

## Ownership / "largest shareholder" math

Printed automatically:
- shares needed = shares outstanding x target %
- cost = shares needed x price
- % of free float consumed
- time horizon at 5/10/25% of average daily volume
- largest institutional holder and the % you must exceed to overtake them

**Pitfall (fixed 2026-08-08):** yfinance `pctHeld` is a FRACTION (0.1474 =
14.74%). Printing it raw understates concentration 100x. The script normalises
it and falls back to shares/shares-outstanding when missing.

## ETFs / funds are NOT scored

Detected via `quoteType` and routed to a **fund report** instead. DCF, justified
P/E, ROE, net debt and single-name ownership do not apply to a basket. Scoring
SCHD/VYM on company metrics produced a bogus **0/6 AVOID** — a data artifact,
not a verdict. Funds print "NOT SCORED (fund)" plus AUM, expense, yield, 52w
position and returns. Judge them on expense, yield, distribution growth,
holdings overlap and trend; for DRIP they are buy-and-hold sleeves.

**Pitfall (fixed 2026-08-08):** yfinance returns `dividendYield` and expense
ratio as a PERCENT for funds (3.13 = 3.13%) but a FRACTION for equities
(0.031). Un-normalised this printed "yield 313%". Both are normalised to
fractions on ingest.

## Justified P/E can exceed trailing P/E wildly

For low-beta defensives (PEP justified 39.9 vs actual 18.2; O justified 125.3)
the Gordon formula explodes as g approaches r. Check #2 passing is NOT a
"cheap" signal on these — read the DCF margin of safety instead. The clamp
`g <= r - 0.02` prevents a negative denominator but the result is still
structurally inflated for slow-growth high-payout names.

## Broker rule

Accumulation of REAL equity requires a share-dealing broker (Alpaca, eToro
invest mode). **CFD-only venues (Capital.com, FTMO) give exposure, not
ownership** — they can never build a shareholder position, no dividends, no
voting. Never route an accumulation plan to a CFD account.

## Re-score triggers

- Quarterly, after every earnings print
- Guidance revision or analyst target revision cluster
- Ownership move: 13D/13G filing, insider cluster, largest-holder change
- Price move >= 25% from last scored price
