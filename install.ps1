<#
.SYNOPSIS
  Install Alif's 3D Agent on this PC: check the environment, install dependencies,
  register the Claude Code plugin, then run the doctor. Safe to re-run.

.DESCRIPTION
  1. scripts\check-env.ps1  - read-only report of what the PC has
  2. scripts\setup.ps1      - uv, Blender (asks), MCP addon on port 9877, Playwright,
                              GPU detection, workspace, local.config.json
  3. Claude Code            - adds this folder as a marketplace and installs the plugin
  4. scripts\doctor.py      - pass/fail for the whole setup

.PARAMETER InstallBlender     Install Blender with winget without asking.
.PARAMETER NoBlenderInstall   Never install Blender.
.PARAMETER WithFusion         Also install the Fusion360MCP add-in.
.PARAMETER Workspace          Workspace folder (default %USERPROFILE%\Alif3D).
.PARAMETER SkipPlugin         Don't register the plugin with Claude Code.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install.ps1
  powershell -ExecutionPolicy Bypass -File .\install.ps1 -InstallBlender -WithFusion
#>
[CmdletBinding()]
param(
    [switch]$InstallBlender,
    [switch]$NoBlenderInstall,
    [switch]$WithFusion,
    [string]$Workspace,
    [switch]$SkipPlugin
)

$ErrorActionPreference = 'Stop'
$Repo = $PSScriptRoot
$PluginId = 'alifs-3d-agent@alifs-3d-agent'
$env:PYTHONIOENCODING = 'utf-8'

function Phase($n, $msg) { Write-Host "`n########## $n. $msg ##########" -ForegroundColor Magenta }
function Run-Native {
    $exe, $rest = $args
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { & $exe @rest 2>&1 | ForEach-Object { "$_" } } finally { $ErrorActionPreference = $old }
}
function Find-Claude {
    $c = Get-Command claude -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
    if ($c) { return $c }
    if (Test-Path "$HOME\.local\bin\claude.exe") { return "$HOME\.local\bin\claude.exe" }
    return Get-ChildItem "$HOME\.vscode\extensions" -Directory -Filter 'anthropic.claude-code-*' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | ForEach-Object { Join-Path $_.FullName 'resources\native-binary\claude.exe' } |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}

Write-Host "Alif's 3D Agent installer  ($Repo)" -ForegroundColor Cyan

# ---------------------------------------------------------------- 1. check
Phase 1 'Environment check'
& (Join-Path $Repo 'scripts\check-env.ps1')

# ---------------------------------------------------------------- 2. dependencies
Phase 2 'Install dependencies'
$setupArgs = @{}
foreach ($k in 'InstallBlender', 'NoBlenderInstall', 'WithFusion') {
    if ($PSBoundParameters.ContainsKey($k)) { $setupArgs[$k] = $true }
}
if ($Workspace) { $setupArgs.Workspace = $Workspace }
& (Join-Path $Repo 'scripts\setup.ps1') @setupArgs

# ---------------------------------------------------------------- 3. plugin
Phase 3 'Register the Claude Code plugin'
$claude = Find-Claude
if ($SkipPlugin) {
    Write-Host '    skipped (-SkipPlugin)'
} elseif ($claude) {
    $known = Run-Native $claude plugin marketplace list | Out-String
    if ($known -match 'alifs-3d-agent') {
        Run-Native $claude plugin marketplace update alifs-3d-agent | Out-Host
    } else {
        Run-Native $claude plugin marketplace add $Repo | Out-Host
    }
    $installed = Run-Native $claude plugin list | Out-String
    if ($installed -match [regex]::Escape($PluginId)) { Write-Host "    already installed: $PluginId" -ForegroundColor Green }
    else { Run-Native $claude plugin install $PluginId | Out-Host }
} else {
    Write-Host '    Claude Code CLI not found. In Claude Code, type:' -ForegroundColor Yellow
    Write-Host "      /plugin marketplace add $Repo"
    Write-Host "      /plugin install $PluginId"
}

# ---------------------------------------------------------------- 4. doctor
Phase 4 'Doctor'
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) { Run-Native uv run --quiet (Join-Path $Repo 'scripts\doctor.py') | Out-Host }
else { Write-Host '    uv not on PATH yet: open a new terminal and run  uv run scripts\doctor.py' -ForegroundColor Yellow }

Write-Host "`nNext: restart Claude Code, open Blender, then try  /alifs-3d-agent:studio-doctor  and  /alifs-3d-agent:shoot <file>" -ForegroundColor Cyan
Write-Host "Port 9877 FAIL above is normal until Blender is open." -ForegroundColor Gray
