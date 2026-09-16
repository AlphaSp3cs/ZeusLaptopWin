# Incident: D: volume discarded committed writes — 2026-08-08

Full transcript of the durability failure that motivated the fresh-handle
verification rule. Kept because the symptoms were genuinely confusing and a
future session hitting the same pattern should recognise it fast.

## Timeline

1. Built a unified OHLCV store at `D:\Hermes\workflow\data\bars.db`.
   Result: **1,778,734 bars, 435 symbols, 9 sectors, 232MB.** Readiness board
   printed ALL SECTORS READY. Verified by reading it back.

2. Launched a 1h backfill for the 105 Sunday-open symbols in the background.

3. Minutes later, `D:\Hermes\workflow\` contained only `README.md`. Everything
   else — `data/`, `scripts/`, the database — gone. All surviving entries
   timestamped `12:07`.

4. Three consecutive `ls /d/Hermes/` calls returned
   `No such file or directory`. A fourth returned the directory.

5. The pre-existing Hermes install that lived at `D:\Hermes` was ALSO gone:
   `config.yaml`, `bin/`, `cache/`, `clang64/`, `hermes-agent/`, and several
   `config.yaml.bak.*` files. **Not created or touched by this session.**

6. The background 1h job then completed and reported:

       [update] done in 172s - 1,209,758 bars written/updated
         OK 105   EMPTY 0   ERROR 0

   Its output did not exist. The process genuinely wrote, committed, and
   returned success against a path the filesystem was discarding.

7. Throughout: `df -h /d` reported `932G size, 671G avail`. Writes returned
   exit 0. `mount` showed the volume normally mounted NTFS.

## What made it hard to diagnose

- **Success was reported at every layer.** SQLite committed cleanly, the
  process exited 0, the summary line counted rows it had genuinely inserted.
- **Small writes survived.** A `persisttest/a.txt` created during triage
  persisted while a 232MB database and the entire pre-existing install did not.
- **It self-healed.** A controlled probe — 20,000 rows / 11.7MB SQLite, re-read
  after a 20s delay — passed cleanly, and the subsequent full rebuild verified
  at 1,837,554 rows on disk.

Because it recovered, the temptation is to call it transient and move on. The
correct read is that **the storage layer demonstrated it can silently discard
committed data**, so success reporting from that layer is no longer sufficient
evidence on its own.

## Rebuild results after hardening

    1d: 435/435 symbols   OK 435  EMPTY 0  ERROR 0
        [persistence] VERIFIED - 568,976 rows on disk (67 MB)
    1h: 106/106 symbols   OK 106  EMPTY 0  ERROR 0
        [persistence] VERIFIED - 1,782,217 rows on disk (232 MB)

## Diagnostics to hand the user

    chkdsk D: /scan
    Get-PhysicalDisk | Select FriendlyName,HealthStatus,OperationalStatus
    Get-WinEvent -LogName System -MaxEvents 50 |
      Where {$_.LevelDisplayName -match "Error|Warning"} |
      Format-Table TimeCreated,Id,Message -Wrap

Also check: OneDrive/Dropbox sync scope covering the directory, and any AV or
cleanup scheduled task firing near the wipe timestamp.

## Reporting posture

Do not quietly rebuild and present a clean result. The user needs to know their
pre-existing install was destroyed by something outside this session, because
it implies unbacked-up data elsewhere on the volume is at risk. State plainly:
what was lost, that it was not caused by the agent, what recovered, and what
they should run to diagnose the hardware.

## Related provider quirks found the same session

Both are the same species of bug — a field whose UNITS are inconsistent, where
the wrong reading is plausible rather than obviously broken:

- `yfinance` `pctHeld` on institutional holders is a **fraction**
  (`0.1474` = 14.74%). Printed raw it understates ownership concentration 100x.
  Observed: largest holder rendered as "0.15%" instead of "14.74%".
- `yfinance` `dividendYield` and expense ratio come back as a **percent for
  funds** (`3.13` = 3.13%) but a **fraction for equities** (`0.031`).
  Un-normalised this rendered a 3.13% yield as "313%".

Normalise on ingest:

```python
dy = f(info.get("dividendYield"))
d["div_yield"] = dy / 100 if (dy is not None and dy > 1) else dy
```

A wrong-by-100x number that still looks like a number will not raise anything.
Sanity-bound any ratio you print.
