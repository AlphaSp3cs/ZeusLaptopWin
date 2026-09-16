# Stale `_latest.json` artifact bug — diagnosis and reusable guard

## Symptom

Every command in the pipeline exits 0. The report looks complete and plausible.
The numbers are hours old.

## Diagnosis (2026-08-04/05)

`enhanced_trade_gate.py` had **no `main()`**. Its `__main__` block was a test
harness containing one hardcoded Gold trade:

```python
if __name__ == "__main__":
    test_trade = {"symbol": "GC", "name": "Gold", "price": 4115.40, ...}
    setup = calculate_trade_setup(test_trade, "swing")
    print(f"Symbol: {setup.symbol}")
    ...
```

Running `python3 enhanced_trade_gate.py` printed:

```
Symbol: GC
Side: LONG
Validation: GO -
```

...and wrote **nothing**. The `enhanced_setups_*_latest.json` files on disk were
13 hours stale (07:27 vs a 20:16 scan), so the whole report was built on the
morning's data.

The real entry point was `run_universal_workflow.py --gate-only`, which loads
the scan and calls `process_all_setups()`.

## How it was caught

Not by the exit code — by a data-consistency check. The gate's long list
contained `TIP`, `^IXIC`, `XLC` which were **absent from the scan's**
`qualified_longs`, and was missing `UNG` which was the scan's top-ranked long.
Symbol-set mismatch between adjacent pipeline stages is the tell.

```bash
ls -la --time-style=full-iso *_latest.json
# enhanced_setups_day_latest.json    2026-08-04 07:27:18
# enhanced_setups_swing_latest.json  2026-08-04 07:27:18
# universal_scan_results_latest.json 2026-08-04 20:16:39   <-- newer than its own outputs
```

## Reproduction (confirms the diagnosis)

Running the gate against the old scan reproduces the exact stale GO list that
was wrongly reported — `XLU, TLT, XLF, SPY, ETH, 000001.SS`:

```bash
python3 enhanced_trade_gate.py \
  --scan-file universal_scan_results_20260804_072718.json \
  --dry-run --allow-stale
```

## The fix — reusable guard pattern

Apply this shape to any phase script that reads an upstream artifact.

### 1. Parse the input's own timestamp, not the file mtime

File mtime lies on Windows because symlink creation fails (`WinError 1314`) and
the workflow falls back to copying. The scan's self-reported `scan_timestamp`
is authoritative.

```python
STALE_AFTER_MINUTES = 90

def _staleness_minutes(scan_path, scan_data):
    import datetime as _dt
    ts = scan_data.get("scan_timestamp")
    if not ts:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    now = _dt.datetime.now(_dt.timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return (now - parsed).total_seconds() / 60.0
```

### 2. Refuse by default, allow explicit override

```python
if age is not None and age > STALE_AFTER_MINUTES and not allow_stale:
    print(f"REFUSING TO RUN: scan is {age:.0f} minutes old (limit {STALE_AFTER_MINUTES}).")
    print("Re-run the scanner, or pass --allow-stale to override.")
    return None
```

The override matters: deliberate backtesting stays possible, and using it leaves
a visible marker in the transcript.

### 3. Stamp provenance into every output

This is the highest-value piece. It makes staleness readable from the artifact
itself instead of requiring an mtime forensics pass.

```python
output = {
    "profile": profile_type,
    "scan_timestamp": stamp,          # inherited from the input
    "scan_source": scan_file,
    "summary": ...,
}
```

Downstream consumers then check:

```python
d = json.load(open('enhanced_setups_swing_latest.json'))
print(d['scan_timestamp'], d['scan_source'])
```

### 4. Meaningful exit codes

`raise SystemExit(0 if res else 1)` — exit 0 only on a real validated run so the
script cannot pass silently inside a chain.

## Verified behaviours after the fix

| Case | Result |
|------|--------|
| Fresh scan (0 min old) | runs, 2 GO long / 10 GO short, exit 0 |
| Stale scan (783 min) | refuses, prints age, exit 1 |
| Stale + `--allow-stale` | runs, reproduces the old GO list |
| Missing scan file | clear error, exit 1 |
| `run_universal_workflow.py --gate-only` | unchanged, still works |

## Generalisable rule

Before trusting `python3 <script>.py`:

```bash
grep -n "def main\|__main__" <script>.py
```

Read the block. If it constructs literal sample data, it is a demo — find the
orchestrator that imports its functions. And regardless of entry point, verify
that downstream artifacts are newer than their upstream inputs before reporting
anything derived from them.
