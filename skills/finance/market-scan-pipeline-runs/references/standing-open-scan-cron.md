# Standing all-sector OPEN SCAN cron

Pattern for making the all-sector scan fire automatically at each session open,
so the x4-relative-volume + gap-up stock hard-gate catches a real gap-up equity
event when one occurs (instead of only when the user manually asks).

## Why a cron at all

The user's stock filter (>=4x 50d vol, longs gap-up) correctly returns ZERO most
days — there is simply no high-volume gap-up equity event in the universe most
sessions. A manually-triggered scan therefore "misses" nothing; but the user wants
the screen to RUN automatically at the open so a genuine event is captured and
flagged without re-asking. A standing cron is the right delivery.

## The runner

`scripts/standing_open_scan_cron.py` (home dir copy: `cron_allsector_open_scan.py`).
Self-contained: runs `run_universal_workflow.py --scan-only` then `--gate-only`,
layers blogwatcher RSS + danger-zone gauge, writes `ALLSECTOR_OPEN_YYYYMMDD.md`
and prints a one-line summary (gauge / regime / #GO / top-stock vol ratio).

It resolves the pipeline dir automatically (works whether the script sits in the
skill's scripts/ dir or the home dir), so it survives being copied between the two.

## Scheduling

Two daily jobs (forever), created with `cronjob action=create`:

  Job 1 "All-Sector Open Scan (US premarket)"   schedule "37 9 * * *"   (09:37 ET, right after US cash open)
  Job 2 "All-Sector Open Scan (London/afternoon)" schedule "37 14 * * *" (14:37 ET, once London/NY overlap is live)

Both: `enabled_toolsets=["terminal","file"]`, prompt runs the script from
`C:\Users\victo`, then summarizes gauge / regime / GO count / top-stock-vol and
flags explicitly if a gap-up stock event is present.

## Delivery caveat (Windows CLI)

CLI/TUI cron jobs are LOCAL-ONLY: output writes to `ALLSECTOR_OPEN_YYYYMMDD.md`
and the job log, but does NOT push into the terminal. To get a ping, recreate the
job with `deliver='telegram'` (or 'all') against a connected gateway.

## Smoke test before scheduling

Always run the script once in the foreground/background first to confirm it runs
end-to-end (scan + gate + news + gauge + markdown write) before relying on the
cron. Verified working 2026-08-06: 11 GO, gauge 82.5, regime HIGH, top stock vol
1.14x (no event), report written.
