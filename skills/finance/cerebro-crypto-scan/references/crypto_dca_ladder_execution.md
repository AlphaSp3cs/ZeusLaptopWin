# Turning a bottom thesis into an executable DCA ladder + reminders

Follow-on request class: after a bottom study names candidates, the user asks
"build the ladder with exact tranche sizes and invalidation wired in, and tell
me when to DCA". Validated 2026-08-08 on NEAR/INJ.

## Why a ladder and not a lump
Measured on NEAR (entry at first sustained <=-90% day): lump -27.8% @12m /
+247.4% @24m; weekly DCA -16.5% / +301.8%. DCA won BOTH horizons and cut
12-month drawdown pain by ~11 points. Always default to DCA for this class.

## Ladder shape that works
5 tranches of 20% per name, split by trigger TYPE — not 5 identical weekly buys:
- T1 immediate, T2 week 2, T3 week 3  -> time-based, guarantees exposure
- T4 at -15% from spot, T5 at -28%    -> price-based, only fire on weakness

Rationale: time tranches get you positioned regardless of price; price tranches
mean a drop BUYS you more but the last add still sits above the invalidation
level. Never place a price tranche below invalidation — that is averaging into
a broken thesis.

Weight between names by base-quality score AND MA200 slope sign, not equally.
NEAR (score 75, slope +2.0%) got 60%; INJ (score 60, slope -8.6%) got 40%.

## Invalidation must be WEEKLY close, not daily
These assets ran 54-69% annualised vol. A daily-close rule against the cycle
low stops you out on noise. Use weekly close under the cycle low. On breach:
flip the symbol to HALTED in a state file, stop issuing tranches, notify, and
require a MANUAL edit to resume. Also carry a soft "warn level" (~-27% from
spot) meaning thesis intact but weakening — do not upsize.

## Reminders on CLI: no gateway means no message, use a Windows toast
A CLI session has no message channel, so `deliver='origin'` cron NEVER reaches
the terminal. Do not promise the user a ping that cannot arrive. Working
pattern:
- `deliver='local'`, `no_agent=true`, script does the notifying itself.
- Fire a native Windows toast from the script via PowerShell
  `Windows.UI.Notifications.ToastNotificationManager` (template 1, two text
  nodes). Wrap in try/except so a toast failure never kills the check.
- ALWAYS fire one test toast and ask the user to confirm they saw it. An
  unverified notification path is the same as no reminder.
- State honestly that cron only fires while the Hermes scheduler is running,
  and give the manual one-liner as the fallback.

## Cron script path constraint (real, not environment-specific)
`cronjob(script=...)` REJECTS absolute/home-relative paths:
"Script path must be relative to ~/.hermes/scripts/". Put a thin shell wrapper
in `~/.hermes/scripts/` that cd's to the real location:
```bash
#!/bin/bash
cd "$HOME" && python3 dca_ladder_check.py --quiet 2>&1
```
then pass just `dca_ladder_cron.sh`. Run the checker in a `--quiet` mode that
prints ONLY when a tranche is due or invalidation hit — a job that speaks every
week regardless is notification spam the user will mute.

## Checker script design
Single script, flags not separate scripts: `--budget <usd>` sets the sleeve,
`--fill SYM:N` records a filled tranche, `--quiet` for cron. Persist to
`dca_ladder_state.json` (started date, budget, filled tranches, halted flags).
Derive the week number from the ladder start date, not from the calendar.

## Framing for this user
Lead with the honest limitation (no message channel) BEFORE presenting the
ladder. Close with the risk that actually matters, in plain language — e.g.
"NEAR is only +0.6% above its MA200, that's the whole basis for its score and
it's paper-thin". When nothing passed the backtest, say the picks are "the
least-bad two in a wrecked field" and size as speculation you can eat -50% on.
