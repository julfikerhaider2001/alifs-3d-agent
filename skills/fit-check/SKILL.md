---
name: fit-check
description: Download a 3D model from a link (Printables, Thingiverse, direct file) or a local file, and check it against the AC lamp (E27 holder) and DC lamp (USB puck light) references. Covers physical fit (hole vs shaft clearance), similarity score, a live fit check in Blender (both models placed together, collision test, visual check), and saving the assembled scene for rendering. Use when the user gives a model link or file and asks whether it fits their lamp.
argument-hint: <link or file> [ac|dc|auto]
---

# Fit check

References live in `${CLAUDE_PLUGIN_ROOT}/references/<id>/reference.json`:
- `ac-lamp`: E27 lamp holder with M10 nipple and shade collar. Interfaces `shade_hole` (Ø40 shaft) and `m10_mount` (Ø10).
- `dc-lamp`: ANTOTEN 5V USB puck light. Interfaces `puck_pocket` (Ø70) and `lens_opening` (Ø60).

If a reference has `"status": "provisional"`, its sizes are typical values, not measurements.
Say so in every verdict ("fits the provisional E27 reference").

## 1. Get the model

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/fetch_model.py" "<link or path>" [--name <short-name>]
```

The files land in `<workspace>/input/<name>/`. The last line is JSON with `dir` and `files`.
- Printables and direct file links download directly.
- Thingiverse needs the user's own API token (`thingiverse_token` in local.config.json). If it's
  missing, pass on the script's instructions.
- MakerWorld, Cults3D and other login sites: **don't try to get around their login or bot checks.**
  Ask the user to download the file in their browser and give you the path, then run the same
  command with that path.
- Only G-code or PDF in the download: say so and ask for another file or model.

## 2. Measure and check

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/fit_check.py" check "<dir from step 1>" --name <name> --ref <auto|ac-lamp|dc-lamp|all>
```

Use `--ref ac-lamp` or `--ref dc-lamp` when the user said which lamp; otherwise use `all`.
It writes `<workspace>/fit/<name>/report.md`, `report.json`, and Blender-ready STLs in mm under
`<workspace>/fit/<name>/blender/` (`REF_<id>.stl` plus one per model file).

Reading the result:
- Physical fit verdicts: `fits`, `too tight`, `interference`, `too loose`, `falls through`,
  `no mating feature found`. Clearance is hole Ø minus shaft Ø, in mm.
- Similarity is 0–100: shape (scale-free) blended with overall size. Above about 80 means a similar
  object; below about 50 means unrelated.
- Several files (e.g. a shade plus a base): the mating part is the one with the best interface score.
  The other parts attach to it, so treat them as one assembly.

## 3. Live check in Blender

Run this through the Blender MCP tools (`get_addon_status` first; if Blender isn't connected,
report the step 2 results and say the live check is waiting for Blender).

1. New empty scene: `bpy.ops.wm.read_homefile(use_empty=True)`.
2. Import the reference and the mating part (STLs are in mm, so scale them to metres):

```python
import bpy, bmesh, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
MM = 0.001
def imp(path, name):
    bpy.ops.wm.stl_import(filepath=path, global_scale=MM)
    o = bpy.context.selected_objects[0]; o.name = name; return o
ref  = imp(r"<blender>/REF_<id>.stl", "REF_<id>")
part = imp(r"<blender>/<part>.stl", "PART_<name>")
```

3. Place the part on the reference using `best_interface` from report.json: the `hole` has `axis`,
   `center_3d` (mm), `from` and `to` (mm along that axis), and `seat_z` (mm) is where it sits on
   the reference. The reference axis is world Z through x = y = 0.

```python
def place(part, axis, center_3d, h_from, h_to, seat_z, flip=False):
    rot = {"z": (0, 0, 0), "x": (0, math.radians(90), 0), "y": (math.radians(-90), 0, 0)}[axis]
    part.rotation_euler = rot
    if flip: part.rotation_euler.x += math.pi
    part.location = (0, 0, 0); bpy.context.view_layer.update()
    i = "xyz".index(axis); a = Vector(center_3d); b = Vector(center_3d)
    a[i], b[i] = h_from, h_to
    wa, wb = (part.matrix_world @ (a * MM)), (part.matrix_world @ (b * MM))
    low = wa if wa.z < wb.z else wb
    part.location = Vector((-low.x, -low.y, seat_z * MM - low.z))

def overlaps(a, b):
    dg = bpy.context.evaluated_depsgraph_get(); trees = []
    for o in (a, b):
        bm = bmesh.new(); bm.from_object(o, dg); bm.transform(o.matrix_world)
        trees.append(BVHTree.FromBMesh(bm)); bm.free()
    return len(trees[0].overlap(trees[1]))
```

   Place it, count `overlaps(ref, part)`, then try `flip=True` too. Keep the orientation that
   collides least **and** makes physical sense (a shade opens away from the holder's cap; a pocket
   faces the puck's back). Some overlap where the crude provisional proxy meets the part is normal.
   Judge collisions at the mating feature itself.
4. Use `look` from the front, the side and a cut-away angle (max_size 768). Check concentricity,
   the seat height, and the cable slot (DC). If the numbers and the picture disagree, trust what you
   see and explain why.
5. Add the other parts of a multi-part model in their designed positions (they share the file's
   coordinate frame, so apply the same transform).
6. Save `<workspace>/renders/<name>.blend` (`pack_all()` first).

## 4. Report

Give: the source link and files, the per-reference table from report.md (fit verdict, clearance,
similarity), the live-check result (orientation chosen, collisions at the interface, screenshots
described in one line each), the `.blend` path, and a one-line verdict:
**"Fits the AC lamp (E27 holder) via shade_hole, +1.0 mm clearance."** If a reference is provisional,
end with a reminder to send real measurements.
