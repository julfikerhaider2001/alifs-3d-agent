<#
.SYNOPSIS
  Read-only environment check for Alif's 3D Agent. Changes nothing.

.DESCRIPTION
  Reports what this PC already has and what install.ps1 would still need to install:
  Windows, PowerShell, winget, git, GitHub login, uv, Blender, Fusion 360, GPU,
  Claude Code CLI, free disk space, and MCP servers that would clash with the plugin's.

  Each line is:  [OK]  / [NEED] (install.ps1 will install it) / [WARN] / [INFO]
  With -Json the same results are printed as JSON (for Claude to read).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\check-env.ps1
#>
[CmdletBinding()]
param([switch]$Json)

$ErrorActionPreference = 'Continue'
$results = New-Object System.Collections.Generic.List[object]
function Add($status, $name, $detail, $action = '') {
    $results.Add([pscustomobject]@{ status = $status; check = $name; detail = $detail; action = $action })
}
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User') + ";$HOME\.local\bin"
}
Refresh-Path

# Windows + PowerShell
$os = Get-CimInstance Win32_OperatingSystem
$build = [int]$os.BuildNumber
if ($build -ge 19041) { Add 'OK' 'Windows' "$($os.Caption) build $build" }
else { Add 'WARN' 'Windows' "$($os.Caption) build $build" 'Windows 10 2004+ or Windows 11 recommended' }
Add 'INFO' 'PowerShell' $PSVersionTable.PSVersion.ToString()

# winget
$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) { Add 'OK' 'winget' (& winget --version) }
else { Add 'WARN' 'winget' 'not found' 'Install "App Installer" from the Microsoft Store; needed to install uv/Blender' }

# git + GitHub login
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) { Add 'OK' 'git' ((& git --version) -replace 'git version ', '') }
else { Add 'NEED' 'git' 'not found' 'winget install --id Git.Git -e' }
$gh = Get-Command gh -ErrorAction SilentlyContinue
if ($gh) {
    $null = & gh auth status 2>&1
    if ($LASTEXITCODE -eq 0) {
        $who = (& gh api user --jq .login 2>$null)
        Add 'OK' 'GitHub login' "gh logged in as $who"
    } else { Add 'WARN' 'GitHub login' 'gh not logged in' 'gh auth login, then gh auth setup-git (needed for git pull of the private repo)' }
} else { Add 'INFO' 'GitHub CLI' 'not installed (optional; git credential manager also works)' }

# uv
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) { Add 'OK' 'uv' (& uv --version) } else { Add 'NEED' 'uv' 'not found' 'install.ps1 installs it with winget (astral-sh.uv)' }

# Blender
$blender = $null
$cfgPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'local.config.json'
if (Test-Path $cfgPath) {
    $c = Get-Content $cfgPath -Raw | ConvertFrom-Json
    if ($c.blender_path -and (Test-Path $c.blender_path)) { $blender = $c.blender_path }
}
if (-not $blender) {
    $cmd = Get-Command blender -ErrorAction SilentlyContinue
    if ($cmd) { $blender = $cmd.Source }
}
if (-not $blender) {
    $keys = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
    $hit = Get-ItemProperty $keys -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match '^Blender' -and $_.InstallLocation } | Select-Object -First 1
    if ($hit -and (Test-Path (Join-Path $hit.InstallLocation 'blender.exe'))) { $blender = Join-Path $hit.InstallLocation 'blender.exe' }
}
if (-not $blender) {
    foreach ($r in "$env:ProgramFiles\Blender Foundation", "${env:ProgramFiles(x86)}\Steam\steamapps\common\Blender") {
        if (Test-Path $r) {
            $f = Get-ChildItem $r -Filter blender.exe -Recurse -Depth 2 -ErrorAction SilentlyContinue |
                 Sort-Object { $_.Directory.Name } -Descending | Select-Object -First 1
            if ($f) { $blender = $f.FullName; break }
        }
    }
}
if ($blender) { Add 'OK' 'Blender' $blender }
else { Add 'NEED' 'Blender' 'not installed (~400 MB)' 'install.ps1 -InstallBlender installs it with winget (BlenderFoundation.Blender); ask the user first' }

# Fusion 360
$fusion = Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -match 'Autodesk Fusion' } | Select-Object -First 1
$addin = Join-Path $env:APPDATA 'Autodesk\Autodesk Fusion 360\API\AddIns\Fusion360MCP\Fusion360MCP.py'
if ($fusion) {
    $state = if (Test-Path $addin) { 'Fusion360MCP add-in installed' } else { 'add-in not installed (install.ps1 -WithFusion)' }
    Add 'INFO' 'Fusion 360' "installed; $state"
} else { Add 'INFO' 'Fusion 360' 'not installed (optional)' }

# GPU
$gpus = Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name
$hint = 'CPU'
if ($gpus -match 'NVIDIA') { $hint = 'OptiX/CUDA likely' } elseif ($gpus -match 'AMD|Radeon') { $hint = 'HIP likely' }
Add 'INFO' 'GPU' (($gpus -join '; ') + " -> $hint (setup asks Blender for the exact backend)")

# Claude Code CLI
$claude = Get-Command claude -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (-not $claude -and (Test-Path "$HOME\.local\bin\claude.exe")) { $claude = "$HOME\.local\bin\claude.exe" }
if (-not $claude) {
    $claude = Get-ChildItem "$HOME\.vscode\extensions" -Directory -Filter 'anthropic.claude-code-*' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | ForEach-Object { Join-Path $_.FullName 'resources\native-binary\claude.exe' } |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ($claude) { Add 'OK' 'Claude Code CLI' $claude }
else { Add 'WARN' 'Claude Code CLI' 'not found' 'install.ps1 will print the /plugin commands to type in Claude Code instead' }

# Disk space on the system drive
$drive = Get-PSDrive -Name ($env:SystemDrive.TrimEnd(':'))
$freeGB = [math]::Round($drive.Free / 1GB, 1)
if ($freeGB -ge 5) { Add 'OK' 'Free disk' "$freeGB GB on $env:SystemDrive" }
else { Add 'WARN' 'Free disk' "$freeGB GB on $env:SystemDrive" 'Blender + Chromium + renders need about 5 GB' }

# MCP servers that would fight over Blender (only one client may connect)
$cj = Join-Path $HOME '.claude.json'
if (Test-Path $cj) {
    try {
        $j = Get-Content $cj -Raw | ConvertFrom-Json
        $found = @()
        if ($j.mcpServers.blender) { $found += 'user scope' }
        foreach ($p in $j.projects.PSObject.Properties) { if ($p.Value.mcpServers.blender) { $found += "project $($p.Name)" } }
        if ($found) { Add 'WARN' 'Other Blender MCP' ("'blender' server also configured in: " + ($found -join ', ')) 'Only one MCP client can use Blender at a time; ask the user whether to remove it (claude mcp remove blender)' }
        else { Add 'OK' 'Other Blender MCP' 'none' }
    } catch { Add 'INFO' 'Other Blender MCP' 'could not read ~/.claude.json' }
}

if ($Json) { $results | ConvertTo-Json -Depth 3; return }
Write-Host "`nAlif's 3D Agent - environment check (nothing was changed)`n" -ForegroundColor Cyan
foreach ($r in $results) {
    $color = @{ OK = 'Green'; NEED = 'Yellow'; WARN = 'Yellow'; INFO = 'Gray' }[$r.status]
    Write-Host ("[{0,-4}] {1}: {2}" -f $r.status, $r.check, $r.detail) -ForegroundColor $color
    if ($r.action) { Write-Host "         -> $($r.action)" }
}
$need = @($results | Where-Object status -eq 'NEED').Count
Write-Host "`n$need item(s) for install.ps1 to install."
