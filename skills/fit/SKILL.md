---
name: fit
description: Full pipeline from a model link. Download the model, check that it fits the AC or DC lamp (physical fit plus similarity), do a live fit check in Blender, render the assembly, and make on-brand posters. Delegates to the fit-inspector, render-artist and poster-designer agents.
argument-hint: <link or file> [ac|dc|auto] ["poster text"]
disable-model-invocation: true
---

# /fit

Arguments: `$ARGUMENTS`

Parse them as `<link or file> [lamp] [poster text]`:
- link or file: Printables, Thingiverse, a direct file link, or a local path (required).
- lamp: `ac` → `ac-lamp`, `dc` → `dc-lamp`, otherwise `auto` (check both). If the second argument
  is neither `ac`, `dc` nor `auto`, treat it as poster text.
- poster text: the rest, used exactly as written (may be Bangla). Optional.

`name` = a short slug from the model title (the fetch step picks it; reuse it everywhere).

## Steps

1. **Fit check.** Delegate to the `alifs-3d-agent:fit-inspector` agent and wait. Give it: the link or
   path, the lamp choice, and the workspace (`uv run "${CLAUDE_PLUGIN_ROOT}/scripts/studio_config.py"`).
   It returns the fit report path, the verdict per reference, similarity scores, the live-check
   result, and `renders/<name>.blend` with the part placed on the lamp.
   - If the download needs a browser login (MakerWorld etc.), it asks for the file. Pass the
     question to the user, then continue with the file they give.
2. **Gate.** If the verdict is not `fits` for the chosen lamp, show the report and ask the user whether
   to continue to render and posters anyway. Stop if they say no.
3. **Render.** Delegate to `alifs-3d-agent:render-artist` and wait. Give it the existing
   `renders/<name>.blend` (an assembly: don't re-import or re-centre). Ask for materials that make
   both parts read clearly (the printed part in its likely filament look, the lamp part realistic),
   the `studio` mood unless the user asked otherwise, and the three cameras framed on the assembly,
   with the detail camera on the mating interface.
4. **Posters.** Delegate to `alifs-3d-agent:poster-designer` and wait. Give it the hero transparent
   render, the poster text (if none, a short headline about the product; don't claim compatibility
   unless the fit verdict is `fits` with a non-provisional reference), and the name. It follows brand.md.

## Final report

| Step | Result |
|---|---|
| Source | link, downloaded files |
| Fit | verdict per lamp, clearance, similarity, live-check summary (note if provisional) |
| Blender scene | renders/<name>.blend |
| Renders | renders/<name>_hero/front/detail (+ _transparent) |
| Posters | posters/<name>_feed / _story / _facebook.png |

Use real absolute paths, then one line on anything that needs the user (measurements, brand.md TODOs).
