# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Check the whole alifs-3d-agent setup on this PC and print PASS/FAIL with a fix for each failure.

  uv run scripts/doctor.py            # full check, exit code 1 if anything FAILs
  uv run scripts/doctor.py --json     # same, machine-readable

Inside Blender (`blender -b --python doctor.py -- --probe`) this file prints one line
`RS_PROBE {json}` with the Blender version, addon state, startup-scene port and the
GPU devices Cycles can see. scripts/setup.ps1 uses that probe for GPU detection.
"""
from __future__ import annotations

import json
import sys

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

PROBE_MARKER = "RS_PROBE "
GPU_ORDER = ("OPTIX", "CUDA", "HIP")


# ---------------------------------------------------------------- inside Blender
def _probe() -> None:
    import addon_utils
    import bpy

    out = {"blender_version": bpy.app.version_string}
    out["addon_installed"] = any(m.__name__ == "blender_mcp" for m in addon_utils.modules())
    out["addon_enabled"] = "blender_mcp" in bpy.context.preferences.addons
    out["startup_port"] = getattr(bpy.context.scene, "blendermcp_port", None)

    gpus = {}
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for backend in GPU_ORDER:
            try:
                devs = prefs.get_devices_for_type(backend)
            except (TypeError, ValueError, AttributeError):
                continue
            names = [d.name for d in devs if d.type == backend]
            if names:
                gpus[backend] = names
    except KeyError:
        pass
    out["gpus"] = gpus
    out["best_backend"] = next((b for b in GPU_ORDER if b in gpus), "CPU")
    print(PROBE_MARKER + json.dumps(out), flush=True)


# --------------------------------------------------------------- outside Blender
def run_probe(blender: str, timeout: int = 180) -> dict:
    import subprocess
    from pathlib import Path

    cmd = [blender, "-b", "--python-exit-code", "1",
           "--python", str(Path(__file__).resolve()), "--", "--probe"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=timeout)
    for line in res.stdout.splitlines():
        if line.startswith(PROBE_MARKER):
            return json.loads(line[len(PROBE_MARKER):])
    raise RuntimeError((res.stdout + res.stderr).strip()[-600:] or f"exit code {res.returncode}")


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def main() -> int:
    import os
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    from studio_config import BLENDER_MCP_PORT, FONTS_DIR, REPO_ROOT, ConfigError, load_config

    as_json = "--json" in sys.argv
    results: list[dict] = []

    def check(name, status, detail="", fix=""):
        results.append({"check": name, "status": status, "detail": detail, "fix": fix})

    setup_fix = "Run: powershell -ExecutionPolicy Bypass -File <repo>\\scripts\\setup.ps1"

    # 1. uv
    uv = shutil.which("uv")
    check("uv installed", "PASS" if uv else "FAIL", uv or "not on PATH",
          "" if uv else "winget install --id astral-sh.uv -e, then open a new terminal")

    # 2. config
    cfg = None
    try:
        cfg = load_config()
        check("local.config.json", "PASS", cfg["_path"])
    except ConfigError as e:
        check("local.config.json", "FAIL", str(e), setup_fix)

    # 3. Blender + probe
    probe = None
    blender = (cfg or {}).get("blender_path")
    if blender and Path(blender).is_file():
        check("Blender path", "PASS", blender)
        try:
            probe = run_probe(blender)
            check("Blender runs headless", "PASS", f"Blender {probe['blender_version']}")
        except Exception as e:  # noqa: BLE001 - report anything Blender throws
            check("Blender runs headless", "FAIL", str(e)[:300],
                  "Reinstall Blender (winget install BlenderFoundation.Blender) and re-run setup.ps1")
    else:
        check("Blender path", "FAIL", f"not found: {blender!r}",
              "Install Blender (winget install BlenderFoundation.Blender), then re-run setup.ps1")

    if probe:
        if probe["addon_enabled"]:
            check("Blender MCP addon enabled", "PASS", "blender_mcp")
        else:
            check("Blender MCP addon enabled", "FAIL",
                  "installed but disabled" if probe["addon_installed"] else "not installed",
                  "Re-run setup.ps1, or Blender > Edit > Preferences > Add-ons > enable 'MCP for Blender'")
        port = probe.get("startup_port")
        if port == BLENDER_MCP_PORT:
            check("Addon port in startup file", "PASS", str(port))
        else:
            check("Addon port in startup file", "FAIL", f"{port} (expected {BLENDER_MCP_PORT})",
                  f"In Blender: N panel > MCP for Blender > Port {BLENDER_MCP_PORT}, then File > Defaults > Save Startup File")

    # 4. live port
    if port_open(BLENDER_MCP_PORT):
        check(f"Port {BLENDER_MCP_PORT} reachable", "PASS", "Blender MCP server is listening")
    else:
        check(f"Port {BLENDER_MCP_PORT} reachable", "FAIL", "nothing listening",
              f"Open Blender (the server auto-starts), or N panel > MCP for Blender > Start MCP Server on port {BLENDER_MCP_PORT}")
    fusion_port = (cfg or {}).get("fusion_mcp_port", 9876)
    check(f"Port {fusion_port} (Fusion add-in)", "INFO",
          "listening" if port_open(fusion_port) else "not listening (fine unless you use Fusion tools)")

    # 5. GPU backend
    configured = ((cfg or {}).get("gpu_backend") or "").upper()
    if not configured:
        check("GPU backend", "FAIL", "not set in local.config.json", setup_fix)
    elif probe:
        best = probe["best_backend"]
        devs = ", ".join(probe["gpus"].get(best, [])) or "CPU only"
        if configured == best:
            check("GPU backend", "PASS", f"{configured} ({devs})")
        else:
            check("GPU backend", "FAIL", f"config says {configured}, Blender detects {best} ({devs})",
                  "Re-run setup.ps1 to re-detect, or update GPU drivers")
    else:
        check("GPU backend", "WARN", f"config says {configured}; could not verify without Blender")

    # 6. fonts
    expected = ["Inter-Variable.ttf", "NotoSansBengali-Variable.ttf", "HindSiliguri-Regular.ttf",
                "HindSiliguri-Medium.ttf", "HindSiliguri-SemiBold.ttf", "HindSiliguri-Bold.ttf"]
    missing = [f for f in expected if not (FONTS_DIR / f).is_file()]
    check("Fonts", "FAIL" if missing else "PASS",
          f"missing {missing}" if missing else f"{len(expected)} files in {FONTS_DIR}",
          "git pull / re-clone the repo; fonts/ is committed" if missing else "")

    # 7. Playwright: export a real Bangla test poster through the production exporter
    if uv and not missing:
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "doctor.html"
            html.write_text(
                "<!doctype html><html lang='bn'><meta charset='utf-8'>"
                "<body style='margin:0;background:#fff;font:700 64px \"Hind Siliguri\"'>"
                "<p style='padding:40px'>বাংলা পরীক্ষা <span style='font-family:Inter'>Test</span></p>",
                encoding="utf-8")
            res = subprocess.run(
                [uv, "run", "--quiet", str(REPO_ROOT / "scripts" / "export_poster.py"), str(html),
                 "--name", "doctor", "--sizes", "facebook", "--out", tmp],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            png = Path(tmp) / "doctor_facebook.png"
            if res.returncode == 0 and png.is_file() and png.stat().st_size > 1000:
                check("Playwright poster export", "PASS", "Chromium rendered a Bangla test poster")
            else:
                tail = (res.stdout + res.stderr).strip().splitlines()[-1:] or ["no output"]
                check("Playwright poster export", "FAIL", tail[0][:300],
                      "Run: uvx --from playwright==1.64.0 playwright install chromium")
    else:
        check("Playwright poster export", "FAIL", "skipped (uv or fonts missing)", "Fix the checks above first")

    # 8. workspace
    ws = (cfg or {}).get("workspace")
    if ws and all((Path(ws) / d).is_dir() for d in ("input", "renders", "posters")):
        check("Workspace", "PASS", ws)
    else:
        check("Workspace", "FAIL", f"{ws!r} missing or incomplete", setup_fix)

    # 9. Fusion add-in (optional)
    appdata = os.environ.get("APPDATA", "")
    addin = Path(appdata) / "Autodesk" / "Autodesk Fusion 360" / "API" / "AddIns" / "Fusion360MCP"
    check("Fusion360MCP add-in (optional)", "INFO",
          "installed" if (addin / "Fusion360MCP.py").is_file() else "not installed (setup.ps1 -WithFusion)")

    failed = [r for r in results if r["status"] == "FAIL"]
    if as_json:
        print(json.dumps({"ok": not failed, "results": results}, indent=2))
    else:
        for r in results:
            print(f"[{r['status']:4}] {r['check']}: {r['detail']}")
            if r["status"] == "FAIL" and r["fix"]:
                print(f"         fix: {r['fix']}")
        print()
        print(f"{len(results) - len(failed)} ok, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    if IN_BLENDER:
        _probe()
    else:
        sys.exit(main())
