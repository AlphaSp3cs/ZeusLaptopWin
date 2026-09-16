---
name: crypto-dca-ladder-reminders
description: Use when building a staged DCA buy ladder with alerts.
---

# Crypto DCA Ladder with Live-Tape Refresh + Reminders

Class of request: "build me a DCA ladder into <names> with exact tranche sizes
and invalidation levels, and remind me when to buy." Downstream of the bottom
study in `cerebro-crypto-scan` → `references/crypto_bottom_research.md`.

Validated 2026-08-08 on NEAR/INJ.

## Architecture — three files, one chain

1. **`dca_tape_refresh.py`** — pulls live tape, writes `dca_ladder_levels.json`.
2. **`dca_ladder_check.py`** — reads that file, evaluates tranches, toasts.
3. **`~/.hermes/scripts/dca_ladder_cron.sh`** — refresh THEN check, weekly cron.

**The ordering is the whole point.** Never let the checker run on hardcoded
levels. Refresh first, and make the checker refuse stale tape.

## Non-negotiable safety rails

- **Staleness gate.** Checker reads `refreshed` from the levels file; if older
  than `MAX_TAPE_AGE_H` (36h) it BLOCKS every buy rather than acting on old
  numbers. Silent staleness is how a ladder buys into a broken thesis.
- **Price cross-check before overwriting levels.** CoinGecko spot vs yfinance
  last close; if `abs(yf/cg-1) > 0.15` REFUSE to update that symbol and record
  `error: price_mismatch`. yfinance `-USD` feeds for renamed tokens are squatted
  (APT/POL/UNI/SUI all read ~$0.0001 in 2026-08). Never silently accept.
- **Weekly close for invalidation, never daily.** These assets run 54–69%
  annualised vol; a daily wick under the cycle low is noise. Breach flips the
  symbol to `halted` in state and requires a MANUAL state-file edit to resume.
- **Tranche levels floored above invalidation.** Recompute as
  `t4 = max(px*0.85, low*1.30)`, `t5 = max(px*0.72, low*1.12)`. Without the
  floor, a falling price drags the buy levels below the stop — you'd be adding
  into a thesis you already called dead.
- **CEREBRO overlay defers SCHEDULED buys only.** Gate on a `DEFER_SIGNALS`
  SET, not a hardcoded string — the user widened it from `{STRONG_SELL}` to
  `{STRONG_SELL, SELL}` on 2026-08-08 when a full cryptoweekend scan returned
  ZERO non-SELL names across the whole tape. Time-based tranches defer;
  price-triggered ones still fire — the entire point of a lower tranche is to
  catch weakness. Blocking those would defeat the ladder.
- **A fully-deferred ladder is SILENT under `--quiet` — add a re-arm alert.**
  Persist `deferred_last` in the state file; when a symbol drops out of that
  set, toast "RE-ARMED". Without it the user hears nothing for weeks and has no
  idea whether the system is waiting or broken. Report the ACTUAL signal in the
  defer reason (`f"CEREBRO {signal}"`), never a hardcoded label.

## CEREBRO integration — inject, never `sc.scan()`

`CerebroScanner.fetch_crypto_data()` catches ALL exceptions and returns
`_generate_mock_data()` — a seeded random walk. Bypass:

```python
sys.path.insert(0, str(Path.home()/"workspace"/"think-tank"/"scanners"))
from cerebro_scan import CerebroScanner
ex = ccxt.binance(); mk = ex.load_markets()
pair = f"{sym}/USDT"                    # /USDT not /USD — /USD hits mock path
if pair not in mk or not mk[pair].get("active"): skip
ohlcv = ex.fetch_ohlcv(pair, timeframe="1h", limit=200)
df = pd.DataFrame(ohlcv, columns=["ts","open","high","low","close","volume"])
sc = CerebroScanner(pair, timeframe="1h")
sc.df = df.set_index(pd.to_datetime(df["ts"], unit="ms"))
sc.calculate_rsi(); sc.calculate_macd(); sc.calculate_bollinger_bands()
sc.calculate_volume_confirmation(); sc.calculate_conviction_score()
sc.determine_signal()
```

Wrap in try/except returning `{"error": ...}` — a CEREBRO outage must degrade
to "no overlay", never block the whole ladder.

## Ladder shape that works

5 tranches: 3 time-based (immediate / week 2 / week 3) to guarantee exposure,
2 price-triggered (-15%, -28%) so weakness buys more. Weight symbols by base
score (NEAR score 75 → 60%, INJ 60 → 40%). DCA beat lump on both 12m and 24m
horizons in the measured study — always DCA.

## Reminders on CLI (no gateway)

CLI sessions have NO delivery channel — a `deliver='origin'` cron job saves
output that the user never sees. Do not promise a ping. Use a **Windows toast**
from inside the script:

```python
subprocess.run(["powershell","-NoProfile","-Command", ps], capture_output=True, timeout=25)
# ps uses [Windows.UI.Notifications.ToastNotificationManager] template 1
```

Toast on action-required only. Run the cron `--quiet` so it stays silent unless
a tranche is due or invalidation hits. Tell the user plainly that cron requires
the Hermes scheduler to be running, and give them the manual command.

## Cron on Windows — THREE traps that all fail SILENTLY

Found 2026-08-08 only by calling `cronjob(action='run')` to force an execution.
Creating a job and seeing `success: true` proves NOTHING — that just means the
job was registered. Until a real execution reports `execution_success: true`,
assume it is broken.

1. **Script path root is `AppData\Local\hermes\scripts\`, NOT `~/.hermes/scripts/`.**
   A relative `script=` resolves under the AppData profile dir. Files written to
   `~/.hermes/scripts/` give `Script not found`.
2. **No `bash` on PATH for the cron runner.** `.sh`/`.bash` entries fail with
   "bash not found on PATH... rewrite the script as Python (.py)". Write cron
   entries as `.py` and shell out with `subprocess`.
3. **`sys.executable` inside a cron script is the hermes venv python, which has
   NO numpy/pandas/yfinance.** Everything works when you test manually (the
   shell's `python3` is a different interpreter) and dies under cron with
   `ModuleNotFoundError: No module named 'numpy'`. Pin the real interpreter:

   ```python
   PYEXE = r"C:\Users\victo\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe"
   if not pathlib.Path(PYEXE).exists():
       PYEXE = sys.executable
   ```

**Verification that actually proves it:** `cronjob(action='run', job_id=...)`
and require `last_status: ok` AND `execution_success: true` in the response.

## Monthly re-screen — the ladder is a snapshot unless you refresh the universe

`dca_tape_refresh.py` refreshes LEVELS for names already in the ladder. It does
NOT find new ones. Pair it with `crypto_bottom_rescreen.py` (monthly cron) which
rebuilds the top-500 universe, re-scores, and DIFFS against the prior snapshot:

- new names entering the `<=-90%` bucket (the only bucket with a positive
  forward median — see `cerebro-crypto-scan/references/crypto_bottom_research.md`)
- names whose base score newly crossed 50
- **degraded ladder names** (score fell >10) → surfaces a LADDER REVIEW line
- names that fell out of screen

Report only the delta, not the full table — a monthly full dump gets ignored.

**Rollback guard is mandatory.** Copy the prior universe+scores to
`~/.hermes/crypto_bottom_history/rollback_*.json` BEFORE re-running, and if the
new run yields `< MIN_CANDIDATES` (5), assume a broken/rate-limited fetch,
restore the backups, toast a failure, and exit. Without this a CoinGecko 429
silently wipes a good snapshot and the diff reports "everything fell out".

Verified 2026-08-08: 478 tradable → 46 liquid → 33 candidates → 24 validated,
4 qualified (NEAR 75, INJ 60, BCH 50, DOGE 50). Note BCH/DOGE clear the numeric
bar but backtested RED/AMBER — qualifying on score is NOT a buy signal, it only
earns a place in the review queue.

## Pitfalls

- `cronjob(script=...)` REJECTS absolute paths — the script must live in
  `~/.hermes/scripts/` and be referenced by bare filename.
- Cron `deliver='local'` is correct on CLI; output is retrievable via
  `cronjob action='list'` but is NOT pushed anywhere.
- Verify the toast pipeline once with a test call before claiming reminders work.
- State file tracks `filled` tranches; `--fill SYM:N` is how the user records a
  buy. Without it the ladder re-issues the same tranche forever.
- Run the whole cron shell script manually once end-to-end before trusting it.
  Chaining two python scripts hides failures in the first one.

## Support files
- `scripts/dca_tape_refresh.py`
- `scripts/dca_ladder_check.py`
- `scripts/dca_ladder_cron.sh`
