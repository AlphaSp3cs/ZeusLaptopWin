---
name: signal-provenance-audit
description: "Use before trusting any sentinel or signal source."
user-invocable: true
metadata:
  version: "1.0"
  tags: ["trading", "integrity", "sentinels", "confluence", "data-quality"]
---

# Signal Provenance Audit

Prove a data source is live before trusting it. Blocks silently-dead scanners from
counting as confluence.

## Why this exists

On 2026-08-08 an audit of the 10-skill "sentinel fleet" found **8 of 10 were DEAD**:
they executed, exited 0, printed nothing, and had **never written a single row** to
their databases. Every one was documented as working; several SKILL.md files claimed
"verified working".

The danger is not that they were broken. It is that **a dead sentinel is silent, and
silence reads as "no signal found"**. Stack eight silent sentinels behind a trade and
you get a setup that looks unopposed by any risk check, when in truth nothing checked it.

Two concrete bugs found, both the same species — *fabricating a plausible value
instead of admitting missing data*:

1. `crypto_sentiment_aggregator.py` checked `data['status']` on an API
   (alternative.me F&G) that has **no `status` key**. It raised `KeyError` on every
   run since creation, was swallowed by `except Exception`, and returned a hardcoded
   `0.5` "neutral". A permanently-broken feed reporting as calm markets.
2. The same file computed a weighted composite where 3 of 4 inputs were `pass` stubs
   returning `None`. Once the crash was fixed, the composite was built from 20% of
   its intended weight while presenting as a full-confidence number.

## The rule

**A data source is guilty until proven live.** Never infer health from exit code 0,
absence of errors, or documentation. Prove it with persisted rows.

## Run the audit

```bash
python3 ~/sentinel_audit.py            # audit persisted state only (fast)
python3 ~/sentinel_audit.py --run      # execute each sentinel first, then audit
python3 ~/sentinel_audit.py --json     # machine-readable, for the trade gate
```

Statuses:
- `LIVE`    — target tables have rows, DB written within 26h. Usable.
- `STALE`   — has rows but DB untouched >26h. Investigate before use.
- `DEAD`    — target tables all empty. **Scaffolding, not a data source.**
- `MISSING` — directory or entrypoint gone.

Exit code is 0 only when every sentinel is LIVE, so it can gate a pipeline.

## Mandatory usage in any scan or setup

1. Run `sentinel_audit.py` **before** quoting any sentinel-derived input.
2. **Exclude DEAD/MISSING sources from the confluence count entirely.** Do not count
   them as neutral, do not count them as passing. Three live confirmations out of ten
   sources is "3 of 3 available", never "3 of 10" and never "7 with no objection".
3. State coverage explicitly: *"sentiment read is 20% coverage — F&G only,
   news/CT/Reddit are stubs. Don't size off it."*
4. If a required risk check (e.g. `trading-risk-dashboard`) is DEAD, the setup is
   **unvalidated**. Say so rather than presenting it as clean.

## Fix pattern for a dead/lying source

- **Never return a plausible default on failure.** Return `None`. A fake `0.5`
  neutral is indistinguishable from a real neutral reading and poisons everything
  downstream. `None` is loud; `0.5` is a lie.
- **Aggregate over available inputs only**, renormalising by weight actually present,
  and report coverage:
  ```python
  available = {k: v for k, v in parts.items() if v is not None}
  total_w = sum(weights[k] for k in available)
  if total_w == 0:
      return None                      # refuse to score
  composite = sum(available[k] * weights[k] for k in available) / total_w
  coverage = round(total_w * 100)      # log this, always
  ```
- **Warn below a coverage floor** (60% used here) so a thin reading can never
  masquerade as a full one.
- **Verify the API contract against a live payload** before trusting field names:
  ```bash
  curl -s "https://api.alternative.me/fng/?limit=1"
  ```
  The `data['status']` bug survived indefinitely because nobody diffed the parsing
  code against one real response.
- **Never let `except Exception` swallow a parse error into a default.** Log it and
  propagate `None`.

## Pitfalls

- A silent script with exit 0 is the *most* dangerous state — it looks healthiest.
  The audit flags `SILENT: produced no stdout/stderr at all` for exactly this.
- A non-empty `.db` file ≠ working. Tables are created at init; **rows** are the proof.
- `crypto-price-alerts` is the counter-example: it genuinely works (12 real alerts
  fired, ETH $1,916 vs $1,856 target) but crashes *after* the alert on an unconfigured
  Telegram push. Partial function — triage as STALE, not DEAD.
- sqlite datetime-adapter DeprecationWarnings are noise here, not failures.

## Extending the fleet

Add sources to the `FLEET` dict in `~/sentinel_audit.py`:
`"skill-dir": (["cli", "args"], ["table_that_proves_it_worked", ...])`.
Pick tables that only gain rows when the source *actually fetched something* — never
a config or schema table.
