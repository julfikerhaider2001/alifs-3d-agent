# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Headless Cycles render of a saved .blend.

Outside Blender (normal use):
  uv run scripts/render.py <file.blend> [--out DIR] [--name NAME]
                           [--samples N] [--res 2160x2700] [--cameras CAM_hero,CAM_front]

  Reads blender_path, gpu_backend and render defaults from local.config.json, then
  re-launches itself inside `blender -b`. For every camera named CAM_* (or the scene
  camera if there are none) it writes two PNGs:
      <out>/<name>_<angle>.png              opaque
      <out>/<name>_<angle>_transparent.png  transparent film (shadow catcher keeps shadows)
  The last stdout line is JSON: {"ok": true, "files": [...]}.

Inside Blender this file is the render job itself; it never saves the .blend.
"""
from __future__ import annotations

import json
import sys

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

MARKER = "RS_RENDERED "


# ---------------------------------------------------------------- inside Blender
def _enable_device(backend: str) -> str:
    import bpy

    scene = bpy.context.scene
    if backend in ("OPTIX", "CUDA", "HIP"):
        prefs = bpy.context.preferences.addons["cycles"].preferences
        try:
            prefs.compute_device_type = backend
            devices = prefs.get_devices_for_type(backend)
            gpus = [d for d in devices if d.type == backend]
            for d in prefs.devices:
                d.use = d.type == backend
            if gpus:
                scene.cycles.device = "GPU"
                return f"GPU {backend}: " + ", ".join(d.name for d in gpus)
        except (TypeError, AttributeError, KeyError) as e:
            print(f"render.py: {backend} unavailable ({e}); falling back to CPU")
    scene.cycles.device = "CPU"
    return "CPU"


def _render_in_blender(job: dict) -> None:
    import os
    import bpy

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    print("render.py device:", _enable_device(job["gpu_backend"]))

    scene.cycles.samples = int(job["samples"])
    scene.cycles.use_denoising = bool(job["denoise"])
    scene.render.resolution_x = int(job["res_x"])
    scene.render.resolution_y = int(job["res_y"])
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "8"

    cams = [o for o in scene.objects if o.type == "CAMERA" and o.name.startswith("CAM_")]
    if job.get("cameras"):
        wanted = set(job["cameras"])
        cams = [o for o in scene.objects if o.type == "CAMERA" and o.name in wanted]
    if not cams:
        if scene.camera is None:
            raise SystemExit("render.py: no CAM_* cameras and no scene camera in this .blend")
        cams = [scene.camera]
    cams.sort(key=lambda o: o.name)

    os.makedirs(job["out"], exist_ok=True)
    for cam in cams:
        angle = cam.name[4:].lower() if cam.name.startswith("CAM_") else cam.name.lower()
        scene.camera = cam
        for transparent in (False, True):
            scene.render.film_transparent = transparent
            scene.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
            suffix = "_transparent" if transparent else ""
            path = os.path.join(job["out"], f"{job['name']}_{angle}{suffix}.png")
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            print(MARKER + path, flush=True)


# --------------------------------------------------------------- outside Blender
def _main() -> int:
    import argparse
    import subprocess
    from pathlib import Path

    from studio_config import ConfigError, load_config

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("blend")
    ap.add_argument("--out", help="output folder (default: folder of the .blend)")
    ap.add_argument("--name", help="file name prefix (default: .blend stem)")
    ap.add_argument("--samples", type=int)
    ap.add_argument("--res", help="WIDTHxHEIGHT, e.g. 2160x2700")
    ap.add_argument("--cameras", help="comma-separated camera names (default: all CAM_*)")
    ap.add_argument("--config")
    a = ap.parse_args()

    try:
        cfg = load_config(a.config)
    except ConfigError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1

    blend = Path(a.blend).resolve()
    blender = cfg.get("blender_path")
    if not blend.is_file():
        print(json.dumps({"ok": False, "error": f"no such .blend: {blend}"}))
        return 1
    if not blender or not Path(blender).is_file():
        print(json.dumps({"ok": False, "error": f"Blender not found at {blender!r}; re-run setup.ps1"}))
        return 1

    r = cfg.get("render", {})
    res_x, res_y = r.get("resolution_x", 2160), r.get("resolution_y", 2700)
    if a.res:
        res_x, res_y = (int(v) for v in a.res.lower().split("x"))
    if max(res_x, res_y) < 2160:
        print(f"render.py: warning: {res_x}x{res_y} is below the 2160px target")

    job = {
        "out": str(Path(a.out).resolve() if a.out else blend.parent),
        "name": a.name or blend.stem,
        "gpu_backend": (cfg.get("gpu_backend") or "CPU").upper(),
        "samples": a.samples or r.get("samples", 256),
        "denoise": r.get("denoise", True),
        "res_x": res_x,
        "res_y": res_y,
        "cameras": [c.strip() for c in a.cameras.split(",")] if a.cameras else None,
    }
    cmd = [blender, "-b", str(blend), "--python-exit-code", "1",
           "--python", str(Path(__file__).resolve()), "--", json.dumps(job)]
    print("render.py:", " ".join(cmd[:3]), "...", flush=True)

    files = []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    for line in proc.stdout:
        if line.startswith(MARKER):
            files.append(line[len(MARKER):].strip())
        elif "Error" in line or "render.py" in line or "Saved:" in line:
            print(line.rstrip(), flush=True)
    code = proc.wait()

    missing = [f for f in files if not Path(f).is_file()]
    ok = code == 0 and files and not missing
    print(json.dumps({"ok": bool(ok), "exit_code": code, "files": files, "missing": missing}))
    return 0 if ok else 1


if __name__ == "__main__":
    if IN_BLENDER:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
        _render_in_blender(json.loads(argv[0]))
    else:
        sys.exit(_main())
