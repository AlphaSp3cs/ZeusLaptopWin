# Verifying claimed prior work before building on it

A recurring class: the user describes work as already done — files written,
skills created, frameworks integrated — and asks you to extend it. **Verify the
claim before extending it.** The work may have happened on a different machine,
a different profile, or in a session whose changes never landed here.

## The case that established this — 2026-08-08

User opened with a detailed, entirely credible summary: a valuation methodology
integrated, gaps closed, a tracker updated at
`C:\Users\bravo-usr1\Desktop\clarity_act_crypto_dca_tracker.md`, and a new
reusable skill `valuation-scorecard` created.

None of it existed on this machine:

- The path was under `C:\Users\bravo-usr1\` — **a different user profile**.
  This host is `C:\Users\victo\`.
- `skills_list` showed no `valuation-scorecard`.
- The local tracker was 130 lines with no NTNX entry and no Section 6.

Had I accepted the framing and "extended" it, I would have written a patch
against a nonexistent baseline and reported success on a foundation that was
not there.

## Rule

**Check before you extend.** Cheap, parallelisable, and catches this instantly:

- `skills_list` — does the named skill exist here?
- `search_files` / `read_file` on the cited path — does the file exist, and does
  it contain the claimed sections?
- Compare the cited path prefix against the actual home directory.

## Reporting posture

Say it plainly in the first line, then do the work for real:

> "That work isn't present on this machine — the path you cited is under
> `C:\Users\bravo-usr1\`, a different profile. Here it's `C:\Users\victo\`.
> There was no `valuation-scorecard` skill and no Section 6 in the tracker. So
> I built it for real rather than pretend it was already integrated."

Do NOT:
- silently rebuild and let the user believe their earlier work was found;
- assume the user is mistaken about having done it (they probably did — just
  elsewhere);
- treat the description as a spec you can only partially satisfy without saying
  which parts were missing.

The user's description is still valuable: it is an accurate specification of
what they want. Build to it. Just do not report it as "already there".

## Cross-machine signals worth checking

- Path prefixes naming a different user or host.
- References to skills, scripts, or DBs that `skills_list` / a file check cannot
  find locally.
- Claims of "verified working" for something with no artifact on disk — the same
  species of problem `signal-provenance-audit` exists to catch, applied to work
  product instead of data sources.

## Related

When the claimed artifact is a *data source* rather than a file, use
`signal-provenance-audit`. When it is a *universe or store*, see this skill's
SKILL.md. This reference covers claimed **code and document** artifacts.
