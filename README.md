# Alif's 3D Agent

> **Claude Code: if you were asked to install this repo, follow [INSTALL.md](INSTALL.md).**

A Claude Code plugin (with its own private marketplace) that turns a 3D product file into social posters:

1. **Fit check** (`/fit`): paste a model link (Printables, Thingiverse, direct file) or a file. The agent
   downloads it, measures its holes, checks the physical fit and similarity against your **AC lamp** (E27
   holder) and **DC lamp** (USB puck light), and places it on the lamp in Blender to check for collisions.
2. **Render**: Blender, driven through [MCP for Blender](https://github.com/ahujasid/blender-mcp),
   imports your FBX/OBJ, applies Poly Haven PBR materials, an HDRI, a shadow-catcher ground and three
   85mm cameras (hero 3/4, front, detail). It saves `renders/<name>.blend`, then renders headless in
   Cycles on your GPU to 2160px+ PNGs, opaque and transparent.
3. **Poster**: an HTML/CSS poster built from your brand sheet, with English and Bangla text rendered by
   Chromium (Inter, Hind Siliguri, Noto Sans Bengali), exported at 1080×1350 feed, 1080×1920
   story and 1200×630 Facebook.

Windows 10/11. Fusion 360 is optional (its MCP server is included too).

## Install on a new PC

Needs Windows 10/11, Claude Code, and a GitHub login (`gh auth status`; the repo is private).
Everything else (uv, Blender, the Blender addon, Playwright, fonts) is installed for you.

**The easy way:** in Claude Code, say:

> install github.com/julfikerhaider2001/alifs-3d-agent

Claude clones the repo, checks the environment, asks before big installs (Blender, Fusion add-in),
installs the dependencies, and registers the plugin. See [INSTALL.md](INSTALL.md).

**By hand**, in PowerShell:

```powershell
gh repo clone julfikerhaider2001/alifs-3d-agent $HOME\alifs-3d-agent
cd $HOME\alifs-3d-agent
powershell -ExecutionPolicy Bypass -File .\scripts\check-env.ps1   # read-only report
powershell -ExecutionPolicy Bypass -File .\install.ps1              # -InstallBlender, -WithFusion, -Workspace D:\...
```

`install.ps1` runs the check, then `scripts\setup.ps1` (dependencies + `local.config.json`), then adds
the clone as a Claude Code marketplace and installs `alifs-3d-agent@alifs-3d-agent`, then the doctor.
It is safe to re-run. If the Claude Code CLI isn't found, it prints the two `/plugin` commands to type.

Afterwards: restart Claude Code and open Blender once (its MCP server auto-starts on port **9877**).
Because the plugin runs straight from the clone, `git pull` updates it.

### What's in the repo

| Path | What it is |
|---|---|
| `install.ps1` | one-shot installer (check → setup → plugin → doctor) |
| `INSTALL.md` | step-by-step for Claude Code when asked to install |
| `scripts/check-env.ps1` | read-only environment report |
| `scripts/setup.ps1` | dependencies + per-PC `local.config.json` |
| `scripts/doctor.py` | pass/fail health check (also `/alifs-3d-agent:studio-doctor`) |
| `scripts/render.py`, `scripts/export_poster.py` | headless Blender render, HTML → PNG export |
| `scripts/fetch_model.py`, `scripts/fit_check.py` | model download, hole measurement, fit and similarity |
| `references/` | AC lamp (E27 holder) and DC lamp (puck light) reference definitions |
| `skills/`, `agents/`, `.mcp.json` | the plugin: skills, subagents, Blender and Fusion MCP servers |
| `fonts/` | Inter, Hind Siliguri, Noto Sans Bengali (OFL) |
| `workspace-template/` | copied to your workspace (`input/`, `renders/`, `posters/`, `CLAUDE.md`) |

## Daily use

Start Claude Code in your workspace folder, open Blender, then:

```
/alifs-3d-agent:start https://www.printables.com/model/...   # or no link: it asks
/alifs-3d-agent:shoot chair.fbx
/alifs-3d-agent:shoot bottle.fbx interior "নতুন বোতল, এখন পাওয়া যাচ্ছে"
/alifs-3d-agent:fit https://www.printables.com/model/889966-lampshade-for-ikea-holmo-or-any-standard-e27-socke ac
/alifs-3d-agent:fit C:\Users\me\Downloads\puck-holder.3mf dc "নতুন হোল্ডার"
/alifs-3d-agent:studio-doctor
```

`/start` is the main entry. It asks for the product link or file, then your requirements (lamp, printer,
filament and colour, part or kit, quantity, poster language and text), then runs: download and licence
check, fit check, a production PDF (`production/<name>/production.pdf`: material, colour, grams, print time,
cost and selling price in BDT, sliced with Bambu Studio; rates in `pricing.json`), the render, and posters
with the logo, price and buy link, designed to Hallmark's anti-AI-design rules. It ends by adding a log
line and any learnings to `CLAUDE.md` and pushing it to GitHub.

**Always up to date:** a SessionStart hook pulls this repo at the start of every conversation and
updates the installed plugin when `version` in `.claude-plugin/plugin.json` changes.

`/fit` runs the whole chain: download → fit report (`fit/<name>/report.md`) → live Blender check →
render → posters. If the part doesn't fit, it stops and asks before rendering.

- **Where downloads work:** Printables (no login), Thingiverse (add your own API token from
  thingiverse.com/developers to `local.config.json` as `thingiverse_token`), and direct file links.
  MakerWorld and other login-only sites aren't scraped: download the file in your browser and give the path.
- **References:** `references/ac-lamp` and `references/dc-lamp` are **provisional** (typical sizes, because
  the store listings publish none). Measure your parts or add their CAD files; see
  [references/README.md](references/README.md).

Outputs go to `renders/`, `fit/` and `posters/`. Fill in `skills/social-poster/brand.md` once (or put a
`brand.md` in the workspace to override it).

## Update

```powershell
cd $HOME\alifs-3d-agent
git pull
powershell -ExecutionPolicy Bypass -File .\install.ps1   # safe; picks up new dependencies
```

then run `/plugin marketplace update alifs-3d-agent` and `/reload-plugins` in Claude Code.

## Troubleshooting

Run `/alifs-3d-agent:studio-doctor` first. It prints PASS/FAIL with a fix for each failure.

- **Ports**: Blender's MCP server uses **9877**, and the Fusion360MCP add-in uses **9876**. If Blender
  shows 9876 in its N panel, change it to 9877 and use *File → Defaults → Save Startup File*. `.blend`
  files remember their own port, so an old file can bring 9876 back.
- **Blender addon not connected**: open Blender → press **N** in the 3D viewport → *MCP for Blender* →
  *Start MCP Server*. If the addon is missing, re-run install.ps1 or enable *Interface: MCP for Blender*
  under *Edit → Preferences → Add-ons*. Then in Claude Code run `/mcp` → reconnect
  `plugin:alifs-3d-agent:blender`.
- **Only one MCP client connected to Blender at a time**: close other Claude Code, Claude Desktop or
  Cursor sessions using Blender, and remove any older `blender` server you added by hand
  (`claude mcp list` / `claude mcp remove blender`).
- **Fusion server**: it starts even when Fusion is closed, and its tools just time out until you run
  the add-in (Shift+S → Add-Ins → Fusion360MCP → Run). A Fusion failure never blocks Blender.
- **Pinned versions**: `mcp-for-blender==2.1.9` (in `.mcp.json` and `setup.ps1`, so the addon and server
  match) and `playwright==1.64.0` (in `export_poster.py` and `setup.ps1`). Bump them together.
- **Telemetry**: the Blender MCP server runs with `DISABLE_TELEMETRY=true`.

Fonts in `fonts/` are under the SIL Open Font License (see `fonts/licenses/`).
