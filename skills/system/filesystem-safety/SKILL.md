---
name: filesystem-safety
description: Use before deleting dirs/files; run a liveness gate first.
---

# filesystem-safety

## Trigger
The user asks you to delete / remove / purge / clean up / wipe / empty a directory or file set — OR you are about to `rm -rf` / `del` anything non-trivial. Applies double when the path looks like app data: `D:\Hermes`, `~/.hermes`, `AppData\Local\...`, `workflow/`, `data/`, `persisttest/`, `probe.db`, `*.db`, `scripts/`, `.cache`, `.tmp`.

**Bottom line:** never delete on a single snapshot. A directory being actively written by a running process looks harmless (0 bytes, empty) but is live scratch space. Deleting it mid-session can break a persistence write or just get recreated. Verify liveness FIRST.

## The safety gate (run before any destructive action)
1. **Full inventory.** `find <path> -type f` plus `ls -la` of each dir. Record size + mtime of every file.
2. **RE-SCAN before deleting.** Run the inventory again. If files appear, disappear, or change size between two scans, the dir is LIVE. This single re-scan is the highest-value step — a one-shot `find` can lie because the tree mutates between your listing calls.
3. **Exclusive-lock test (per file).** Try `os.open(path, os.O_RDWR)` in Python. `PermissionError` => a process holds it open; `FileNotFoundError` => it vanished since your last scan (also a liveness tell); clean open => not exclusively locked. NOTE: an unlocked file in a self-mutating dir is NOT proof of safety.
4. **Reference check (does anything depend on it?).** Grep config/logs/scripts for the exact path. Target SPECIFIC dirs (e.g. `AppData\Local\hermes\logs`) — do NOT grep the entire home/`$HOME`; a full-tree `grep -rIl` routinely times out at 60s and wastes a turn. If the only hits are your own command echoes in a log, the agent's config does NOT depend on the path.
5. **Classify.** User junk (static, unreferenced, stable mtimes) vs agent-owned scratch (live mutation, names like `persisttest`/`probe`/`data`/`scripts`, actively created/cleaned by the runtime).
6. **Offer options, then confirm.** Present: A) leave it, B) delete everything, C) contents-only (keep the folder). Proceed only on explicit user say-so, ideally at a quiet moment, and re-verify it's not mid-write right before the delete.

## Pitfalls
- A single `find` snapshot can lie — re-scan; live dirs mutate between calls.
- Empty files / empty dirs mid-scan are a STRONG liveness signal, not "already gone."
- Don't rely on the lock test alone. A self-mutating workspace can be unlocked between writes yet still be owned by a running process.
- Even if no config references the path, if it's actively mutating, deletion may break a running persistence write OR the runtime will just respawn it.
- Narrow grep scope (specific log/config dirs), never the whole home tree — full-tree grep times out and adds nothing.
- Don't delete a path you can't explain. If you can't state what owns it, that's not "safe to remove," that's "unknown" — leave it.

## Support files
- `scripts/safe_delete_probe.py` — deterministic pre-deletion probe: inventories a path, re-scans for mutation, lock-tests each file, greps a references dir for the path, prints a verdict. Run it before any `rm -rf`.
- `references/live-scratch-case-study.md` — condensed real session: a `D:\Hermes` "cleanup" request that turned out to be live agent scratch (11 MB `probe.db` → 0 bytes, `a.txt` appearing/disappearing, empty `scripts/` spawning). Shows the gate in action.
