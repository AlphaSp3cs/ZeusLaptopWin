# Worked Example: Income Ordering Across Three Tiers

Session artifact from 2026-08-04. The user had an existing buy plan ordered by
RSI and asked to reorder "the ones that make me a monthly income". This is the
reasoning that produced the ordering — reuse the *logic*, refetch the *numbers*.

## The reframe that mattered

The prior doc (`buy_plan_tomorrow.md`) ranked 30 names by RSI — a technical
entry score. The user's goal was income. Same universe, completely different
correct order. RSI was demoted to an entry-limit input.

Rather than overwrite, a second doc (`monthly_income_buy_plan.md`) was written
and the two were cross-linked. Both objectives stay available.

## Slot reasoning — Tier 2 (the tier the user named)

| # | Ticker | Yield | Cycle | 5y CAGR | Payout | Reason for the slot |
|---|--------|-------|-------|---------|--------|---------------------|
| 1 | O | 5.09% | MONTHLY | 5.9% | 265%* | Only true monthly payer; 2× the tier's next yield. Fills the whole calendar alone, so it must be first. |
| 2 | ITW | 2.24% | 3 | 7.1% | 58% | #2 yield + 58-yr growth streak. Anchors Cycle 3. |
| 3 | CME | 1.95% | 3 | -7.6%† | 95% | Negative CAGR is a special-dividend artifact, not a cut. Real all-in yield ~4.0-4.5%. |
| 4 | ABT | 2.38% | 1 | 7.0% | 79% | Only meaningful Cycle-1 anchor in the tier — this buy opens Jan/Apr/Jul/Oct. |
| 5 | EMR | 1.43% | 2 | 1.3% | 50% | Anchors Cycle 2, but growth stalled to 1.3% and RSI 69.5. Resting limit only, no market buy. |
| 6 | DE | 1.09% | 3 | 13.5% | 37% | Low yield now, but 13.5% growth on a 37% payout doubles yield ~every 5.5 yrs. The tier's income compounder. |
| 7 | ROP | 0.93% | 1 | 10.0% | 14% | Lowest payout in the tier = most room to raise. Second Cycle-1 payer. |
| 8 | PH | 0.82% | 2 | 15.4% | 27% | Fastest growth + 68-yr streak. Second Cycle-2 payer. |
| 9 | DHR | 0.82% | 3 | 14.5% | 26% | Best entry (RSI 51.7). Income is incidental; owned for compounding. |
| 10 | TMO | 0.33% | 3 | 13.4% | 10% | Lowest yield of all 30. Pure capital compounder — last if income is the goal. |

\* REIT — AFFO payout ~75%. Not distress.
† Variable annual special dividend distorts the series.

**Key result:** buying just #1-4 (O, ITW, CME, ABT) covers all twelve months.
That fact is more useful to the user than the full ranked list, so it was
surfaced explicitly rather than left implicit in the table.

## Cross-tier blueprint

The three tier tables were then collapsed into a single 15-name ordered list
with a running blended-yield column and a "months now covered" column. Order was
driven by cycle-fill first, yield second:

O (all 12) → PEP (C3) → CVX (C2) → PG (C1) → then depth in each cycle.

After 15 buys: ~2.84% blended yield, every month paid 3-4×, ~6.4% blended
dividend growth. The DRIP table then projected yield-on-cost to 33% at year 30 —
that projection is the argument for the whole plan and belongs in the doc.

## Exclusions worth stating out loud

- **MMM** — 5y dividend CAGR of -12.4%. The dividend was cut. Hard exclude from
  an income plan even though other metrics looked acceptable. Say why; don't
  drop it silently.
- **EMR** — not excluded, but deferred. RSI 69.5 and +11% over EMA20 with 1.3%
  dividend growth. A resting limit well below market is the right instruction.

## Delivery note

The user reads output in a terminal. The response led with the file path and the
reordered Tier 2 list in plain text, then flagged the two judgement calls (MMM
cut, O's REIT payout optics) at the end. No markdown tables in the chat reply —
those live in the doc.
