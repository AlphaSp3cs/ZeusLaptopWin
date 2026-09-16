---
name: skill-library-maintenance
description: Use when auditing or reorganizing a skill library.
category: meta
---

# Skill Library Maintenance

Auditing a skill library for gaps, splitting megaskills, fixing broken
references, and disambiguating routing. Applies whenever the user asks to
"review the workflow", "find gaps", "reorganize the skills", or after any
session that revealed a skill was wrong.

## Run the audit before forming any opinion

`scripts/audit_skill_library.py` does the whole measurement pass:
per-skill size, description, dangling references, orphaned files, and
TRANSITIVE reachability. Run it first, and re-run it after every edit.

`scripts/prove_liveness.py` is the second half of the pass, and the one
people skip: it measures whether code-bearing skills actually WORK, by stub
density and persisted row counts rather than by what the prose claims.
Run it with `--run` when you can afford the execution time. A library can be
100% reachable with zero dangling refs and still be mostly hollow.

Never eyeball a library and start editing. The three highest-value defects
(phantom refs, orphaned files, colliding descriptions) are all invisible to
reading and obvious to measurement. Dead scaffolding is invisible to BOTH
reading and a reference audit — only execution plus row counts finds it.

## The defect classes, in priority order

### 1. Operational silence — the pipeline that never runs
Highest severity, and easy to miss because nothing errors. A cron job can
list as `[active]` while never firing (gateway down, deliver:local, no
delivery channel). Any scheduled job whose output nobody receives is a job
you cannot assume ran.

RULE: verify scheduled work by the EXISTENCE OF ITS DATED ARTIFACT, never by
the scheduler reporting the job as active. Encode that verification into the
skill that owns the job, not just into memory.

#### 1b. Dead scaffolding — the SKILL whose code never worked

The same silence, one level down. A skill ships a script, the script runs,
exits 0, prints nothing, and has **never written a row**. The SKILL.md
describes it as a working data source. Nothing in a documentation-level audit
catches this, because the prose is fine — it's the code that's hollow.

Measured instance (2026-08-08): a 10-skill "sentinel fleet" audited at
**8/10 DEAD**. Several SKILL.md files carried a "verified working" line.

Why it outranks ordinary bugs: **a dead source is silent, and silence reads as
"no signal found."** Stack eight silent checks behind a decision and it looks
unopposed when in truth nothing checked. Absence of objection is not
confirmation.

RULE: **a data source is guilty until proven live.** Never infer health from
exit code 0, absence of errors, or the SKILL.md's own claim. Prove it with
persisted rows — schema/table creation happens at init, so a non-empty `.db`
proves nothing. Rows are the proof.

Detection heuristics that actually work:
- `grep -c 'TODO\|^    pass'` across the skill's scripts — stub density.
- Row counts per table: `select count(*)` over every table in every bundled
  `.db`. All-zero on the tables that only fill when a real fetch succeeded
  means scaffolding.
- Flag `SILENT: produced no stdout/stderr at all` explicitly. Exit 0 with no
  output is the *most* dangerous state because it looks healthiest.

Triage into LIVE / STALE / DEAD / MISSING, not a boolean. Partial function is
common and must not be scored as dead: one skill genuinely fired 12 real
alerts, then crashed on an unconfigured delivery push — working engine,
broken last mile. That's STALE, and the fix is delivery, not a rewrite.

When you find dead scaffolding, **stamp the SKILL.md with a status banner
right under the H1** rather than only fixing code or only telling the user.
The false "verified working" claim is what manufactured the confidence:

    > **STATUS: DEAD (audited YYYY-MM-DD).** Runs, exits 0, has never written
    > a row to `tbl_a, tbl_b`. Scaffolding, not a data source.
    > **Its silence is NOT 'no signal' — it is 'no data'.** Exclude from any
    > confluence count until the audit reports it LIVE.

Then wire the audit as a step INTO the pipeline that consumes those sources,
so the check cannot be forgotten next session. A finding that lives only in
the reply decays; a finding that prints on every run does not.

See `signal-provenance-audit` for the trading-domain instance, the
never-return-a-plausible-default fix pattern, and a runnable auditor.

### 2. Phantom references — skills pointing at files that don't exist
The worst class, because the skill reads as authoritative and sends a future
agent hunting for something that was never written. Distinguish two cases:
- The file exists in the user's workspace but wasn't vendored into the skill
  -> copy it into `scripts/` and the reference resolves.
- The file never existed anywhere -> the skill documented an aspiration.
  Replace the entry with an explicit "no bundled script — compose it from
  X plus the recipe in Y" note. Do NOT quietly delete the line; the reader
  needs to know the capability is unbundled, not that it vanished.

### 3. Colliding descriptions — routing is a coin flip
Two skills whose descriptions match the same trigger mean the router picks
arbitrarily. Symptom: descriptions that are near-paraphrases
("Use when asked to run a named market scan" vs "Use when running any named
market scan pipeline").

CRITICAL DIAGNOSTIC — overlapping descriptions do NOT imply overlapping
content. Measure before you merge:

```python
import difflib
# split both SKILL.md files into H2/H3 sections, then for each section in A
# find its best body-similarity match in B
ratio = difflib.SequenceMatcher(None, body_a, body_b).ratio()
```

If no section pair exceeds ~0.45, the content is COMPLEMENTARY and merging
would just build a bigger megaskill. The fix is re-describing, not merging.
Only merge when bodies genuinely duplicate.

When re-describing, split by PHASE of the task, which is the distinction the
router can actually act on:
  - "Use when STARTING <task>: <choices to make>. Router."
  - "Use when <task> is RUNNING/failing: <diagnostics>. Deep reference."

Keep the trigger inside the first 57 characters — the system-prompt skill
index truncates there. New skills are hard-rejected above 60 chars.

### 4. Megaskills — bulk that is always loaded but rarely needed
Profile section sizes before cutting (the audit script does this). Look for
sections that are pure LOOKUP material: pitfall catalogs, annotated file
indexes, error tables. You consult these on failure; you never need them
resident.

Extract them VERBATIM to `references/`, then leave behind:
  - the 3-5 highest-frequency entries inline, and
  - a one-line pointer to the full catalog.

Nothing is deleted; everything stays one hop away. A 30% size cut with zero
content loss is a typical, achievable result.

### 5. Orphaned support files — on disk, referenced by nobody
An unreferenced file is an invisible file. Either wire it into the SKILL.md
(or into an extracted index that the SKILL.md points at), or delete it.
Orphans are also a good home for newly-discovered operational warnings.

## Reachability is TRANSITIVE

After extracting content into `references/`, a naive "is this file named in
SKILL.md" check reports false orphans — the file is now named in the
extracted index, one hop out. Walk the graph:

    SKILL.md -> references/*.md -> further refs

The audit script does this. Target is 100% reachable, 0 dangling.

## Pitfalls

- **Regex-matching a filename in prose creates a false dangling report.**
  After you replace a phantom `scripts/foo.py` link with prose explaining
  that `foo.py` does not exist, a loose regex still matches the word. Match
  only LINKED refs (inside backticks or markdown links) when checking for
  dangling targets.
- **Patch tools fail on files containing literal `\n` escape sequences.**
  Some SKILL.md files carry escaped newlines inside bullet text. The `patch`
  tool's fuzzy matcher will not find your `old_string`. Fall back to a small
  Python read/replace/write with an `assert count == 1` guard.
- **Extract-then-patch ordering.** If you fix a defect in SKILL.md and THEN
  extract that section to a reference, the fix travels with it — don't
  re-apply it and don't be surprised when the "stale" copy is already
  correct. Verify before assuming a second fix is needed.
- **Do not delete the user's workspace scripts.** A home dir with 180
  scripts and heavy `_v2`/`_fixed`/date-stamped duplication is a real
  hazard (wrong-script risk), but archiving is destructive to a working
  set. Report it with a recommendation and let the user decide.
- **Protected skills.** User-owned / pinned / bundled skills cannot be
  patched. When one of those is the skill that is wrong, say so plainly and
  recommend `hermes curator adopt <name>` rather than attempting the write.

## Curating the memory store

The memory tool checks its char limit against the FINAL state of a batch, so
one call can free space and add entries atomically. But note:

**Replacing an entry with text of similar length frees nothing.** If a batch
is rejected for overflow, reshuffling wording will fail again — and again.
Actually SHORTEN: drop parenthetical detail, redundant paths, and dated
specifics. Trimming 4-5 verbose entries in a single batch alongside the new
one is what lands it.

Observed failure mode, worth pre-empting: three consecutive rejections at
2,267 -> 2,406 -> 2,227 against a 2,200 limit, because each retry only
rephrased. The rejection message reports exact projected chars — **do the
arithmetic before resubmitting.** Budget = limit - len(new entry), then cut
at least that many chars from existing entries in the SAME batch. Landing it
took shortening four unrelated entries at once, not editing the one that
seemed most related to the new fact.

Cheapest reliable cuts, in order: dated measurement detail already captured
in a skill, duplicated file paths, parentheticals, and "(standing)" style
qualifiers. Never cut a user preference or a safety constraint to make room.

Memory holds who the user is and current operational state. How to do a
class of task belongs in a skill.

## Deliverable shape

Write the audit to a dated file (`WORKFLOW_ANALYSIS_YYYYMMDD.md`) with:
  - numbered gaps G1..Gn, each with severity, evidence, and fix status
  - an explicit "NOT FIXED — needs your decision" section
  - a summary of changes applied
  - verification output proving refs still resolve
  - a closing "THE ONE THING TO DO NEXT"

Lead the spoken reply with the single highest-severity operational finding,
not with the tidying. Hygiene wins are not the headline when something is
silently not running.
