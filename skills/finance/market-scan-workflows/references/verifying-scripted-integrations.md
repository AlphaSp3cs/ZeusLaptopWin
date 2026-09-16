# Verifying a scripted integration actually works

Class of failure: you wire an existing interactive tool into an automated
pipeline, the output *looks* right, and a critical branch is silently dead.
Two real instances on 2026-08-08, both in `scan.py`, both invisible on screen.

## Never verify by eyeballing output — assert the parsed value

The danger gauge printed:

    [REGIME] Gauge:  82.5/100  ... EXTREME DANGER

...and the `>=75` warning never fired. The line rendered perfectly; the parse
returned `None`. Cause: ANSI colour codes inside the numeric token
(`'Gauge: \x1b[91m\x1b[1m\x1b[5m 82.5/100\x1b[0m'`), so
`float(line.split("Gauge:")[1].split("/")[0])` raised, a bare `except: pass`
swallowed it, and `score` stayed `None`.

Two compounding sins: colour codes in machine-read output, and a bare except
hiding the failure. The report text stayed correct because it echoed the raw
line — only the *decision* was dead.

The check that caught it:

```python
import scan
s, line = scan.danger_gauge()
assert s is not None, "score failed to parse"
print("EXTREME fires:", s >= 75)
```

**Rule: after wiring any parsed value into a decision branch, assert the parsed
value in isolation.** Reading the rendered output proves nothing — the string
can be perfect while the number is `None`. Prefer a machine-readable artifact
(`latest_gauge.json`) over scraping styled stdout when one exists.

## Interactive monitors hang subprocess callers

`danger_zone_gauge.py` `main()` was `while True: ... time.sleep(60)`. It seemed
fine interactively only because every caller wrapped it in `timeout 60`. Called
from `subprocess.run` with no wrapper it would block until the subprocess
timeout on EVERY scan.

Before wiring any existing script into a pipeline, grep its entry point:

```
grep -nE "while True|time.sleep|input\(|argparse|--once|def main" <script>
```

If it loops, add a `--once` flag (compute → print → write artifact → return)
rather than relying on an external `timeout`. Fixed version runs in ~2s.

**Tell: a script that "works" only when someone wrapped it in `timeout` is not
working — the wrapper is hiding a loop.**

## A refusal must propagate to the caller's exit code

Third instance, same session. `scan.py` printed `[gate] REFUSED/FAIL` when the
gate correctly rejected a stale scan — but never folded that flag into the
run's result:

```python
ok_g, tail_g = gate(scan_json, equity, allow_stale)
print(f"[gate] {'OK' if ok_g else 'REFUSED/FAIL'}\n{tail_g}")
# BUG: ok_g never reaches ok_all -> exit 0 on a refusal
```

So a run that authorised NOTHING exited 0, and a cron caller would log it as a
success. Fix is one line (`ok_all &= ok_g`), but the class is general:

**Rule: every guard that can REFUSE must be able to fail the process.** Any
safety check whose only effect is a printed string is decorative. After adding
a refusal path, test it by forcing the refusal and asserting the returned flag
/ exit code — never by reading the message.

Forcing the refusal is usually cheap — mutate the input the guard reads:

```python
d['scan_timestamp'] = (now - timedelta(hours=6)).isoformat()   # age past limit
# then: assert gate(...)[0] is False
```

Back up and restore the real file around such a test, and re-read the restored
value to confirm the restore landed.

## Check your PROBE before blaming the system

Two "failures" in this sweep were bugs in the diagnostic, not the code:

- `datetime.fromisoformat(d['generated'])` → `TypeError` because the real key
  was `refreshed`.
- `v['warn']` → `KeyError` because the real key was `warn_level`.

Both briefly looked like broken state files. The correct reflex on a probe
error is to dump the actual keys first:

```python
print(sorted(d['symbols']['NEAR'].keys()))
print(list(d.keys()))
```

...then confirm the CONSUMER reads the same names (`grep -n "cfg\[" consumer.py`).
Matching producer keys to consumer keys is the real test; a hand-written probe
is a third implementation that can be wrong on its own.

**Never report a failure sourced only from your own ad-hoc probe.** Re-run it
correctly first. Reporting a phantom bug costs trust exactly as much as missing
a real one.

## Invariant assertions beat spot-checks on money paths

For anything that can move capital, assert the ORDERING invariants rather than
eyeballing levels. For a DCA ladder:

```
T5 > invalidation      # no tranche buys below the stop-out
T4 > T5                # tranches descend
warn > invalidation    # stress level sits above the halt
```

This catches a whole class of recompute bugs (a refreshed level drifting below
the halt price) that reading a table of numbers will not.

## Archiving duplicate scripts safely

Before moving dead scripts, prove nothing imports them — don't trust filenames:

```python
import ast, pathlib
arch = {p.stem for p in pathlib.Path(ARCHIVE).glob('*.py')}
for f in pathlib.Path.home().glob('*.py'):
    t = ast.parse(f.read_text(encoding='utf-8', errors='ignore'))
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            for x in n.names:
                if x.name.split('.')[0] in arch: print(f.name, x.name)
        elif isinstance(n, ast.ImportFrom) and n.module:
            if n.module.split('.')[0] in arch: print(f.name, n.module)
```

Used to archive 22 duplicate scanners (62 → 29 entrypoints) with zero breakage.

## Background-notification bugs are free evidence — read them

The gauge loop was exposed by a `notify_on_complete` message arriving AFTER the
router had been declared working. The notification contained
`"Starting live monitor (60s refresh) — Press Ctrl+C to stop"`, which
contradicted the earlier claim. Late async output is a real verification
channel; when it contradicts something already reported as done, re-open it and
say so plainly rather than letting the earlier claim stand.
