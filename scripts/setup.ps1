<#
.SYNOPSIS
  One-time (and safe to re-run) per-PC setup for alifs-3d-agent.

.DESCRIPTION
  - Installs uv (winget astral-sh.uv) if missing
  - Finds Blender; offers to install it with winget if missing (asks first)
  - Installs + enables the MCP for Blender addon from the command line and sets its port to 9877
  - Installs Playwright Chromium for poster export
  - Detects the Cycles GPU backend (OptiX > CUDA > HIP > CPU)
  - Creates the workspace from workspace-template/ (never overwrites your files)
  - Writes local.config.json at the repo root and sets ALIF3D_CONFIG for your user
  - With -WithFusion: installs the Fusion360MCP add-in (Fusion uses port 9876)

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
  powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -WithFusion -Workspace D:\Alif3D
#>
[CmdletBinding()]
param(
    [switch]$WithFusion,
    [switch]$InstallBlender,      # install Blender with winget without asking
    [switch]$NoBlenderInstall,    # never offer to install Blender
    [string]$Workspace,
    [string]$BlenderPath
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Keep in sync with .mcp.json and scripts/export_poster.py
$BlenderMcpPackage = 'mcp-for-blender==2.1.9'
$PlaywrightVersion = '1.64.0'
$BlenderMcpPort    = 9877
$FusionMcpPort     = 9876

$RepoRoot   = Split-Path -Parent $PSScriptRoot
$ConfigPath = Join-Path $RepoRoot 'local.config.json'
$env:PYTHONIOENCODING = 'utf-8'   # uv tools print non-ASCII; cp1252 consoles crash on it

$Done = New-Object System.Collections.Generic.List[string]
$Todo = New-Object System.Collections.Generic.List[string]

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    ok: $msg" -ForegroundColor Green; $Done.Add($msg) }
function Warn($msg) { Write-Host "    !!  $msg" -ForegroundColor Yellow; $Todo.Add($msg) }

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user    = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user;$HOME\.local\bin"
}

function Test-Interactive {
    # Claude Code (and other tools) run scripts with no keyboard; never block on Read-Host there.
    if ([Console]::IsInputRedirected) { return $false }
    return [Environment]::UserInteractive -and -not ([Environment]::GetCommandLineArgs() -match '^-NonI')
}

function Write-Utf8NoBom($path, $text) {
    [IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false))
}

# Run a native exe, returning stdout+stderr as strings. PS 5.1 turns redirected stderr
# into errors, which 'Stop' would make fatal, so relax it just for the call.
function Run-Native {
    $exe, $rest = $args
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { & $exe @rest 2>&1 | ForEach-Object { "$_" } } finally { $ErrorActionPreference = $old }
}

# ------------------------------------------------------------------ existing config
$cfg = [ordered]@{}
if (Test-Path $ConfigPath) {
    $old = Get-Content $ConfigPath -Raw | ConvertFrom-Json
    foreach ($p in $old.PSObject.Properties) { $cfg[$p.Name] = $p.Value }
    Write-Host "Found existing $ConfigPath (will update it)"
}

# ------------------------------------------------------------------ 1. uv
Step 'uv'
Refresh-Path
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Run-Native winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements | Out-Host
    Refresh-Path
}
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) { Ok "uv: $(& uv --version)" }
else { Warn 'uv is not on PATH after install. Open a NEW terminal and re-run setup.ps1.'; }

# ------------------------------------------------------------------ 2. Blender
function Find-Blender {
    $cands = New-Object System.Collections.Generic.List[string]
    if ($BlenderPath) { $cands.Add($BlenderPath) }
    if ($cfg.blender_path) { $cands.Add([string]$cfg.blender_path) }
    $cmd = Get-Command blender -ErrorAction SilentlyContinue
    if ($cmd) { $cands.Add($cmd.Source) }
    $keys = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
    Get-ItemProperty $keys -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match '^Blender' -and $_.InstallLocation } |
        ForEach-Object { $cands.Add((Join-Path $_.InstallLocation 'blender.exe')) }
    $roots = @("$env:ProgramFiles\Blender Foundation", "$env:LOCALAPPDATA\Programs\Blender Foundation",
               "${env:ProgramFiles(x86)}\Steam\steamapps\common\Blender")
    foreach ($r in $roots) {
        if (Test-Path $r) {
            Get-ChildItem $r -Filter blender.exe -Recurse -Depth 2 -ErrorAction SilentlyContinue |
                Sort-Object { $_.Directory.Name } -Descending | ForEach-Object { $cands.Add($_.FullName) }
        }
    }
    foreach ($c in $cands) { if ($c -and (Test-Path $c -PathType Leaf)) { return (Resolve-Path $c).Path } }
    return $null
}

Step 'Blender'
$blender = Find-Blender
if (-not $blender -and -not $NoBlenderInstall) {
    $answer = 'n'
    if ($InstallBlender) { $answer = 'y' }
    elseif (Test-Interactive) { $answer = Read-Host '    Blender not found. Install it now with winget (BlenderFoundation.Blender)? [y/N]' }
    if ($answer -match '^[yY]') {
        Run-Native winget install --id BlenderFoundation.Blender -e --accept-source-agreements --accept-package-agreements | Out-Host
        $blender = Find-Blender
    }
}
if ($blender) {
    $cfg.blender_path = $blender
    $ver = (Run-Native $blender -b --factory-startup --version | Select-String '^Blender\s+(\S+)' | Select-Object -First 1)
    if ($ver) { $cfg.blender_version = $ver.Matches[0].Groups[1].Value }
    Ok "Blender $($cfg.blender_version) at $blender"
} else {
    Warn 'Blender not found. Install it (winget install BlenderFoundation.Blender) and re-run setup.ps1 (or install.ps1 -InstallBlender).'
}

# ------------------------------------------------------------------ 3. Blender MCP addon
if ($blender -and $uv) {
    Step "MCP for Blender addon ($BlenderMcpPackage)"
    $tmp = Join-Path $env:TEMP 'alifs-3d-agent-addon'
    New-Item -ItemType Directory -Force $tmp | Out-Null
    $addonFile = Join-Path $tmp 'blender_mcp.py'
    Remove-Item $addonFile -ErrorAction SilentlyContinue
    # The addon bundled with the pinned server package, so their protocol versions match.
    Run-Native uvx $BlenderMcpPackage install-addon --addons-dir $tmp | Out-Null
    if (-not (Test-Path $addonFile)) {
        Write-Host '    package install-addon failed; downloading addon.py from GitHub instead'
        Invoke-WebRequest 'https://raw.githubusercontent.com/ahujasid/blender-mcp/main/addon.py' -OutFile $addonFile -UseBasicParsing
    }
    $src = $addonFile.Replace("'", "\'")
    $expr = "import bpy, addon_utils, shutil, os; d = bpy.utils.user_resource('SCRIPTS', path='addons', create=True); shutil.copy2(r'$src', os.path.join(d, 'blender_mcp.py')); addon_utils.enable('blender_mcp', default_set=True, persistent=True); bpy.ops.wm.save_userpref(); print('RS_ADDON_OK' if 'blender_mcp' in bpy.context.preferences.addons else 'RS_ADDON_FAIL')"
    $out = Run-Native $blender -b --python-exit-code 1 --python-expr $expr | Out-String
    if ($out -match 'RS_ADDON_OK') { Ok 'Blender MCP addon installed + enabled, user prefs saved' }
    else { Warn "Addon install failed. Blender output tail:`n$($out.Trim() -split "`n" | Select-Object -Last 8 | Out-String)" }

    # Port lives on the scene, so set it in the startup file every new scene starts from.
    $expr2 = "import bpy; s = bpy.context.scene; s.blendermcp_port = $BlenderMcpPort; s.blendermcp_use_polyhaven = True; s.blendermcp_auto_start_server = True; bpy.ops.wm.save_homefile(); print('RS_PORT_OK', s.blendermcp_port)"
    $out2 = Run-Native $blender -b --python-exit-code 1 --python-expr $expr2 | Out-String
    if ($out2 -match "RS_PORT_OK $BlenderMcpPort") { Ok "Addon port $BlenderMcpPort + Poly Haven saved in Blender startup file" }
    else { Warn "Could not save the startup file. In Blender: N panel > MCP for Blender > Port $BlenderMcpPort, tick Poly Haven, then File > Defaults > Save Startup File." }
}

# ------------------------------------------------------------------ 4. GPU backend
if ($blender -and $uv) {
    Step 'GPU backend (OptiX > CUDA > HIP > CPU)'
    $probeOut = Run-Native $blender -b --python-exit-code 1 --python (Join-Path $PSScriptRoot 'doctor.py') '--' '--probe' | Out-String
    $line = ($probeOut -split "`r?`n") | Where-Object { $_ -like 'RS_PROBE *' } | Select-Object -First 1
    if ($line) {
        $probe = $line.Substring(9) | ConvertFrom-Json
        $cfg.gpu_backend = $probe.best_backend
        $names = ''
        if ($probe.best_backend -ne 'CPU') { $names = ' (' + (($probe.gpus.($probe.best_backend)) -join ', ') + ')' }
        Ok "GPU backend: $($probe.best_backend)$names"
    } else {
        if (-not $cfg.gpu_backend) { $cfg.gpu_backend = 'CPU' }
        Warn "GPU probe failed; using $($cfg.gpu_backend). Run /alifs-3d-agent:studio-doctor for details."
    }
} elseif (-not $cfg.gpu_backend) { $cfg.gpu_backend = 'CPU' }

# ------------------------------------------------------------------ 5. Playwright Chromium
if ($uv) {
    Step "Playwright $PlaywrightVersion Chromium"
    Run-Native uvx --from "playwright==$PlaywrightVersion" playwright install chromium | Out-Host
    if ($LASTEXITCODE -eq 0) { Ok 'Playwright Chromium installed' }
    else { Warn "Playwright install failed. Retry: uvx --from playwright==$PlaywrightVersion playwright install chromium" }
}

# ------------------------------------------------------------------ 5b. Fit engine (trimesh etc.)
if ($uv) {
    Step 'Fit engine (mesh analysis for /fit)'
    $fitOut = Run-Native uv run --quiet (Join-Path $PSScriptRoot 'fit_check.py') selftest | Out-String
    if ($fitOut -match '"ok": true') { Ok 'Fit engine installed and selftest passed' }
    else { Warn "Fit engine selftest failed. Run: uv run scripts\fit_check.py selftest" }
}

# ------------------------------------------------------------------ 6. Workspace
Step 'Workspace'
if (-not $Workspace) { $Workspace = if ($cfg.workspace) { [string]$cfg.workspace } else { Join-Path $HOME 'Alif3D' } }
$template = Join-Path $RepoRoot 'workspace-template'
New-Item -ItemType Directory -Force $Workspace | Out-Null
$copied = 0
Get-ChildItem $template -Recurse -Force | ForEach-Object {
    $rel = $_.FullName.Substring($template.Length).TrimStart('\')
    $dest = Join-Path $Workspace $rel
    if ($_.PSIsContainer) { New-Item -ItemType Directory -Force $dest | Out-Null }
    elseif ($_.Name -ne '.gitkeep' -and -not (Test-Path $dest)) { Copy-Item $_.FullName $dest; $copied++ }
}
$cfg.workspace = (Resolve-Path $Workspace).Path
Ok "Workspace $($cfg.workspace) ($copied new files)"

# ------------------------------------------------------------------ 7. Fusion add-in (optional)
if ($WithFusion) {
    Step 'Fusion360MCP add-in'
    $addIns = Join-Path $env:APPDATA 'Autodesk\Autodesk Fusion 360\API\AddIns'
    $zip = Join-Path $env:TEMP 'fusion360-mcp-server.zip'
    $ext = Join-Path $env:TEMP 'fusion360-mcp-server'
    Invoke-WebRequest 'https://codeload.github.com/faust-machines/fusion360-mcp-server/zip/refs/heads/main' -OutFile $zip -UseBasicParsing
    Remove-Item $ext -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive $zip $ext -Force
    $addonSrc = Get-ChildItem $ext -Directory | Select-Object -First 1 | ForEach-Object { Join-Path $_.FullName 'addon' }
    if (Test-Path (Join-Path $addonSrc 'Fusion360MCP.py')) {
        $dest = Join-Path $addIns 'Fusion360MCP'
        New-Item -ItemType Directory -Force $dest | Out-Null
        Copy-Item (Join-Path $addonSrc '*') $dest -Recurse -Force
        Ok "Fusion360MCP add-in copied to $dest"
        $Todo.Add('Fusion: Shift+S > Add-Ins > Fusion360MCP > Run (tick Run on Startup). It listens on port 9876.')
    } else { Warn 'Fusion add-in folder not found in the downloaded repo; install it by hand.' }
    $cfg.fusion_addin = $true
}

# ------------------------------------------------------------------ 8. Write config
Step 'local.config.json'
$cfg.blender_mcp_port = $BlenderMcpPort
$cfg.fusion_mcp_port  = $FusionMcpPort
if (-not $cfg.render) { $cfg.render = [ordered]@{ samples = 256; resolution_x = 2160; resolution_y = 2700; denoise = $true } }
Write-Utf8NoBom $ConfigPath ($cfg | ConvertTo-Json -Depth 5)
[Environment]::SetEnvironmentVariable('ALIF3D_CONFIG', $ConfigPath, 'User')
$env:ALIF3D_CONFIG = $ConfigPath
Ok "Wrote $ConfigPath and set ALIF3D_CONFIG for your user"

# ------------------------------------------------------------------ Summary
if ($blender) {
    $Todo.Add("Open Blender once. The MCP server auto-starts on port $BlenderMcpPort (check: N panel > MCP for Blender). Only one MCP client can be connected to Blender at a time.")
}
$Todo.Add("If you ran setup.ps1 directly (not install.ps1), in Claude Code: /plugin marketplace add $RepoRoot   then   /plugin install alifs-3d-agent@alifs-3d-agent")
$Todo.Add('Restart Claude Code (new terminal) so it sees ALIF3D_CONFIG, then run /alifs-3d-agent:studio-doctor')
$Todo.Add("Fill in $RepoRoot\skills\social-poster\brand.md (or copy it to $($cfg.workspace)\brand.md)")

Write-Host "`n================ alifs-3d-agent setup summary ================" -ForegroundColor Cyan
Write-Host 'Done:' -ForegroundColor Green
$Done | ForEach-Object { Write-Host "  [x] $_" }
Write-Host 'Left to do by hand:' -ForegroundColor Yellow
$Todo | ForEach-Object { Write-Host "  [ ] $_" }
