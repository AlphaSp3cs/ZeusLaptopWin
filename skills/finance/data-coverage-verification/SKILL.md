---
name: data-coverage-verification
description: Use before trusting any market data store or scan universe.
---

# Data Coverage Verification

Companion to `signal-provenance-audit`. That skill proves a data *source* is
live. This one proves the *universe* it was pointed at contains what you hold,
and that what it wrote actually survived.

Three distinct lies, all with the same signature — **clean exit, no error, no
data** — and all indistinguishable from "nothing is happening in that asset":

1. **Dead source** — covered by `signal-provenance-audit`.
2. **Universe gap** — the asset was never requested.
3. **Discarded write** — the data was fetched, committed, and then lost.

## 1. Universe gaps

Found 2026-08-08: three of six active DCA ladder coins (IOTA, JTO, ENA) were
absent from the shared `crypto_universe.py` (43 symbols, none of them these).
All three were live on the provider the whole time — never registered. Anything
deriving its symbol list from that module was silently blind on half the book.

Rules:

- **Liveness is not coverage.** Proving the fetcher works says nothing about
  whether it was aimed at your holdings. Audit both.
- **Declare holding universes explicitly; never inherit them.** A position,
  ladder, or watchlist universe gets a hardcoded list in the consuming code,
  not a reference to a shared module that can drift.
- **Assert holdings resolve to rows.** Every symbol in a state/position file
  must return data. `6/6` is the only acceptable answer; `3/6` with a clean
  exit is exactly the failure this catches.
- **Add the symbol in the same change as the holding.** Never assume a shared
  universe module already knows a name you just started tracking.

Implementation that works — explicit list, registered as its own sector AND
unioned into the parent universe so coverage is asserted twice:

```python
LADDER = ["ALGO-USD", "IOTA-USD", "JTO-USD", "ENA-USD", "NEAR-USD", "INJ-USD"]

def load_crypto():
    import crypto_universe as cu
    return sorted(set(cu.CRYPTO_YF_SYMBOLS) | set(LADDER))
```

## 2. Storage that lies about persistence

On 2026-08-08 a volume accepted a fully committed 232MB SQLite database, then
discarded it. A follow-on job reported `OK 105 EMPTY 0 ERROR 0` and its output
was gone seconds later. Directory listings flickered between present and
"No such file or directory" across consecutive commands while free space
reported normally throughout.

**A clean commit is not proof of persistence.** Where durability is suspect:

- `PRAGMA synchronous=FULL`.
- After every write batch, **reopen the store on a fresh handle and re-count
  rows**, verified against a floor of what should already exist:

```python
def verify_persisted(expect_min_rows=1):
    if not DB.exists():
        return False, "DB FILE MISSING after commit"
    c2 = sqlite3.connect(DB, timeout=30)          # fresh handle, not the writer
    n = c2.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    c2.close()
    if n < expect_min_rows:
        return False, f"only {n:,} rows on disk, expected >= {expect_min_rows:,}"
    return True, f"{n:,} rows verified on disk"
```

- On failure, declare the store **EMPTY** and refuse to scan against it. A
  half-persisted store is worse than none: it reads as thin data rather than
  missing data.
- **Keep code masters on a different volume from the data** and mirror on every
  run, so a wipe destroys only re-downloadable data, never source.

## 3. Reporting coverage honestly

- Print a per-bucket coverage board (`covered/total`, newest bar, staleness)
  before any scan consumes the store.
- A symbol that returned nothing is **UNCOVERED**, logged with its status, and
  named in output. Its absence from results is NOT a "no signal" reading.
- Weekend/holiday staleness is expected for anything that closed Friday — carry
  an explicit `--max-age-days` tolerance rather than flagging normal closures.
- Retire delisted names into a `retired` table and delete them from the active
  universe, so re-init can't resurrect them and they stop polluting the failure
  list. Distinguish "delisted, correctly excluded" from "should be here and
  isn't" — only the second is a coverage bug.

## Verification checklist before any scan

1. Source LIVE? → `signal-provenance-audit`
2. Universe contains every held symbol? → assert state file ⊆ store
3. Last write persisted? → fresh-handle re-count
4. Coverage board printed, uncovered names named out loud?
5. Only then read the data.

Failing 2, 3, or 4 produces output that looks like a calm market. That is the
whole danger.

## Support files

- `references/storage-durability-incident-2026-08-08.md` — full transcript of
  the volume that discarded a committed 232MB database, the confusing symptoms
  (success reported at every layer, small writes surviving, self-healing), the
  diagnostics to hand the user, and two `yfinance` unit-inconsistency bugs
  (`pctHeld` fraction-vs-percent, `dividendYield` percent-for-funds) found the
  same session.
- `references/verifying-claimed-prior-work.md` — when the user describes work as
  already done (often from another machine or profile), verify the artifacts
  exist here before extending them, and say plainly when they don't.

