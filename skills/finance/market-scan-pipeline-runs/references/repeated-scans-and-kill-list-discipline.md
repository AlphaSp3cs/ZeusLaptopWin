# Repeated scans in one session: kill-list discipline and refusal

Worked record from 2026-08-05, where the user ran the all-sector scan three
times in four hours and asked for gold levels five separate times. The value of
this session was almost entirely in what was *refused*.

## The three runs

| Run (UTC) | GO setups | Qualified shorts | Survived backtest |
|---|---|---|---|
| 10:29 | 14 | 9 index/sector shorts | XLU L, HYG S, XLE S (+3 marginal) |
| 13:31 | 8  | ^GSPC, ^IBEX | BNB L, TRX L (+2 marginal) |
| 14:40 | 5  | **zero** | BNB L, TRX L (+2 marginal) |

Meanwhile RSI *rose*: ^GSPC 66.3 → 68.5 → 67.5, ^DJI 66.7 → 69.2 → 70.1,
^GDAXI 69.5 → 70.1 → 69.8.

Read: a gate producing fewer and worse setups while the tape extends is a
late-cycle signature. Report the trend across runs, not just the current
snapshot. "Zero shorts validated in an EXTREME DANGER regime" was the single
most informative line of the third report.

## Names the scanner re-emitted after rejection

| Symbol | Side | Runs emitted | Win% | Avg R | PF | Verdict |
|---|---|---|---|---|---|---|
| ^GSPC | SHORT | 1, 2 | 15.8 | −0.537 | 0.32 | rejected each time |
| ^IBEX | SHORT | 1, 2 | 23.8 | −0.433 | 0.38 | rejected each time |
| DOT-USD | LONG | 1, 2, 3 | 40.0 | −0.129 | 0.74 | rejected 3× |

The backtest returned **identical numbers to three decimals** each time. That
reproducibility is the evidence: the rejection is structural (a bull-market
artifact in the entry rule), not sampling noise.

Practical rule: re-run the backtest rather than refusing from memory — it costs
one script invocation and converts "I remember this was bad" into a citable
table. Then show the prior and current figures together.

## Standing kill list as of 2026-08-05

```
SHORT ^GSPC 0.32 | SHORT ^IBEX 0.38 | SHORT SPY 0.40 | SHORT QQQ 0.44
SHORT XLI 0.35  | SHORT XLF 0.54  | SHORT XLK 0.68 | SHORT XLB 0.80
SHORT XLY 0.96  | LONG UNG 0.71   | LONG DOT-USD 0.74
```

All are RSI>60 index/sector fades except the two longs. Any future scan that
surfaces one of these needs the re-backtest + re-rejection treatment.

## The gold refusal sequence

The user asked for actionable gold levels five times as price ran
4213 → 4259 → 4294 (+4.9% on the day, a 2.3× ATR range).

1. Short @ 4225, stop 4236.50 — **stopped out**.
2. Short @ 4270, stop 4295 — would have stopped out in the 10:15 bar.
3. Declared 4300 as the invalidation line. Price hit 4298.90.
4. Refused a third short. Gave conditional levels only, gated on a 15m lower
   high AND 5m RSI back under 60.
5. Refused again when the gate re-emitted `WATCH SHORT GC` at successively
   higher prices (4253.90 → 4299.80) — the gate was chasing price up.

What made the refusal correct and legible:
- **Stated the losses first**, unprompted, before answering the new question.
- Distinguished *structure* (still bearish: −4.11% vs a falling 200-day, 28%
  off the 52w high) from *momentum* (flipped bullish: daily RSI 43.8 → 62.4,
  reclaimed the 50-day, 8 consecutive higher 5m closes). Both true; momentum
  governs the next few hours.
- Refused the long too — not because the tape was wrong but because gold longs
  backtest at PF 0.75–0.84. Symmetry proves the discipline isn't directional
  bias.
- Named the invalidation *in advance*, then honoured it when hit.
- Tied it to the user's own instruction: chasing a fifth number is the same
  error the scanner makes with SPY.

Also note: a `WATCH` verdict was never backtested and passed only the liquidity
check. It is not a fallback when the GO list is empty.

## Report skeleton for run N>1

1. **What changed since the last run** — GO count delta, RSI drift table, new
   names appearing, names that vanished.
2. Regime (gauge + blogwatcher), unchanged in structure from run 1.
3. Per-class coverage counts.
4. Backtest table for this run's GOs.
5. Positions with fresh prices — re-pull, never restate a stale entry.
6. **Rejected this run** + **standing kill list**.
7. WATCH section, clearly not tradeable.
8. The read, including the cross-run trend.
