# Sweeping a trading/scan system for bugs

Class of request: "make sure we have no bugs", "sweep our system entirely",
"check everything works before Monday". Run in this order — cheapest and
broadest first, highest-stakes last. Executed 2026-08-08 across ~194 files;
found one real bug the earlier targeted checks had missed.

## Order of operations

1. **Compile everything.** Cheapest possible net.
   ```bash
   for f in *.py; do python3 -m py_compile "$f" || echo "FAIL $f"; done
   ```

2. **Hunt infinite loops in anything a scheduler or router invokes.**
   `grep -nE "while True" <each script called by cron or the router>`.
   A `while True` in a script called via `subprocess.run` hangs until timeout.
   See the `--once` section in `verifying-scripted-integrations.md`.

3. **Mock/fake-data fallbacks.** `grep -ln "_generate_mock\|mock_data" *.py`.
   Then confirm each consumer BYPASSES it (CEREBRO: inject `sc.df = df`, never
   call `sc.scan()`). A scanner that silently returns a seeded random walk is
   the worst possible failure — it looks like data.
   Scope the grep to `*.py` in the target dir; a recursive `grep -r` from home
   times out on plugin caches.

4. **Scheduled jobs actually resolve.** Read the cron store directly rather
   than trusting formatted CLI output:
   ```python
   json.loads((Path.home()/'AppData/Local/hermes/cron/jobs.json').read_text())
   ```
   Confirm every job is enabled and every `script` / prompted command points at
   a file that exists. Then RUN the highest-stakes one and check its exit code.

5. **State-file integrity.** For each persisted state file, confirm the keys the
   PRODUCER writes are the keys the CONSUMER reads (see "Check your PROBE"
   in `verifying-scripted-integrations.md`).

6. **Force every refusal path.** Guards are the point of the system, so prove
   each one can actually stop a run — stale timestamps, cooldowns, halts.
   Assert the returned flag / exit code, not the printed message.

7. **Money-path invariants.** Assert orderings, not values (T5 > invalidation,
   T4 > T5, warn > invalidation).

8. **Contamination checks.** For crypto work confirm stablecoins, gold tokens
   (XAUT/PAXG/KAU/XAUM) and wrapped/LST receipts are excluded from candidate
   lists — they pass numeric filters but their edge isn't crypto's.

9. **Price cross-checks present.** Every consumer of yfinance prices must
   cross-check against CoinGecko spot with a ~15% divergence drop. This is what
   catches squatted/renamed feeds (APT reading $0.000131 vs a real $0.579).

10. **Secrets.** Confirm no API keys or order-placement calls in workspace
    scripts. Expect hits in vendored plugin caches — exclude those, don't
    "fix" them.

## What this sweep actually found

Steps 1–5 all passed. The real bug surfaced at step 6: a gate refusal that
printed correctly but exited 0. **The broad checks pass; the guard-forcing
checks find things.** Don't stop after the compile sweep.

## Tuning an alerter: stricter or more frequent both need design changes

Two adjacent requests from 2026-08-08, neither a parameter tweak:

- **Stricter / "defer that one too".** Widen the gate to a SET (e.g.
  `DEFER_SIGNALS = {"STRONG_SELL", "SELL"}`) so the next widening is one line.
  Then immediately ask: can the system still tell the user when conditions
  CLEAR? A stricter gate raises the odds that everything is blocked
  indefinitely and the user cannot distinguish "waiting" from "broken". Persist
  the blocked set and emit a RE-ARMED alert when an item drops out of it.

- **"Constantly" / higher cadence.** Naive run-over-run diffing breaks at high
  frequency — counters drift upward and every run fires. Three changes make it
  viable: escalate against a BASELINE FROZEN AT LAST ALERT (not the previous
  run), add a per-item cooldown, and write snapshots only when something
  alerted (48 runs/day otherwise buries the history dir).

**Verify anti-spam with the silence test, never by reading one run:**

```
cold start                                      -> alerts
immediate re-run                                -> SILENT
third re-run                                    -> SILENT
age last_alert past cooldown AND lower baseline -> alerts again
```

If run 2 is not silent, the baseline freeze is broken and the user will mute
the whole system.

## Reporting shape

Lead with the new bug(s) found and fixed. Then list what passed, each with the
evidence that it was actually exercised (not merely inspected). Then disclose
any false alarms caused by your own probes — hiding those is worse than the
phantom bug itself.
