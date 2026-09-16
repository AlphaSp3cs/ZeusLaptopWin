---
name: bar-store-operations
description: Use when refreshing market bars or prepping for market open.
---

# Bar Store Operations (D:\Hermes)

Unified OHLCV store feeding every sector scan. Data on D: per workspace law
(671GB free vs 54GB on C:). **Script source masters live on C: and are mirrored
to D: automatically** — see the durability warning below.

## Commands

    python3 ~/bars_db.py --init                       # register universes
    python3 ~/bars_db.py --update                     # incremental daily, all
    python3 ~/bars_db.py --update --tf 1h --sector crypto --sector fx
    python3 ~/bars_db.py --status
    python3 ~/market_open_ready.py --json             # sector readiness board

Via the router:

    python3 ~/scan.py ready        # readiness board only
    python3 ~/scan.py bars         # refresh + readiness
    python3 ~/scan.py premarket    # auto-refreshes bars first
    python3 ~/scan.py <mode> --no-bars

## Coverage

9 sectors, 435 active symbols: crypto 43 · equity 324 · fx 15 · metals 7 ·
energy 8 · ags 8 · indices 15 · bonds 10 · dividend 20.
Daily 1d for everything; 1h for the Sunday-open sectors (crypto, fx, metals,
energy, indices, bonds, ags).

Timings: full 1d rebuild ~5.5 min / ~570k bars. 1h for 105 symbols ~3 min /
~1.2M bars.

## Session opens (Sunday night ET)

    17:00  fx (Sydney)
    18:00  metals, energy, indices futures, bonds futures
    19:00  ags (CBOT grains)
    Mon 04:00  equity pre-market
    Mon 09:30  equity regular / cash indices
    crypto     24/7

## !! CONCURRENT SESSIONS SHARE THIS STORE

**Root cause of the 2026-08-08 "vanishing directory" incident: a SECOND Hermes
session was working in `D:\Hermes\workflow` at the same time**, creating
`backtest/` and its own C:\Users\victo\bt\ masters. Directories appeared and
disappeared between consecutive commands because another agent was reorganising
the tree concurrently — not (only) a failing drive.

Before blaming hardware, check for a co-worker:

    ls -lat D:\Hermes\workflow\            # dirs you did not create
    ls -lat C:\Users\victo\bt\             # other sessions' script masters

Rules for shared use:
- Create your subdirectory immediately before writing into it; never assume it
  survived from an earlier command in the same session.
- `bars.db` itself has held up fine under concurrent access (WAL + 60s busy
  timeout). Readers are safe while another session writes.
- Do NOT `rm -rf` anything under `D:\Hermes\workflow` you did not create.

## !! DURABILITY: D: SILENTLY DISCARDED A COMMITTED WRITE

On 2026-08-08 `D:\Hermes` lost a fully committed 1.78M-bar / 232MB database
**and** the pre-existing Hermes install (config.yaml, bin/, clang64/). A
subsequent 1.2M-bar job reported `OK 105 EMPTY 0 ERROR 0` and its output was
gone seconds later. Directory listings flickered between present and
"No such file or directory" across consecutive commands.

Consequences baked into the tooling:

1. `bars_db.py` uses `PRAGMA synchronous=FULL`.
2. After every update it calls `verify_persisted()` — reopens the DB on a
   **fresh handle** and re-counts rows. A clean commit is NOT proof of
   persistence on this volume.
3. Both scripts `mirror_source()` themselves back to `C:\Users\victo\` on every
   run, so a D: wipe can never destroy the source again.
4. Never edit only the D: copy. Edit the C: master, then copy across.

**If `--update` prints `[persistence] FAILED`, treat the store as EMPTY. Do not
scan against it.** Check drive health first:

    chkdsk D: /scan
    Get-PhysicalDisk | Select FriendlyName,HealthStatus,OperationalStatus

## Doctrine

- A symbol returning no data is **UNCOVERED**, recorded in `fetch_log`, printed
  loudly. Its absence from a scan is not a "no signal" reading.
- Weekend staleness is expected for anything that closed Friday; the readiness
  check tolerates `--max-age-days` (default 5).
- Retired symbols (delisted/acquired) are deleted from `symbols` and kept in
  `retired` so `--init` can't resurrect them. Currently: K, WBA, IAC, IPG, SEE,
  WRK, AGR, SOHO, OTRK.
- The store answers WHEN. Fundamentals come from `valuation_scorecard.py`.
  `enhanced_trade_gate.py` remains the only authoriser. Nothing here trades.

## Schema

`bars(symbol,tf,ts,ohlcv)` PK(symbol,tf,ts) upsert · `symbols` · `symbol_tags`
(multi-bucket membership — a symbol in two sectors would otherwise understate
coverage) · `fetch_log` (per-symbol last status) · `retired`.
