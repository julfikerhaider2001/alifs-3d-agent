---
name: product-render
description: Set up and render a product shot in Blender from an FBX/OBJ in the workspace input/ folder. Covers import, scale and origin, Poly Haven PBR materials, HDRI lighting (studio or interior), shadow-catcher ground, three 85mm cameras (hero 3/4, front, detail), saving renders/<name>.blend, and a headless Cycles render to 2160px+ PNG plus transparent PNG. Use for any product render, packshot, or "render this model" request.
argument-hint: <file in input/> [studio|interior]
---

# Product render

You drive a live Blender through the Blender MCP tools (`get_addon_status`, `get_scene_info`,
`execute_blender_code`, `search_assets`, `import_asset`, `look`). You set up the scene through MCP,
but the **final render always runs through `scripts/render.py`** (headless Cycles on the GPU from
local.config.json). Never render through MCP.

Inputs: a model file (FBX or OBJ), a mood (`studio` default, or `interior`), and optionally a name.

## 0. Preflight

1. Resolve config and the workspace:
   `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/studio_config.py"` → use `workspace` from the JSON.
   Folders: `<workspace>/input`, `<workspace>/renders`, `<workspace>/posters`.
2. Find the model: the argument as given, else `<workspace>/input/<arg>`. If several files
   match or none, list `input/` and ask.
3. `name` = file stem, lowercased, spaces → `-` (e.g. `Water Bottle v2.fbx` → `water-bottle-v2`).
4. Call `get_addon_status`. If it fails, stop and tell the user: open Blender (the server
   auto-starts on port 9877; N panel → MCP for Blender), make sure no other MCP client is
   connected to it, and run `/alifs-3d-agent:studio-doctor`.

## 1. Clean scene and import

In `execute_blender_code`:
- Start from a new empty scene (`bpy.ops.wm.read_homefile(use_empty=True)` keeps the addon and
  the 9877 port setting; then delete any leftover objects). Set the units to metric.
- Import: `.fbx` → `bpy.ops.import_scene.fbx(filepath=...)`; `.obj` → `bpy.ops.wm.obj_import(filepath=...)`.
- Select the imported meshes and **apply rotation and scale**
  (`bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)`).
- Read the world bounding box. Real products are usually 2 cm to 2 m. Fusion often exports in cm
  or mm, so if the largest dimension is under 0.01 m or over 10 m, rescale by the obvious power of 10
  and apply again. Report the final dimensions.

## 2. Origin at the bottom, product at the world origin

- Several parts: keep them as separate objects (materials stay separate), parent them to an
  empty called `PRODUCT`.
- Put the pivot at the **bottom centre** of the combined bounding box (for one object, set its origin
  there; for several, place the `PRODUCT` empty there), then move it so that point sits at (0, 0, 0).
- Add a Weighted Normal or shade auto smooth if CAD faceting shows.

## 3. PBR materials (Poly Haven)

- Enable Poly Haven on the scene: `bpy.context.scene.blendermcp_use_polyhaven = True`.
- Choose a material per part from its name, what the user said, or by asking if unclear
  (brushed metal, matte plastic, rubber, wood, fabric, glass...).
- `search_assets` for Poly Haven textures, then `import_asset` and assign. CAD meshes rarely have
  good UVs, so for tiled textures use Texture Coordinate (Object) → Mapping → Image Texture with
  **Box** projection (blend about 0.2), scaled to real-world size.
- Glass, chrome and plain plastics don't need textures. Use a Principled BSDF with the right
  roughness, metallic and transmission. Find nodes **by type** (`n.type == "BSDF_PRINCIPLED"`),
  never by name.

## 4. HDRI environment

- `studio` mood: a Poly Haven studio HDRI (`search_assets` "studio"), strength about 1.0, rotated so the
  key light rakes across the hero face.
- `interior` mood: a soft daylight interior HDRI (`search_assets` "interior" or "room").
- Clean opaque background: in the World node tree, mix the HDRI Background with a plain Background
  (light neutral, or the brand background colour from brand.md if known) using
  **Light Path → Is Camera Ray** as the factor. The product stays lit by the HDRI and the camera
  sees a clean colour.

## 5. Ground plane with shadow catcher

- Add a plane at z = 0, about 20× the product footprint, called `GROUND`.
- `GROUND.is_shadow_catcher = True` (Cycles). The transparent render keeps the contact shadow as alpha.

## 6. Cameras: three 85mm shots

Create three cameras with `lens = 85`, `sensor_width = 36`, aimed with a Track To constraint at an
empty `TARGET` placed at the product's bounding-box centre:
- `CAM_hero`: 3/4 view, about 35° around from the front and 15–20° above.
- `CAM_front`: straight on, about 5° above, centred.
- `CAM_detail`: closer, framing the most interesting feature (logo, texture, button, edge).
  Enable depth of field (focus object = `TARGET` or a feature empty, f/2.8–4).

Set the distance so the product fills about 70% of the 4:5 frame
(`distance ≈ (size / 2) / tan(fov / 2) × 1.4`). Use `look` on each camera and adjust framing,
rotation and lighting until it looks like a real catalogue shot. Keep `look` images small (`max_size` 768).

## 7. Save

- `bpy.ops.file.pack_all()` so Poly Haven textures and HDRIs travel with the file. This is
  required, because the headless render can't see Blender's temp downloads.
- `bpy.ops.wm.save_as_mainfile(filepath="<workspace>/renders/<name>.blend")`.

## 8. Final render (headless, never MCP)

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" "<workspace>/renders/<name>.blend"
```

It renders every `CAM_*` at the configured resolution (default 2160×2700) with Cycles on the
configured GPU backend and writes, for each angle:
`renders/<name>_<angle>.png` and `renders/<name>_<angle>_transparent.png`.
Options: `--samples N`, `--res 2160x2160`, `--cameras CAM_hero`. A test or quick preview may use
lower samples. Never go below 2160 px on the long side for final output.

The last line is JSON; if `ok` is false, read the error, fix the scene, save, and render again.

## 9. Report

Return the `.blend` path and every PNG path (opaque and transparent per angle), the mood or HDRI used,
the materials per part, and the final dimensions.
