# PowerShell Command Quick Reference (MSYS Host)

Use these command recipes when the Hermes `terminal` tool is running through bash on a Windows host. Each PowerShell recipe is written as a `.ps1` file to avoid bash `$`‑eating issues.

## RAM / Process Audit

```powershell
# Write to C:/Users/victo/Desktop/ram_audit.ps1
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 25 Name, @{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB,1)}}, Id | Format-Table -AutoSize
```

```bash
pwsh.exe -ExecutionPolicy Bypass -File C:/Users/victo/Desktop/ram_audit.ps1
```

## Disk Audit

```powershell
# Write to C:/Users/victo/Desktop/disk_audit.ps1
Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -gt 0 } | Select-Object Name,@{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}},@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}} | Format-Table -AutoSize
```

```bash
pwsh.exe -ExecutionPolicy Bypass -File C:/Users/victo/Desktop/disk_audit.ps1
```

## Installed Programs > 50MB (sorted by size)

```powershell
# Write to C:/Users/victo/Desktop/installed_audit.ps1
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

## Running Services

```powershell
# Write to C:/Users/victo/Desktop/services_audit.ps1
Get-Service | Where-Object { $_.Status -eq 'Running' } | Sort-Object DisplayName | Select-Object Name, Status, StartType, DisplayName | Format-Table -AutoSize
```

## Disable & Stop a Service

```powershell
# Example: disable Windows Search indexer (saves ~77MB RAM)
# Write to C:/Users/victo/Desktop/disable_wsearch.ps1
Set-Service -Name "WSearch" -StartupType Disabled
Stop-Service -Name "WSearch" -Force
Write-Output "WSearch disabled and stopped."
```

## Clear Temp / Junk Folders

```bash
# Bash-native (no PowerShell needed)
rm -rf /c/Users/victo/AppData/Local/Temp/* 2>/dev/null
rm -rf /c/Users/victo/AppData/Local/NuGet/cache/* 2>/dev/null
rm -rf /c/Users/victo/AppData/Local/D3DSCache/* 2>/dev/null
```

## Uninstall Pattern (per-app, with timeout)

```powershell
# Write to C:/Users/victo/Desktop/uninstall_app.ps1
$ErrorActionPreference = "SilentlyContinue"
$appName = "Razor Cortex"  # change per target
$app = Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" | Where-Object { $_.DisplayName -like "*$appName*" } | Select-Object -First 1
if ($app) {
    $cmd = $app.UninstallString
    if ($cmd -match "msiexec") {
        $msiArgs = ($cmd -replace "msiexec.exe","").Trim() -replace "/I", "/X"
        Start-Process "msiexec.exe" -ArgumentList "$msiArgs /quiet /norestart" -Wait -NoNewWindow
    } elseif ($cmd) {
        Start-Process cmd.exe -ArgumentList "/c `"$cmd`" /S" -Wait -NoNewWindow
    }
    Write-Host "Uninstall launched for $($app.DisplayName)" -ForegroundColor Green
} else {
    Write-Host "$appName not found" -ForegroundColor Gray
}
```

**Important**: Run ONE uninstall per `.ps1` file with a timeout. Some uninstallers (Razer Cortex) hang on `-Wait`. If a script times out, kill the process and remove leftovers manually:

```powershell
# Remove leftover folders
$leftovers = @(
    "C:\Program Files (x86)\Razer",
    "$env:LOCALAPPDATA\Razer",
    "$env:APPDATA\Razer"
)
foreach ($p in $leftovers) {
    if (Test-Path $p) {
        Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "Removed: $p" -ForegroundColor Green
    }
}
```

## Post-Uninstall Cleanup Checklist

1. Check registry: `Get-ItemProperty "HKLM:\...\Uninstall\*", "HKCU:\...\Uninstall\*" | Where-Object { $_.DisplayName -like "*App*" }`
2. Check folders: `Test-Path "C:\Program Files\App"`, `Test-Path "$env:APPDATA\App"`, etc.
3. Remove leftovers with `Remove-Item -Recurse -Force`
4. Clear temp scripts: `Remove-Item C:\Users\victo\Desktop\*.ps1 -Force`

## Common Programs to Remove (Space Savings)

| Program | Size | Verdict |
|---------|------|---------|
|---------|------|---------|
| Razer Cortex | 642 MB | Bloatware — safe to remove |
| Stremio | 209 MB | Remove if unused |
| Grok Bot | 443 MB | Remove if unused |
| Java 8u503 | 227 MB | Ancient — update or remove |
| Office 2007 | 13 MB | Abandonware — remove |
| Dolby Audio X2 SDK | 9.5 MB | SDK not runtime — remove |
| PowerToys (Preview) | 1.26 GB | Duplicate of non-preview — remove preview |
| Ollama 0.34 | 2.8 GB | Remove if not running local models |

## Bash-Native Alternatives (No PowerShell)

| Task | Bash Command |
|------|--------------|
| Largest dirs | `du -sh /c/Users/victo/* 2>/dev/null \| sort -rh \| head -20` |
| Largest files (>100MB) | `find /c/Users/victo -type f -size +100M -exec ls -lh {} \; 2>/dev/null \| sort -k5 -rh \| head -20` |
| Process list | `tasklist /fo csv 2>/dev/null \| head -30` |
| High-RAM processes | `tasklist /fi "memusage gt 50000" /fo csv 2>/dev/null` |
| System RAM | `systeminfo 2>/dev/null \| grep -E "Total Physical\|Available Physical"` |
| Drive space | `df -h 2>/dev/null` |
| Installed programs | `wmic product get name,version /format:csv 2>/dev/null` |
