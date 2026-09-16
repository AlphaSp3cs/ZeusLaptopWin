# Case study: the "D:\Hermes cleanup" that was live agent scratch

## Request
User: "make sure you are completely aware of all files you can use or stop using and delete inside the D:\Hermes".

## What the first snapshot showed (looked harmless)
```
D:\Hermes\workflow\persisttest\a.txt         (6 bytes, "hello")
```
One tiny text file. Looked like junk.

## What the re-scans revealed (the dir was LIVE)
- `D:\Hermes\workflow\data\probe.db` appeared at 11 MB, then shrank to 0 bytes.
- `a.txt` went MISSING between two listing calls.
- `D:\Hermes\workflow\scripts\` (empty dir) appeared during the scan.
- `probe.db` was not exclusively locked, but the continuous create/shrink/delete proved
  the runtime itself owned the lifecycle.

## Reference check
Grep of `AppData\Local\hermes\logs`. The ONLY hits for "D:\Hermes" were echoes of the
agent's OWN timed-out grep command. => The agent's config/skills do NOT depend on this path.

## Verdict
Live agent-owned persistence/scratch area (names: persisttest, probe, workflow, scripts).
Self-managed; 0 real user data; deleting mid-session could break a running write or just
get respawned. Decision: do NOT delete. Offered options A (leave) / B (delete anyway) /
C (contents only) and waited for explicit user choice.

## Lesson baked into the skill
A single `find` snapshot lies for live dirs. Re-scan, lock-test, and grep a SPECIFIC
log dir (never the whole home tree — times out). Mutation between scans is the tell.
