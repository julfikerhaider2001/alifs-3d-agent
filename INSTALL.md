# Installing Alif's 3D Agent (instructions for Claude Code)

The user will say something like *"install github.com/julfikerhaider2001/alifs-3d-agent"*.
Follow these steps in order on their Windows PC. Run PowerShell scripts with
`powershell -NoProfile -ExecutionPolicy Bypass -File <script>`. The scripts never wait for keyboard input.

## 1. Get the repo

- Check the GitHub login first: `gh auth status`. The repo is private.
  If gh isn't logged in, ask the user to run `gh auth login` (GitHub.com → HTTPS → browser) and
  then `gh auth setup-git`. Don't try to log in for them.
- Clone to `%USERPROFILE%\alifs-3d-agent`, unless the user names another folder:
  `gh repo clone julfikerhaider2001/alifs-3d-agent "$HOME\alifs-3d-agent"`
  If the folder already exists and is this repo, run `git -C <folder> pull` instead.

## 2. Check the environment (read-only)

```
powershell -NoProfile -ExecutionPolicy Bypass -File <repo>\scripts\check-env.ps1
```

Show the user a short summary: what's OK, what is `NEED` (will be installed), and any `WARN`.
Then ask the user (one question each, only where it applies):
- **Blender missing** → "Install Blender with winget (~400 MB)?" → `-InstallBlender` or `-NoBlenderInstall`.
- **Fusion 360 installed** → "Also install the Fusion360MCP add-in?" → `-WithFusion`.
- **Another `blender` MCP server configured** → "Remove it so it doesn't fight the plugin for Blender?"
  If yes: `claude mcp remove blender -s <scope>` (only with their OK).
- Workspace folder: default `%USERPROFILE%\Alif3D`. Only ask if they mentioned another place (`-Workspace`).

## 3. Install

```
powershell -NoProfile -ExecutionPolicy Bypass -File <repo>\install.ps1 [-InstallBlender | -NoBlenderInstall] [-WithFusion]
```

Always pass `-InstallBlender` or `-NoBlenderInstall` when Blender is missing. This takes a few minutes
(winget, Playwright Chromium, Blender headless runs); use a long timeout (10 min).
It installs uv, Blender (if allowed), the MCP for Blender addon on port 9877, Playwright Chromium,
detects the GPU backend, creates the workspace, writes `local.config.json`, registers the plugin
(`alifs-3d-agent@alifs-3d-agent`), and finishes with the doctor.

## 4. Report

Tell the user:
- what was installed and what was already there
- the doctor result. **Port 9877 FAIL is expected until Blender is open.**
- what's left for them to do by hand (the "Left to do by hand" list from setup), normally:
  1. Restart Claude Code (so the plugin and `ALIF3D_CONFIG` load).
  2. Open Blender once. The MCP server auto-starts on 9877 (N panel → MCP for Blender).
  3. Fusion only: Shift+S → Add-Ins → Fusion360MCP → Run.
  4. Fill in `skills/social-poster/brand.md`.
- how to use it: `/alifs-3d-agent:shoot <file>` and `/alifs-3d-agent:studio-doctor`.

## If something fails

- `uv` not found right after installing: open a new terminal (PATH refresh) and re-run install.ps1.
- winget missing: the user must install "App Installer" from the Microsoft Store.
- Re-running install.ps1 is always safe; it skips what's done and keeps local.config.json settings.
