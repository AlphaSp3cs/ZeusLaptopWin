# Verified commands — Hermes home relocation (Windows)

All commands below were executed successfully in this session. Run them as files
(`cmd /c file.cmd` or `powershell -ExecutionPolicy Bypass -File file.ps1`), NOT
inline through git-bash `cmd /c "..."` — inline quoting mangles backslashes and
breaks robocopy/mklink/move (ERROR 123 / "syntax is incorrect").

## Diagnose active home
```
echo HERMES_HOME=$HERMES_HOME
reg query "HKCU\Environment" /v HERMES_HOME
du -sh "$LOCALAPPDATA/hermes"          # run background; big state.db
# active = newest config.yaml + auth.json active_provider
grep -o '"active_provider": "[^"]*"' "$LOCALAPPDATA/hermes/auth.json"
```

## robocopy_hermes.cmd   (copy live home to D:)
```
@echo off
robocopy "C:\Users\victo\AppData\Local\hermes" "D:\Hermes" /E /COPY:DAT /R:2 /W:2 /NFL /NDL /NP /LOG:"C:\Users\victo\robocopy_hermes.log"
echo robocopy_exit=%ERRORLEVEL% >> "C:\Users\victo\robocopy_hermes.log"
```
Result this session: 20,251 files / 1.648 GB copied, 0 failed. Exit code 3 = OK
(copied + 1 extra = pre-created Downloads subdir).

## downloads_cutover.cmd   (move Downloads aside + junction to D:)
```
@echo off
set "DL=C:\Users\victo\Downloads"
set "DLD=D:\Hermes\Downloads"
reg add "HKCU\Environment" /v HERMES_HOME /t REG_SZ /d "D:\Hermes" /f
if exist "%DL%" (
  if exist "%DLD%" ( robocopy "%DL%" "%DLD%" /E /COPY:DAT /R:1 /W:1 /NFL /NDL /NP /LOG:"C:\Users\victo\robocopy_dl.log" )
  if not exist "%DL%.cdrive.bak" ( move "%DL%" "%DL%.cdrive.bak" )
)
if not exist "%DL%" ( mklink /J "%DL%" "%DLD%" )
```
Verify junction: `fsutil reparsepoint query C:\Users\victo\Downloads`
→ "Reparse Tag Value : 0xa0000003" (Name Surrogate / Mount Point).

## cutover.cmd   (AFTER user fully quits Hermes — move C: home aside + junction)
```
@echo off
set "SRC=C:\Users\victo\AppData\Local\hermes"
set "BAK=C:\Users\victo\AppData\Local\hermes.cdrive.bak"
set "DST=D:\Hermes"
if exist "%SRC%" ( if not exist "%BAK%" ( move "%SRC%" "%BAK%" ) )
if not exist "%SRC%" ( mklink /J "%SRC%" "%DST%" )
```
Cannot run while Hermes is live: "Access is denied" (state.db / gateway.pid / snap
script held open). Requires full restart first.

## consolidate_old.ps1   (merge Hermes_tmp_* fragments back into D:\Hermes.old)
```
$prefix = 'Hermes_tmp_'
$dest = 'D:\Hermes.old'
$items = Get-ChildItem -Path 'D:\' -Filter "$prefix*" -ErrorAction SilentlyContinue
$moved = 0; $skipped = 0
foreach ($it in $items) {
    $orig = $it.Name.Substring($prefix.Length)
    $target = Join-Path $dest $orig
    if (Test-Path $target) {
        $dup = Join-Path (Join-Path $dest '.dup') $orig
        if (-not (Test-Path (Join-Path $dest '.dup'))) { New-Item -ItemType Directory -Path (Join-Path $dest '.dup') | Out-Null }
        try { Move-Item -Path $it.FullName -Destination $dup -Force -ErrorAction Stop; $moved++ } catch { $skipped++ }
    } else {
        try { Move-Item -Path $it.FullName -Destination $target -Force -ErrorAction Stop; $moved++ } catch { $skipped++ }
    }
}
Write-Output "moved=$moved skipped=$skipped"
```
Result: moved=128 skipped=0.

## move_old.ps1   (move stale D:\Hermes aside to D:\Hermes.old — recoverable)
```
try {
    Move-Item -Path 'D:\Hermes' -Destination 'D:\Hermes.old' -Force -ErrorAction Stop
    Write-Output 'PS_MOVE_OK'
} catch {
    Write-Output ('PS_MOVE_FAIL: ' + $_.Exception.Message)
}
```
NOTE: if `D:\Hermes.old` already exists as a folder, this nests into
`D:\Hermes.old\Hermes\...` (Move-Item-into-folder behavior). Recoverable, just untidy.

## Observed results / lessons
- robocopy /COPY:DAT copies the live state.db even while Hermes holds it open.
- `D:\Hermes` may already exist (old install). Preserve as `.old`; never overwrite/delete.
- `~/.hermes` (C:\Users\victo\.hermes) was a stale abandoned copy; active home is
  `%LOCALAPPDATA%\hermes`.
- After cutover, free C: by deleting `%LOCALAPPDATA%\hermes.cdrive.bak` ONLY after
  `hermes config get model` proves D: is the live home.
