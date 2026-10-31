---
name: shoot
description: Full pipeline. Render a product model from input/ in Blender, then make feed, story and Facebook posters from the render. Delegates to the render-artist and poster-designer agents.
argument-hint: <file> [studio|interior] ["poster text"]
disable-model-invocation: true
---

# /shoot

Arguments: `$ARGUMENTS`

Parse them as `<file> [mood] [poster text]`:
- `file`: the model, a name in `<workspace>/input/` or a full path (required; if missing, list
  `input/` and ask which one).
- `mood`: `studio` (default) or `interior`. If the second argument is neither, treat it as poster text.
- `poster text`: everything else (quoted text may be Bangla). Optional.

## Steps

1. `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/studio_config.py"` → workspace. Confirm the model file exists.
   Work out `name` the same way the product-render skill does (lowercase file stem, spaces → `-`).
2. **Render.** Delegate to the `alifs-3d-agent:render-artist` agent and wait for it (foreground; the
   poster depends on it). Give it: absolute model path, mood, name, workspace.
   It must return the `.blend` path and the PNG paths. If it reports that Blender isn't connected or
   the render failed, stop and show the user its message plus "run /alifs-3d-agent:studio-doctor".
3. Check the files it reported exist (`<name>_hero_transparent.png` at least).
4. **Poster.** Delegate to the `alifs-3d-agent:poster-designer` agent and wait for it. Give it: the hero
   transparent PNG (plus the other angles as alternates), the poster text exactly as the user wrote it,
   name, workspace.
5. Check the three poster PNGs exist.

## Final report

End with a short table of every output path:

| Output | Path |
|---|---|
| Blender scene | renders/<name>.blend |
| Renders | renders/<name>_hero.png, _front, _detail (+ _transparent) |
| Posters | posters/<name>_feed.png, _story.png, _facebook.png |

Use the real absolute paths. Add one line on anything the agents flagged (e.g. brand.md still has TODOs).
