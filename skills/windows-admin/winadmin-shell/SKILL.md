---
name: winadmin-shell
description: Use when MSYS bash breaks PowerShell admin commands.
version: 1.0.0
author: Hermes Agent
category: windows-admin
---

# Windows Admin Shell Techniques

The Hermes `terminal` tool on Windows hosts runs through **bash (git-bash / MSYS)**, not PowerShell. This creates a specific failure mode when running PowerShell inline: **bash eats `$` variables**, producing parser errors, empty output, or silently wrong results.

Use this skill whenever you need to:
- Audit disk usage, RAM, processes, services, or installed programs
- Run PowerShell commands from the Hermes terminal
- Debug why a system query returned empty/mangled output

## The Core Pitfall

```bash
# FAILS — bash interprets $_.WorkingSet64 as a bash variable (empty)
powershell.exe -Command "Get-Process | Select-Object Name, @{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB,0)}}"
```

Bash expands `$_.WorkingSet64` to empty string before PowerShell sees it. Result: parser error or empty table.

## The Fix: Write .ps1 Files

Write the PowerShell script to a file, then execute with `pwsh.exe -File`:

```bash
# 1. Write script (use << 'EOF' to prevent bash $ expansion)
cat > /c/Users/victo/Desktop/myscript.ps1 << 'EOF'
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 15 Name, @{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB,1)}}, Id | Format-Table -AutoSize
EOF

# 2. Execute
pwsh.exe -ExecutionPolicy Bypass -File C:/Users/victo/Desktop/myscript.ps1
```

### Key Rules
- **`pwsh.exe`** (PowerShell Core) not `powershell.exe` — faster, more reliable
- **`-ExecutionPolicy Bypass`** — required; default policy blocks scripts
- **Forward slashes** in path: `C:/Users/victo/Desktop/file.ps1`
- **`<< 'EOF'`** (single-quoted delimiter) — prevents bash from expanding `$` inside the heredoc body

## When You Need This Pattern

Any PowerShell command using:
- Pipeline variables: `$_.Property`
- Calculated properties: `@{N='Name';E={Expression}}`
- Script blocks: `Where-Object { $_.Condition }`
- `$variable` references inside double-quoted strings

### Common Commands That Fail Inline

| Command | What breaks |
|---------|-------------|
| `Get-Process \| Sort-Object WorkingSet64` | `$_.WorkingSet64` |
| `Get-Service \| Where-Object { $_.Status -eq 'Running' }` | `$_.Status` |
| `Get-PSDrive -PSProvider FileSystem` | `$_.Used`, `$_.Free` |
| `Get-ItemProperty \| Select-Object @{N='Size';E={...}}` | Calculated property |
| `Get-WindowsOptionalFeature -Online` | Needs elevation + `$_.State` |

## Bash-Native Alternatives (No PowerShell)

Some queries can be done with bash tools, avoiding PowerShell entirely:

```bash
# Largest directories
du -sh /c/Users/victo/* 2>/dev/null | sort -rh | head -20

# Largest files (>100MB)
find /c/Users/victo -type f -size +100M -exec ls -lh {} \; 2>/dev/null | sort -k5 -rh | head -20

# Process list (simple, no calculated properties)
tasklist /fo csv 2>/dev/null | head -30

# Process memory filter
tasklist /fi "memusage gt 50000" /fo csv 2>/dev/null

# System RAM
systeminfo 2>/dev/null | grep -E "Total Physical|Available Physical"

# Installed programs (simple)
wmic product where "name like '%%'" get name,version /format:csv 2>/dev/null
```

Note: `du` and `find` are slower than PowerShell on large trees but avoid the escaping issue entirely.

## System Audit Quick Reference

### Disk Audit

```bash
# Per-drive usage (bash)
df -h 2>/dev/null

# Per-directory usage
du -sh /c/Users/victo/Desktop /c/Users/victo/Downloads /c/Users/victo/Documents /c/Users/victo/AppData/Local 2>/dev/null | sort -rh

# PowerShell (in .ps1 file)
Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}},@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}} | Format-Table -AutoSize
```

### RAM Audit

```bash
# PowerShell (in .ps1 file) — top 20 RAM consumers
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 20 Name, @{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB,1)}}, Id | Format-Table -AutoSize

# Bash alternative
systeminfo 2>/dev/null | grep -E "Total Physical|Available Physical"
tasklist /fi "memusage gt 50000" /fo csv 2>/dev/null
```

### Installed Programs Audit

```powershell
# PowerShell (in .ps1 file) — programs > 50MB, sorted by size
$regPaths = @(
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
$results = @()
foreach ($p in $regPaths) {
    $results += Get-ItemProperty $p -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -and $_.EstimatedSize -gt 50 } | Select-Object DisplayName, @{N='SizeMB';E={[math]::Round($_.EstimatedSize/1KB,1)}}, Publisher
}
$results | Sort-Object SizeMB -Descending | Select-Object -First 30 | Format-Table -AutoSize
```

### Service Audit

```powershell
# PowerShell (in .ps1 file) — services that are running
Get-Service | Where-Object { $_.Status -eq 'Running' } | Sort-Object DisplayName | Select-Object Name, Status, StartType, DisplayName | Format-Table -AutoSize

# Disable a service (example)
# Set-Service -Name "WSearch" -StartupType Disabled
# Stop-Service -Name "WSearch" -Force
```

## Uninstall + Leftover Cleanup Pattern

Uninstalling apps on Windows via Hermes requires care: uninstallers can hang, leave registry entries, and scatter files across `Program Files`, `%APPDATA%`, `%LOCALAPPDATA%`. Follow this sequence:

1. **One app per `.ps1` file** — don't batch uninstalls; one hang blocks everything.
2. **Check `UninstallString`** — if it contains `msiexec`, append `/quiet /norestart`. If it's an `.exe`, append `/S`.
3. **Run with timeout** — `pwsh.exe -File ...` with `timeout_s=120`. If it times out, kill the process.
4. **Remove filesystem leftovers** — check and delete from:
   - `C:\Program Files\<App>`
   - `C:\Program Files (x86)\<App>`
   - `%APPDATA%\<App>`
   - `%LOCALAPPDATA%\<App>`
   - `%PROGRAMDATA%\<App>`
5. **Remove registry leftovers** — check both `HKLM:\...\Uninstall` and `HKCU:\...\Uninstall`.
6. **Clean up temp scripts** — delete `.ps1` files from Desktop/Temp after use.

Full examples in `references/ps1-command-reference.md`.

## Pitfalls

- **Empty output is the tell.** If a PowerShell command returns nothing or a parser error, suspect bash `$`-eating first — not a Windows problem.
- **`pwsh.exe` vs `powershell.exe`**: `pwsh.exe` is PowerShell Core (faster, cross-platform). `powershell.exe` is Windows PowerShell 5.1 (slower, but always present). Prefer `pwsh.exe`.
- **Path separators**: Use forward slashes in `.ps1` file paths passed to `pwsh.exe -File`. MSYS bash doesn't translate them for native Windows executables.
- **Heredoc delimiter**: Always `<< 'EOF'` not `<< EOF`. The single quotes prevent bash expansion of `$` inside the body.
- **Temp file location**: Write `.ps1` files to a writable location like `/c/Users/victo/Desktop/` or `$env:TEMP`. The working directory may not be writable.
- **cmd.exe wrapper is fragile**: `cmd /c "powershell -Command \"...\"""` requires triple-escaping — prefer `.ps1` files.
- **Elevation**: Some commands (like `Get-WindowsOptionalFeature -Online`) require admin elevation and will fail even with correct escaping.
- **Uninstallers hang**: Some uninstallers (e.g., Razer Cortex) hang when run via `Start-Process -Wait`. Run them one at a time with a timeout, or skip and remove leftovers manually.
- **Leftovers persist**: After uninstalling, check both registry (`HKLM:\...\Uninstall`, `HKCU:\...\Uninstall`) AND filesystem (`Program Files`, `ProgramData`, `%APPDATA%`, `%LOCALAPPDATA%`) for leftover entries/folders. Remove manually with `Remove-Item -Recurse -Force`.
- **Clean up your temp scripts**: After running `.ps1` audit/cleanup scripts from the Desktop or Temp, delete them so they don't clutter the workspace.

## Overlap Note

This skill covers hands-on shell technique for Windows administration. For broader Windows admin concepts (GPO, AD, server roles), see `winadmin-mega` (user-owned). If you frequently need both, recommend `hermes curator adopt winadmin-mega` so they can be consolidated by the background curator.

## Support Files

- `references/ps1-command-reference.md` — quick-copy command recipes for RAM/disk/program/service audits, plus a table of common bloatware to remove during system cleanup.