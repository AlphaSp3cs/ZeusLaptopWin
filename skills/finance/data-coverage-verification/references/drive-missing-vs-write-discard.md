# D: drive entirely missing — distinct from write-discard (2026-09-14)

The 2026-08-08 incident (see `storage-durability-incident-2026-08-08.md`)
covered a volume that **silently discarded committed writes** while staying
mounted. This note covers the distinct failure mode observed 2026-09-14:
the D: drive is **entirely absent** from the filesystem.

## Symptoms

- `ls /d 2>/dev/null` returns nothing
- `ls /d/Hermes 2>/dev/null` returns `No such file or directory`
- `Get-PSDrive -PSProvider FileSystem` shows only C: (and Temp mapped to C:)
- Every path reference to `D:\Hermes\workflow\` fails
- `bars_db.py` (hardcoded `ROOT = pathlib.Path(r"D:\Hermes\workflow")`)
  cannot open the database

## Impact on the scan pipeline

1. `scan.py` line 142: `BARS = pathlib.Path(r"D:\Hermes\workflow")` — every
   `bars_refresh()` call fails with MISSING
2. `bars_db.py` line 37: `ROOT = pathlib.Path(r"D:\Hermes\workflow")` —
   `DB = ROOT / "data" / "bars.db"` does not exist
3. `market_open_ready.py` at `D:\Hermes\workflow\scripts\` — missing,
   only backup exists at `C:\Users\victo\hermes_backup_20260808\`
4. Backtest engine (`bt_store.py`, `bt_runner.py`) — cannot read bars.db
5. Sentiment aggregator at `D:\Hermes\skills\...` — missing

## Diagnostic commands

```bash
# Is D: mounted at all?
ls /d 2>/dev/null && echo "D: EXISTS" || echo "D: NOT FOUND"

# PowerShell drive check
powershell.exe -Command "Get-PSDrive -PSProvider FileSystem | Select-Object Name"

# Drive health (run elevated)
wmic logicaldisk get size,freespace,caption /format:csv

# Check for USB/external drive that might be D:
Get-Disk | Select-Object FriendlyName,BusType,HealthStatus
```

## Options when D: is missing

1. **Restore D: drive** — if it was an external USB that got unplugged,
   reconnecting restores everything instantly. The 2026-08-08 incident
   suggested the volume can self-heal.

2. **Migrate to C:** — if D: is permanently gone, `bars_db.py` and `scan.py`
   need their `ROOT`/`BARS` paths updated to a C: location. Copy
   `D:\Hermes\workflow\data\bars.db` from backup if available, or
   re-fetch from yfinance.

3. **Use `--no-bars` flag** — `python3 scan.py premarket --no-bars` skips the
   bar refresh but still fails when trying to read bars.db for the gate.

4. **Direct Yahoo Finance API** — for price-only reads, use the chart API
   directly (see `finance:market-scan-pipeline-runs` reference
   `references/fallback-scanning-without-backend.md`). This bypasses the
   entire local storage layer.

## Prevention

- Code masters live on C: per workspace law, but the DATA lives on D:. If D:
  is external/USB, it's a single point of failure.
- Consider mirroring bars.db to C: periodically, or using cloud storage.
- The `scan.py` startup should ping D: and warn early rather than failing
  deep into the pipeline.

## Related

- `storage-durability-incident-2026-08-08.md` — the write-discard failure mode
  (different symptoms: volume present but data disappears after commit)
