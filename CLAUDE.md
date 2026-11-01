# Alif's 3D Agent: notes

The agent's memory. It lives in the GitHub repo, so every PC shares it: the plugin's SessionStart hook
pulls the repo at the start of each conversation, and `/alifs-3d-agent:start` appends to this file and
pushes at the end of each run. Read it before using any alifs-3d-agent skill.

## Rules

- Main entry: `/alifs-3d-agent:start [link or file]`. It interviews the user, then runs download →
  licence → fit → production PDF → render → posters → these notes.
- Never script a download from a login site (MakerWorld, Cults3D). Open the page in the user's browser
  and watch `~/Downloads`; the public MakerWorld design API is fine for metadata.
- Selling prints of someone else's design needs a licence that allows it. Say so before adding a price.
- Posters follow Hallmark (`~/.claude/skills/hallmark`) and brand.md; run sloplint before export.
- Changing skills, agents, scripts or pricing.json: bump `version` in `.claude-plugin/plugin.json` in
  the same commit. Installed copies only update when the version changes.

## Learnings

- **Blender 5.2 STL import**: `wm.stl_import(global_scale=0.001)` puts 0.001 in the object's scale
  and leaves the mesh in mm. Apply the scale (`transform_apply(scale=True)`) before placing parts.
- **Transparent renders**: the shadow catcher leaves a faint dark rectangle in `_transparent.png`.
  Posters use the opaque `_hero.png` full-bleed instead.
- **Cycles on the GT 1030**: six 2160×2700 frames at 128 samples took about 55 minutes.
- **Bambu Studio CLI**: system profiles inherit from each other and the CLI crashes (0xC0000005)
  unless they are flattened first; `production.py` does that. Bash on Windows mangles its paths, so
  call it from Python or PowerShell.
- **Hallmark on Windows**: clone with `git -c core.autocrlf=false`, or install.mjs rejects the theme
  files (CRLF pushes them over 8 KB) and the SKILL.md frontmatter.
- **Taka sign**: ৳ is a Bengali character. Set it in Hind Siliguri with `lang="bn"`, or the poster
  exporter fails its Bangla check.
- **Logos**: the brand PDF's logo images have an opaque black box, not transparency. The keyed PNGs
  in `brand/` are the ones to use.

## Log

- 2026-11-01: ISSAY pendant lamp, Rumbles series (MakerWorld 466600, mmera, personal-use licence).
  AC lamp: fits the provisional E27 reference, +0.1 mm (snug). A1 + PLA Matte bone white: 84 g,
  6 h 37 min (MakerWorld profile: 81 g, 6 h 02 min). Cost ৳448, suggested ৳630.
