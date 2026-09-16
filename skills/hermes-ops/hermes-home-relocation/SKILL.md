---
name: hermes-home-relocation
description: Relocate Hermes data dir to another drive.
---

# Hermes Home Relocation

## When to use
- User wants Hermes data off the system drive (C:) to save space, or to live on a specific path (e.g. `D:\Hermes`).
- "Move all my Hermes stuff to D", "my C drive is full", "point Hermes at another folder".

## Key facts (verify before touching anything)
1. Hermes reads its data dir from the `HERMES_HOME` env var. Default is `~/.hermes` on Linux/macOS and `%LOCALAPPDATA%\hermes` on Windows. It scopes config, skills, sessions, `state.db`, logs, caches, AND the gateway PID file.
2. The Windows installer bakes the absolute path of the venv launchers into `hermes.exe` and the gateway Startup VBS (`%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe`). So setting `HERMES_HOME` alone is NOT enough — if you delete the C: folder, the launchers break. The robust fix is to leave a directory junction at the old C: path pointing at the new location.
3. There may be a STALE second copy at `~/.hermes` (Linux-style) that is abandoned. Confirm the ACTIVE home via the `HERMES_HOME` env value plus the newest `config.yaml` plus `auth.json`'s `active_provider`. Do not migrate the stale one.

## Workflow (Windows, C: to D:)

1. Diagnose active home + size:
   - `reg query "HKCU\Environment" /v HERMES_HOME` (or `echo $HERMES_HOME` in git-bash).
   - `du -sh "$LOCALAPPDATA/hermes"` (run in background if it times out — big `state.db`).
   - Confirm live home: compare `config.yaml` mtime and `auth.json` `active_provider` between candidates.
2. Create target dirs: `mkdir D:\Hermes` and `mkdir D:\Hermes\Downloads`.
3. If the target already holds an OLD or STALE install (e.g. `D:\Hermes` exists with its own `state.db`, different model/provider in `config.yaml`, older mtime): move it aside INTACT (recoverable, never delete): `Move-Item D:\Hermes D:\Hermes.old`. Watch for "Access denied" from a transient Defender/Search lock on `state.db` — retry, or stop the Windows Search service (needs admin).
4. Copy the live home to D: with robocopy (copies open files via shadow semantics, preserves timestamps/ACLs):
   `robocopy "C:\Users\victo\AppData\Local\hermes" "D:\Hermes" /E /COPY:DAT /R:2 /W:2 /NFL /NDL /NP`
   Exit code 3 means "copied + extras at dest" (harmless; extras = the pre-created `Downloads` subdir).
   PITFALL: do NOT launch robocopy via git-bash `cmd /c "robocopy \"src\" \"dst\""` — quotes/backslashes get mangled (you will see `C:\Users\victo\"C:\...\"` and ERROR 123). Wrap in a `.cmd` file and run `cmd /c file.cmd` (see references/verified-commands.md).
5. Set HERMES_HOME in the user environment:
   `reg add "HKCU\Environment" /v HERMES_HOME /t REG_SZ /d "D:\Hermes" /f`
6. Redirect Downloads: move existing `C:\Users\victo\Downloads` contents into `D:\Hermes\Downloads`, then junction:
   `move C:\Users\victo\Downloads C:\Users\victo\Downloads.cdrive.bak`
   `mklink /J C:\Users\victo\Downloads D:\Hermes\Downloads`
   Verify: `fsutil reparsepoint query C:\Users\victo\Downloads` shows Tag `0xa0000003` (Name Surrogate / Mount Point).
7. The C: home junction requires a Hermes RESTART. You CANNOT rename or move `%LOCALAPPDATA%\hermes` while Hermes is running — this session and its child python processes hold handles (`state.db`, `gateway.pid`, the terminal snap script). `move` returns "Access is denied". So:
   - Do steps 1-6 now (they do not touch the live home).
   - Ask the user to FULLY quit Hermes (desktop app + this session).
   - After restart, move the now-unlocked C: home aside (`move %LOCALAPPDATA%\hermes %LOCALAPPDATA%\hermes.cdrive.bak`) and create the junction `mklink /J %LOCALAPPDATA%\hermes D:\Hermes`.
   - Relaunch `hermes config get model` to prove it reads from `D:\Hermes`, then delete `.cdrive.bak` to free C:.
8. Validate: `hermes config get model` resolves; `dir D:\Hermes\config.yaml` works via the junction; gateway still auto-starts from the Startup VBS.

## PITFALLS
- git-bash to cmd quoting (general Windows gotcha): compound `cmd /c "..."` commands with nested quotes or backslashes break silently (ERROR 123 / "syntax is incorrect"). This hits `robocopy`, `mklink`, `move`, `reg`, `findstr`. Always write a `.cmd` file and execute `cmd /c file.cmd`. Powershell `-File` also mangles `$_` through git-bash — put scripts in `.ps1` files too.
- Powershell Move-Item nesting: `Move-Item A B` when `B` already exists as a folder MOVES A into B (B\A), not renames A to B. If you must rename, ensure the destination does not exist, or use `cmd /c move`. (This is how a half-moved `D:\Hermes` ended up as `D:\Hermes.old\Hermes\...` — recoverable, just untidy.)
- Stale second home: a leftover `~/.hermes` may exist and confuse you. The active Windows home is `%LOCALAPPDATA%\hermes`.
- Never delete the C: home (unless reinstalling): the launchers' baked paths live there. Always junction, never delete.
- Old install at target: `D:\Hermes` may already exist from a previous install attempt. Preserve it as `.old`; do not overwrite.
- Partial-move fragments: a failed `move` can scatter top-level items as `Hermes_tmp_*` siblings. Consolidate them back with a Powershell loop that strips the prefix (see references/verified-commands.md).

## references/
- `references/verified-commands.md` — exact `.cmd`/`.ps1` wrappers and diagnosis commands that worked this session (robocopy, cutover, downloads cutover, old-install consolidation), plus observed results.
