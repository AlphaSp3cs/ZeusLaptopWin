---
name: ourotaurus-workflow-gap-closure
description: "Use to register skills, restart cron, bridge API keys."
category: finance
---

# OuroTaurus Workflow Gap Closure

Repeating maintenance procedure for the OuroTaurus trading system on Windows. The
July-10 gap analysis built 12 skills as .py engines but they were ORPHANED: no
SKILL.md, not registered in Hermes, no cron wiring, gateway down, keys unreachable.

## Trigger
- "workflow analysis", "find gaps", "skills not triggering", "cron not firing",
  "gateway not running", "close the loop", "make sure we are perfect".

## The 3 failure modes this fixes
1. **Orphaned skills** — engine .py exists in ~/.hermes/skills/<name>/ but has only
   skill.yaml + README, no SKILL.md. Hermes only loads SKILL.md. Symptom:
   `hermes skills list --source local` doesn't show them.
2. **Gateway down** — symptom: `hermes cron list` prints "Gateway is not running —
   jobs won't fire automatically." All cron jobs are dead until fixed.
3. **Keys unreachable** — engines read HERMES_TELEGRAM_BOT_TOKEN / GLASSNODE_API_KEY
   etc., but those names live in ~/.hermes/secure/.env as TELEGRAM_BOT_TOKEN / etc.,
   and are NOT in any env Hermes loads. Symptom: engine logs "Telegram not configured".

## Steps
1. **Check gateway:** `hermes gateway status`. If "No gateway process detected",
   run `hermes gateway start` (Windows: also `hermes gateway install` for autostart).
2. **Verify cron will fire:** `hermes cron list` should NOT show the gateway warning.
3. **Register skills:** for each orphan in ~/.hermes/skills/<name>/ that lacks
   SKILL.md, write a SKILL.md (YAML frontmatter: name/description/user-invocable/
   metadata.tags + a "Run it" bash block with the real CLI). Then sync into the REAL
   enabled-skills dir:
   `REAL="$APPDATA/../Local/hermes/skills"; mkdir -p "$REAL/$name"; cp SKILL.md +
   *.py + README.md + skill.yaml there; add _meta.json + skill-card.md`.
   Verify: `hermes skills list --source local | grep <name>` shows "enabled".
4. **Bridge keys:** create `_ourotaurus_secrets.py` (loads ~/.hermes/secure/.env, maps
   TELEGRAM_BOT_TOKEN->HERMES_TELEGRAM_BOT_TOKEN, GLASSNODE_API_KEY->GLASSNODE_API_KEY,
   KRAKEN_API_KEY/SECRET, BINANCE_API_KEY, GMAIL_CREDENTIALS, DISCORD_WEBHOOK_URL->
   HERMES_DISCORD_WEBHOOK_URL). Copy it into every engine subdir and add after the
   import block:
   ```
   sys.path.insert(0, os.path.dirname(__file__))
   import _ourotaurus_secrets  # noqa: F401
   ```
5. **Verify:** `python3 <engine>.py <cli>` runs and shows keys loaded (e.g. "Telegram
   notifications enabled"). Smoke-import all 12.

## Pitfalls
- `hermes skills install ./localpath` fetches the HUB version by slug, NOT your local
  engine .py — do NOT use it to register these; copy files manually into REAL dir.
- The REAL enabled-skills dir is `~/AppData/Local/hermes/skills/` (Windows), NOT
  `~/.hermes/skills/`. The latter is the source/build dir.
- `.no-bundled-skills` in AppData/Local/hermes means bundled seeding is opted out —
  local skills must be placed manually.
- Never print secrets. Only ever echo key NAMES, never values.
- Re-run this whole procedure after `hermes skills reset` or re-seeding bundled skills.

## Deliverable
Write closure report to ~/.hermes/WORKFLOW_GAP_CLOSURE_AUG2026.md (update date).
