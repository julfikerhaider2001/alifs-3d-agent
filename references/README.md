# Lamp references

`/alifs-3d-agent:fit` checks downloaded models against these two products:

| Folder | Product | Mating interfaces |
|---|---|---|
| `ac-lamp/` | ES E27 lamp holder, M10 nipple, shade collar ([listing](https://www.daraz.com.bd/products/1pcs-es-e27-m10-light-bulb-lamp-holder-lampshade-collar-lighting-pendant-socket-screw-2-colors-i1581146309-s12671081540.html)) | `shade_hole` over the Ø40 body, `m10_mount` for the Ø10 nipple |
| `dc-lamp/` | ANTOTEN 5V USB LED puck light ([listing](https://www.amazon.com/dp/B09R18WZ25)) | `puck_pocket` around the Ø70 body, `lens_opening` for the Ø60 lens |

Both are **provisional** right now: the listings publish no dimensions, so the sizes are typical values.
Verdicts say "provisional" until you replace them.

## Make a reference exact

Either way, edit `reference.json` in the lamp's folder and set `"status": "measured"`.

**Option A: measurements.** Measure the items in `measure_me` with calipers, then update:
- `proxy`: the simple shape used for the similarity score and the Blender live check (mm, Z up).
- `interfaces[].shaft_d`: the diameter a mating hole goes over.
- `interfaces[].clearance`: the acceptable hole-minus-shaft gap in mm. About 0.3–2.0 for a slip fit on
  FDM prints; tighten it for press fits.
- `interfaces[].seat_z`: the height where the mating part sits.

**Option B: a real model.** Put the CAD export (STEP preferred, or STL/3MF) in the folder and set
`"model": "<file name>"`. It replaces the proxy shape; keep `interfaces` up to date. The model must
be in mm, with its round axis along Z through x = y = 0, oriented as `orientation` says.

Check your edit: `uv run scripts/fit_check.py refs`.
