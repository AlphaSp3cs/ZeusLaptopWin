# FREYA GAP SCOUT — WORKFLOW (missing-piece coverage)

Owner: Freya (Pack Research & Intelligence / scout)
Trigger: user asks Freya to "hunt competitor info / cover gaps / build a scout
list," or any time the main scan engine reports a methodology it lacks.

## Steps
1. COMPETITIVE INTEL (Freya's job)
   - Identify which methodologies the Pack covers vs. what serious competitors /
     canonical TA literature uses. Grep the real code first (no guessing):
       grep -rilE "wyckoff|order block|FVG|volume profile|POC|VSA|HVF|market profile|footprint" --include=*.py --include=*.md <skills + scan code>
   - Classify each as COVERED / PARTIAL / ABSENT.

2. BUILD A REAL DETECTOR (never fabricate)
   - Read live data (bars.db) — confirm schema + row counts before writing math.
   - Each detector is pure OHLCV signal math. Conservative thresholds.
   - Prove it returns data: run it, check "Scanned N, signals M" is plausible.

3. PACKAGE
   - Put scanner in skill `scripts/`, SKILL.md with trigger + run command + schema.
   - Install to the canonical skills root (loaded every session):
     C:/Users/victo/AppData/Local/hermes/skills/finance/freya-gap-scout/
   - Also drop a copy under the Freya profile so the scout owns it:
     D:/Hermes/profiles/freya/skills/research/freya-gap-scout/

4. SURFACE THE SCOUT LIST (not the warehouse)
   - Print only symbols that look like live setups (method + bias + levels).
   - Copy JSON to Desktop/scandata/<run> per the standing scandata rule.

5. RECHECK (standing rule)
   - Next scan, compare against the snapshot and report DELTAS. A gap hit that
     persists + confirms on the main scan gate becomes a trade candidate.

## Edge cases
- bars.db missing/stale → detectors return None, symbol skipped (correct).
- Over-firing (signals > ~30% of scanned) → tighten thresholds in the detector.
- MARKET_PROFILE alone = context, not a trade. Require Wyckoff/VSA/HVF or a
  main-scan setup before routing to enhanced_trade_gate.py.
