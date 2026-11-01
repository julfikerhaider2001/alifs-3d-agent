# SessionStart hook: keep this PC's alifs-3d-agent in step with GitHub.
#  1. pull the clone (fast-forward only, local edits stashed and restored),
#  2. push commits a previous session made but could not push,
#  3. when the clone's plugin version differs from the installed copy, update the installed plugin
#     (takes effect in the next session or after /reload-plugins),
#  4. print a short note, which Claude Code adds to the conversation's context.
# It never blocks the session: every failure is reported in the note and the script exits 0.
$ErrorActionPreference = 'SilentlyContinue'
$clone = if ($env:ALIF3D_CONFIG) { Split-Path $env:ALIF3D_CONFIG } else { Join-Path $HOME 'alifs-3d-agent' }
if (-not (Test-Path (Join-Path $clone '.git'))) { exit 0 }

$status = @()
$before = git -C $clone rev-parse --short HEAD
git -C $clone pull --ff-only --autostash --quiet 2>$null
if ($LASTEXITCODE -ne 0) { $status += 'pull failed (offline, or local commits diverged)' }
$after = git -C $clone rev-parse --short HEAD
if ($before -ne $after) { $status += "pulled $before..$after" }

$ahead = git -C $clone rev-list --count '@{u}..HEAD' 2>$null
if ([int]$ahead -gt 0) {
    git -C $clone push --quiet 2>$null
    $status += if ($LASTEXITCODE -eq 0) { "pushed $ahead local commit(s)" } else { "$ahead commit(s) not pushed yet" }
}

$want = (Get-Content (Join-Path $clone '.claude-plugin\plugin.json') -Raw | ConvertFrom-Json).version
$have = if ($env:CLAUDE_PLUGIN_ROOT) { Split-Path $env:CLAUDE_PLUGIN_ROOT -Leaf } else { $want }
if ($want -ne $have -and (Get-Command claude -ErrorAction SilentlyContinue)) {
    claude plugin marketplace update alifs-3d-agent *> $null
    claude plugin update alifs-3d-agent@alifs-3d-agent --scope user *> $null
    $status += if ($LASTEXITCODE -eq 0) { "plugin updated $have -> $want (restart Claude Code or /reload-plugins to use it)" } else { "plugin update to $want failed: run  claude plugin update alifs-3d-agent@alifs-3d-agent" }
}

$state = if ($status) { $status -join '; ' } else { 'up to date' }
Write-Output "alifs-3d-agent: synced with GitHub at $after ($state). Before using any alifs-3d-agent skill, read $clone\CLAUDE.md; after a run, add the log line and any learnings there, then commit and push the clone."
exit 0
