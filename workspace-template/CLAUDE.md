# Alif's 3D Agent workspace

This folder is a alifs-3d-agent workspace (created by `scripts/setup.ps1` in the alifs-3d-agent repo).

## Folders
- `input/`: drop product models here (FBX or OBJ, e.g. exported from Fusion 360: File → Export → FBX).
- `renders/`: `<name>.blend` scenes and rendered PNGs (`<name>_<angle>.png` + `_transparent.png`).
- `posters/`: poster HTML sources and PNGs (`<name>_feed.png`, `_story.png`, `_facebook.png`).
- `fit/`: fit-check reports (`fit/<name>/report.md`) and Blender-ready STLs.
- `brand.md` (optional): per-workspace brand sheet; overrides the plugin's `skills/social-poster/brand.md`.

## Commands
- `/alifs-3d-agent:shoot <file> [studio|interior] ["poster text"]`: render and make posters.
- `/alifs-3d-agent:fit <link or file> [ac|dc] ["poster text"]`: download a model, check it fits the AC/DC lamp, render it on the lamp, make posters.
- `/alifs-3d-agent:studio-doctor`: check the setup when something fails.

## Rules
- Blender must be open with the MCP for Blender server on port **9877** (Fusion's add-in uses 9876).
- Only one MCP client can be connected to Blender at a time.
- Final renders run headless through `scripts/render.py`, never through MCP.
- Poster text, especially Bangla, is rendered by the browser (Playwright), never by Pillow.
- Don't delete or overwrite files in `input/`.
- Never get around a website's login or bot checks to download a model; ask the user for the downloaded file instead.
