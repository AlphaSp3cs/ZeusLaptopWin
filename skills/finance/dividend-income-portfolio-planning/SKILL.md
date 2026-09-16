---
name: dividend-income-portfolio-planning
description: Use when ordering a ticker list into an income buy plan.
---

# Dividend & Income Portfolio Planning

Covers the class of task: "take a list of tickers and produce an ordered,
executable buy plan" — especially when the user's stated goal is **income**
(monthly cash flow) rather than pure capital appreciation.

## Trigger conditions

- User supplies a tier/watchlist of tickers and asks for "buy order",
  "order to buy", "for tomorrow's open", or "put them in the doc".
- User says the goal is monthly income, dividends, cash flow, or "pays me".
- User asks to re-rank an existing plan by a different objective.

## Core principle: order by the stated objective, not by a generic score

The single most common mistake is ranking by a technical score (RSI, momentum)
when the user asked for **income**. If the user says "the ones that make me a
monthly income", the primary sort key is income delivery. RSI becomes a
tie-breaker and an entry-price input, not the ranking axis.

Always produce a *separate* doc rather than overwriting a prior plan built on a
different objective. Cross-link the two so neither is orphaned.

## The pay-month cycle framework (the load-bearing insight)

US companies pay quarterly on one of three cycles. Owning one name from each
cycle converts a lumpy quarterly income stream into a monthly one.

| Cycle | Pay months |
|-------|-----------|
| Cycle 1 (JAJO) | Jan · Apr · Jul · Oct |
| Cycle 2 (FMAN) | Feb · May · Aug · Nov |
| Cycle 3 (MJSD) | Mar · Jun · Sep · Dec |

Rule to encode in every income plan: **buy one name from each cycle before
buying a second name from any cycle.** True monthly payers (e.g. `O`) fill all
twelve months alone and should be ranked first in an income ordering.

Derive the cycle empirically from the dividend history — do NOT assume it from
the sector or guess. See `scripts/dividend_profile.py`.

## Workflow

1. **Check for prior work.** `session_search` for earlier buy plans / analysis
   docs for the same tickers, and check the filesystem for the doc the user is
   referring to ("inside the doc"). Read it before writing a new one.
2. **Pull live dividend data** with `scripts/dividend_profile.py`. Capture per
   ticker: price, yield, annual rate, actual pay months, payout ratio, and
   5-year dividend CAGR.
3. **Persist the raw dataset** to a JSON file next to the doc so the numbers in
   the plan are auditable and the next session doesn't re-fetch blind.
4. **Rank each tier** by: current income contribution → cycle diversification →
   entry quality (RSI/price vs EMA).
5. **Write the doc** with the sections in "Output shape" below.
6. **Cross-link** from any pre-existing plan doc to the new one.

## Sector risk distribution & 52-week-low entry (drawdown control)

When the user asks to *manage risk across sectors*, *minimize drawdown*, or *order by
closeness to the 52-week low*, extend the plan with this layer (condensed; see
`references/sector-risk-and-52w-low-ordering.md` for the full technique + yfinance 1.5.x fixes):

- Tag every holding by sector; compute per-sector realized **MaxDD** (trailing-12m deepest
  peak-to-trough). Cap single-sector weight ≤20%, raised to ≤22% for low-drawdown sleeves,
  cut to ≤14–18% for high-drawdown sleeves (Tech/AI, Telecom). Equal-weight across sectors
  is the lowest-drawdown posture.
- Order the primary list **grouped by sector, each group sorted ascending by % above
  52-week low** (cheapest entry first). Build a one-cheapest-per-sector shortlist for instant
  sector spread + margin-of-safety entries.
- State the caveat: near-52w-low is cheapness vs the past year, not a forward signal; keep
  MaxDD and %-positive-swing columns beside it so entries aren't blind.
- **Emit a model book with per-sector dollar weights** (e.g. a $100k illustrative allocation):
  cap% × capital per sector, each sector deployed into its cheapest names first. This makes the
  drawdown control actionable, not just a table.
- **Segregate the DRIP/income hold book from any swing/prop-firm book.** Income backtests win on
  dividends but lose on price (PG: 97% of 1y windows negative *price* return; KMB 100%). Don't let
  a dividend name into the swing book just because its yield is high.
- **Regime filter (swing side):** no new longs when the broad index is below its 200-day. In the
  OB 2026 data late-2024 was a broad drawdown (10–13 of 45 names lost together on 1y holds).
- The honest-backtest / FTMO-validation side (same-bar look-ahead, phantom P&L, walk-forward) lives
  in the `trading-backtest-integrity` skill — consult it before trusting ANY backtest number.

## Output shape that works for this user

The user wants an execution artifact, not an essay. Include:

- A per-tier table with: buy #, ticker, price, yield, annual $/share, pay
  months, cycle, 5y div CAGR, payout ratio, RSI, **explicit entry limit price**,
  and a one-line "why this slot".
- A consolidated "12-month paycheck blueprint" — a single ordered buy list
  across all tiers with running blended yield and which months are now covered.
- A timed execution script for the open (08:30 refresh, 09:30 tranche 1, etc.).
- Explicit SKIP / AVOID entries with the reason, not silent omission.
- Sell rules framed against the *stated objective* (income thesis breaks), so
  price drops read as buy signals rather than sell signals.
- DRIP compounding table (yield-on-cost by year) — this is the payoff the whole
  plan is arguing for.

Order limits, never market orders, for income positions. State a step-up rule
(e.g. raise limit in $0.50 steps, max 3 steps) so the plan is actionable when
unfilled.

## Pitfalls

- **A REIT payout ratio over 100% is not a red flag.** REITs are measured on
  AFFO, not GAAP EPS. `O` showed 265% payout while its AFFO payout was ~75%.
  Call this out explicitly in the doc or the user will read it as distress.
- **A negative 5-year dividend CAGR means the dividend was cut.** This is a hard
  exclusion for an income plan, regardless of how good the other metrics look.
  Flag it loudly rather than quietly dropping the name.
- **A negative CAGR can also be a special-dividend artifact.** `CME` pays a
  variable annual special dividend; the computed CAGR was -7.6% while its real
  all-in yield was ~4-4.5%. Check whether the dividend series has irregular
  large payments before concluding a cut.
- **Low yield ≠ bad income holding.** A 0.8% yield on a 20% payout ratio with
  15% dividend growth outranks a 3% yield on an 85% payout with 1% growth over a
  holding period. Separate "income today" from "growth of income" and say which
  slot each name occupies.
- **High payout ratio caps future raises.** Names above ~80% payout (with
  non-REIT accounting) should be labelled income-now, not income-compounder.
- **Windows paths in `printf`:** `printf 'C:\Users\victo\...'` mangles the path —
  bash interprets `\U` as a unicode escape and `\v` as a vertical tab. Use
  `write_file` / `patch` for content containing Windows paths, or single-quote
  and avoid `printf` entirely.
- **Live-fetch gotchas — yfinance 1.5.2 on system Python 3.13 (this workspace).** Three traps break a backtest on the first run: (1) `Ticker.history(..., progress=False, actions=True)` raises `unexpected keyword argument 'progress'` — drop `progress` and `actions`; use `t.history(period="3y", interval="1wk", auto_adjust=True)`. (2) The dividend series index is tz-aware (`America/New_York`); comparing to `datetime.datetime.now()` raises `Cannot compare tz-naive and tz-aware`. Build cutoffs with `pd.Timestamp.now(tz=divs.index.tz)` (fall back to `pd.Timestamp.now()` if naive). (3) `Ticker.dividends` can come back empty even when dividends exist — fall back to `Ticker.get_dividends()`. A working fetch wrapper is in `scripts/backtest_income_swing.py`.
- **Backtest + rank when asked for "best swing trades + highest dividend."** Do NOT rank by yield alone. Run a weekly-entry rolling 1-year hold backtest (price + realized dividends, no DRIP/tx costs) and report both `% positive windows` (swing reliability) and `median total return`. High yield + weak swing (e.g. PFE in the OB 2026 run: 6.5% yield but only 70.5% positive windows, negative 3y price) is an income-now trap, not a swing. Screen `>=90% positive AND >=20% median` for the quality-income set. Trailing 3y total returns are REALIZED (caught the 2023-26 bull) — use them as context, not as forward projections.
- **Never assert a reason you have not read from the data.** When excluding or
  down-ranking a name, open the underlying record (dividend history, payout
  series, validation output) and quote the actual figure. Grouping two names
  under one asserted cause is the failure mode: they usually fail for different
  reasons, and the user will check. If you have not verified it, say you have
  not verified it.

## Related skills

For running the scan pipelines that produce the RSI/ATR/technical inputs used
as entry-quality tie-breakers here, see `market-scan-pipeline-runs`.

## Support files

- `scripts/dividend_profile.py` — fetches price, yield, pay months, payout
  ratio, and 5y dividend CAGR for a ticker list; emits JSON.
- `scripts/backtest_income_swing.py` — reusable LIVE backtest + highest-yield
  ranking. `python3 backtest_income_swing.py --tickers ARCC,MAIN,MO,O` or
  `--html "C:\path\to\report.html"`. Pulls live price/dividends, runs a
  weekly-entry rolling 1y long-swing backtest (price + realized divs), decomposes
  trailing 3y price-vs-income, ranks by live yield (highest first), applies the
  `>=90% positive / >=20% median` quality screen, and emits a cycle-diversified
  LIMIT-order buy plan + `<out>.json` raw snapshot. Handles the yfinance 1.5.2
  gotchas above out of the box.
- `references/income-ordering-worked-example.md` — a full worked ordering
  across three tiers with the reasoning per slot.
- `references/sector-risk-and-52w-low-ordering.md` — sector concentration caps,
  52w-low proximity ordering, and yfinance 1.5.x live-fetch fixes for extending an
  income plan into a drawdown-controlled, margin-of-safety-ordered book.
