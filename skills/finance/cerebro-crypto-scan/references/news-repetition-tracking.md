# Crypto news repetition tracking

Class of request: "watch crypto news constantly, tell me if something repeats /
if a story is escalating." Built 2026-08-08 after the Coldcard exploit ran
$88.6M -> $89M -> $116M -> $130M over three days while each individual headline
read like old news. The signal was the ESCALATION, not any single article.

## Why theme-diffing beats sentiment scoring

blogwatcher already gives per-symbol sentiment. What it does NOT give is
"this same story got bigger since yesterday". Track themes across runs and diff:

- **NEW** — a theme that just crossed the repetition bar (>=2 distinct outlets
  or >=3 headlines). Independent outlets covering the same thing is the signal;
  one outlet repeating itself is not.
- **ESCALATING** — max dollar figure grew >15%, OR headline count grew by >2.
- **FADING** — was >=3 headlines, now absent.

Toast only on NEW or ESCALATING. A tracker that fires every run gets ignored.

## Regex word boundaries are mandatory — substring matching is garbage

Both of these were real false positives on the first run:

- `"rug"` matched "d**rug** revenues" → a CVS earnings story classified as a
  DeFi exploit.
- `"treasury"` matched "US **Treasury**'s OFAC sanctions" → a sanctions story
  classified as BULLISH institutional adoption, inverting its meaning.

Use `re.search` with anchored patterns: `r"\bsec\b"` not `"sec "`,
`r"rug ?pull"` not `"rug"`, `r"crypto treasury|bitcoin treasury"` not
`"treasury"`. Always eyeball the first run's per-theme headlines and confirm
each one actually belongs — a mislabeled BULLISH theme is worse than no theme.

## Dollar-figure extraction

`\$\s?([\d,]+(?:\.\d+)?)\s*(m|million|b|billion|k)?` normalised to millions.
Caveat observed: a Coldcard headline mentioning "$800 million ETF inflows"
pushed the coldcard theme's max to $800M. The max-across-theme figure is a
crude escalation proxy, not a precise loss total — treat a jump as a prompt to
read the headlines, not as a number to quote.

## blogwatcher interface

Class is `BlogwatcherIntegration` (NOT `BlogwatcherClient`), wrapping
`C:\Users\victo\bin\blogwatcher-cli.exe`:

```python
from blogwatcher_integration import BlogwatcherIntegration
c = BlogwatcherIntegration(); c.scan()
arts = c.get_articles(limit=300, unread_only=False)   # ~300 rows
```

If the fetch returns empty, print and **do NOT write state** — an empty run
would wipe the baseline and make every theme look "new" next time.

## High-frequency mode (every 30 min) — anti-spam is mandatory

The user asked for "constantly" on 2026-08-08, so cadence went to `*/30 * * * *`
(48 runs/day). Naive run-over-run diffing CANNOT be used at that frequency —
headline counts drift upward all day and every run would toast. Three changes
make it viable:

1. **Escalate against the baseline AT LAST ALERT, not the previous run.**
   Persist `alert_baseline[theme] = {n, max_usd_m}` frozen at alert time. The
   next alert must beat THAT level. Otherwise a theme creeping n=8,9,10,11
   fires four times for one story.
2. **Per-theme cooldown** (`--cooldown-min`, default 180). A theme cannot
   re-alert within the window no matter what. Store `last_alert[theme]` ISO ts.
3. **Snapshot only when something alerted**, and prune to the newest 200 files.
   A per-run dump at 48/day buries the history dir in identical JSON.

Verification that matters — run this exact sequence after any change:
- cold start → alerts once
- immediate re-run → SILENT
- third re-run → SILENT
- age `last_alert` past cooldown AND lower `alert_baseline` → alerts again
Confirmed working 2026-08-08. If run 2 is not silent, the baseline freeze is
broken and the user will get 48 toasts a day and disable the whole thing.

## Scheduling

Weekend-frequent: `0 */4 * * 6,0` (every 4h Sat/Sun), `--quiet`,
`deliver='local'`, Windows toast. Respects the user's no-auto rule only because
they explicitly asked for it. Note cron requires the Hermes scheduler running —
say so, and give the manual command.

## Measured result 2026-08-08 (300 articles)

9 repeating themes. sanctions_regulatory n=16, stablecoin n=11,
coldcard_exploit n=10, exchange_hack n=8. Tone: 36 bearish-theme headlines vs
14 bullish → RISK-OFF. Non-obvious cross-current worth reporting: ETFs added
~$800M *in the wake of* the exploit, i.e. institutional flows absorbed the
hack — the news tape was uniformly bearish while flows were not.
