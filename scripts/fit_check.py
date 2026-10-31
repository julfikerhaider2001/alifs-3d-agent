# /// script
# requires-python = ">=3.10"
# dependencies = ["trimesh==4.8.3", "numpy", "scipy", "networkx", "lxml", "shapely", "rtree", "manifold3d", "cascadio"]
# ///
"""Measure a downloaded 3D model and check it against the AC / DC lamp references.

  uv run scripts/fit_check.py check <model files or folder> --name NAME [--ref auto|ac-lamp|dc-lamp|all] [--out DIR]
  uv run scripts/fit_check.py measure <model file>
  uv run scripts/fit_check.py refs           # build/refresh reference meshes, list their status
  uv run scripts/fit_check.py selftest

check writes <out>/report.md, <out>/report.json and Blender-ready STLs in mm
(<out>/blender/*.stl; import in Blender with global_scale=0.001). Default out:
<workspace>/fit/<NAME>. The last stdout line is a JSON summary.

Physical fit: the model is sliced along X, Y and Z; round holes and pegs are fitted with circles.
Each reference interface (references/<id>/reference.json) names a shaft diameter and the clearance a
mating hole needs. The closest hole decides: fits / too tight / interference / too loose / falls through.

Similarity: D2 shape-distribution match (scale-free) blended with bounding-size match, 0-100.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

from studio_config import REPO_ROOT, ConfigError, load_config, workspace

REF_DIR = REPO_ROOT / "references"
MESH_EXT = {".stl", ".3mf", ".obj", ".step", ".stp", ".glb", ".gltf", ".ply", ".off"}
AXES = "xyz"


# ------------------------------------------------------------------ loading
def load_mesh(path: Path) -> tuple[trimesh.Trimesh, list[str]]:
    notes = []
    mesh = trimesh.load(str(path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"no mesh geometry in {path.name}")
    ext = path.suffix.lower()
    biggest = float(mesh.extents.max())
    # STEP comes through cascadio in metres; OBJ/GLB/PLY have no units, tiny means metres.
    if (ext in (".step", ".stp") and biggest < 5) or (ext in (".obj", ".glb", ".gltf", ".ply") and biggest < 2):
        mesh.apply_scale(1000.0)
        notes.append("loaded in metres; converted to mm")
    if not mesh.is_watertight:
        notes.append("mesh is not watertight; hole detection may be less reliable")
    return mesh, notes


def model_files(inputs: list[str]) -> list[Path]:
    files = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in MESH_EXT)
        elif p.suffix.lower() in MESH_EXT:
            files.append(p)
    return files


# ------------------------------------------------------------------ features
def fit_circle(pts: np.ndarray) -> tuple[float, float, float, float]:
    x, y = pts[:, 0], pts[:, 1]
    a = np.c_[2 * x, 2 * y, np.ones(len(x))]
    (cx, cy, c), *_ = np.linalg.lstsq(a, x**2 + y**2, rcond=None)
    r = float(np.sqrt(max(c + cx**2 + cy**2, 0)))
    err = float(np.abs(np.hypot(x - cx, y - cy) - r).max())
    return float(cx), float(cy), r, err


def section_rings(path) -> list[tuple[str, np.ndarray]]:
    """Closed outlines of one slice, each tagged 'boss' (outer) or 'hole' (inner)."""
    try:
        rings = []
        for poly in path.polygons_full:
            rings.append(("boss", np.asarray(poly.exterior.coords)))
            rings += [("hole", np.asarray(r.coords)) for r in poly.interiors]
        return rings
    except ValueError:
        # Overlapping shells (common in downloaded STLs) break polygon repair. Fall back to raw
        # loops: a loop nested inside an odd number of other loops is a hole.
        from shapely.geometry import Point, Polygon

        loops = [np.asarray(d) for d in path.discrete if len(d) >= 4]
        polys = [Polygon(l) for l in loops]
        rings = []
        for i, loop in enumerate(loops):
            inside = Point(loop.mean(axis=0)) if not polys[i].is_valid else polys[i].representative_point()
            depth = sum(1 for j, p in enumerate(polys) if j != i and p.is_valid and p.area > polys[i].area and p.contains(inside))
            rings.append(("hole" if depth % 2 else "boss", loop))
        return rings


def circular_features(mesh: trimesh.Trimesh, slices: int = 80) -> list[dict]:
    """Round holes and pegs, found by slicing along each axis."""
    raw = []
    for ai, axis in enumerate(AXES):
        lo, hi = mesh.bounds[:, ai]
        span = hi - lo
        if span < 0.5:
            continue
        step = span / slices
        heights = np.linspace(lo + step / 2, hi - step / 2, slices)
        sections = mesh.section_multiplane(plane_origin=np.zeros(3), plane_normal=np.eye(3)[ai], heights=heights)
        for h, path in zip(heights, sections):
            if path is None:
                continue
            to_3d = path.metadata.get("to_3D") if path.metadata else None
            for kind, pts in section_rings(path):
                if len(pts) < 10:
                    continue
                cx, cy, r, err = fit_circle(pts)
                if r < 1.0 or err > max(0.04 * r, 0.25):
                    continue
                c3 = (np.asarray(to_3d) @ [cx, cy, 0, 1])[:3] if to_3d is not None else [np.nan] * 3
                raw.append((axis, kind, 2 * r, cx, cy, float(h), step, c3))
    groups: dict[tuple, list] = {}
    for axis, kind, d, cx, cy, h, step, c3 in raw:
        key = (axis, kind, round(d / 0.4), round(cx / 2), round(cy / 2))
        groups.setdefault(key, []).append((d, cx, cy, h, step, c3))
    feats = []
    for (axis, kind, *_), items in groups.items():
        ds = np.array([i[0] for i in items])
        hs = np.array([i[3] for i in items])
        step = items[0][4]
        # World-space centre of the circle, mid-way along its length (mm), for placing parts in Blender.
        c3 = np.nanmedian(np.array([i[5] for i in items], dtype=float), axis=0)
        c3[AXES.index(axis)] = (hs.min() + hs.max()) / 2
        feats.append({
            "axis": axis, "kind": kind,
            "d": round(float(np.median(ds)), 2),
            "center_2d": [round(float(np.median([i[1] for i in items])), 2),
                          round(float(np.median([i[2] for i in items])), 2)],
            "from": round(float(hs.min() - step / 2), 2), "to": round(float(hs.max() + step / 2), 2),
            "length": round(float(hs.max() - hs.min() + step), 2),
            "center_3d": [round(float(v), 2) for v in c3],
        })
    feats.sort(key=lambda f: (-f["length"], -f["d"]))
    return feats


def summary(mesh: trimesh.Trimesh) -> dict:
    return {
        "extents_mm": [round(float(v), 2) for v in mesh.extents],
        "volume_cm3": round(float(abs(mesh.volume)) / 1000, 2) if mesh.is_volume else None,
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
    }


# ------------------------------------------------------------------ references
def build_proxy(parts: list[dict]) -> trimesh.Trimesh:
    meshes = []
    for p in parts:
        if p["shape"] in ("tube", "cylinder"):
            z0, z1 = p["z"]
            h = z1 - z0
            if p["shape"] == "tube":
                m = trimesh.creation.annulus(r_min=p["id"] / 2, r_max=p["od"] / 2, height=h, sections=96)
            else:
                m = trimesh.creation.cylinder(radius=p["d"] / 2, height=h, sections=96)
            m.apply_translation([0, 0, z0 + h / 2])
        elif p["shape"] == "side_cylinder":
            x0, x1 = p["x"]
            m = trimesh.creation.cylinder(radius=p["d"] / 2, height=x1 - x0, sections=32)
            m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
            m.apply_translation([(x0 + x1) / 2, 0, p["z_center"]])
        else:
            raise ValueError(f"unknown proxy shape {p['shape']}")
        meshes.append(m)
    try:
        return trimesh.boolean.union(meshes, engine="manifold")
    except Exception:  # noqa: BLE001 - a plain concatenation still works for similarity and Blender
        return trimesh.util.concatenate(meshes)


def load_reference(rid: str) -> tuple[dict, trimesh.Trimesh, Path]:
    folder = REF_DIR / rid
    meta = json.loads((folder / "reference.json").read_text(encoding="utf-8"))
    if meta.get("model") and (folder / meta["model"]).is_file():
        path = folder / meta["model"]
        mesh, _ = load_mesh(path)
    else:
        path = folder / "proxy.stl"
        mesh = build_proxy(meta["proxy"])
        mesh.export(path)
    return meta, mesh, path


def reference_ids() -> list[str]:
    return sorted(p.name for p in REF_DIR.iterdir() if (p / "reference.json").is_file())


# ------------------------------------------------------------------ checks
def check_interface(feats: list[dict], iface: dict, open_mesh: bool = False) -> dict:
    d = iface["shaft_d"]
    cmin, cmax = iface["clearance"]
    # In an open (single-wall) mesh a lone loop can be a hole wall, so pegs count too.
    kinds = ("hole", "boss") if open_mesh else ("hole",)
    near = [f for f in feats if f["kind"] in kinds and d - 3 <= f["d"] <= d + 8]
    out = {"interface": iface["name"], "shaft_d": d, "clearance_ok": [cmin, cmax]}
    if not near:
        return {**out, "verdict": "no matching hole", "score": 0}
    ideal = (cmin + cmax) / 2
    best = min(near, key=lambda f: abs((f["d"] - d) - ideal) - 0.02 * f["length"])
    clr = round(best["d"] - d, 2)
    if clr < 0:
        verdict = "interference"
    elif clr < cmin:
        verdict = "too tight"
    elif clr > cmax:
        verdict = "too loose"
    else:
        verdict = "fits"
    if iface.get("max_hole_d") and best["d"] >= iface["max_hole_d"]:
        verdict = "falls through"
    notes = []
    if best["length"] < iface.get("min_length", 0):
        notes.append(f"engagement only {best['length']} mm (want >= {iface['min_length']})")
    if open_mesh and best["kind"] == "boss":
        notes.append("open mesh: matched a single-wall loop; confirm in the live Blender check")
    if iface.get("also_check"):
        notes.append("also check: " + iface["also_check"])
    score = {"fits": 100, "too tight": 55, "too loose": 45}.get(verdict, 10)
    if notes and verdict == "fits" and "engagement" in notes[0]:
        score = 75
    return {**out, "verdict": verdict, "hole_d": best["d"], "clearance": clr,
            "hole": best, "seat_z": iface.get("seat_z"), "notes": notes, "score": score}


def d2_histogram(mesh: trimesh.Trimesh, n: int = 3000, pairs: int = 30000) -> np.ndarray:
    pts, _ = trimesh.sample.sample_surface(mesh, n, seed=7)
    rng = np.random.default_rng(7)
    i, j = rng.integers(0, n, pairs), rng.integers(0, n, pairs)
    dist = np.linalg.norm(pts[i] - pts[j], axis=1)
    dist /= dist.mean() or 1
    hist, _ = np.histogram(dist, bins=48, range=(0, 3))
    return hist / max(hist.sum(), 1)


def similarity(a: trimesh.Trimesh, b: trimesh.Trimesh) -> dict:
    shape = 1 - 0.5 * float(np.abs(d2_histogram(a) - d2_histogram(b)).sum())
    ea, eb = np.sort(a.extents), np.sort(b.extents)
    size = float(np.mean(np.minimum(ea, eb) / np.maximum(np.maximum(ea, eb), 1e-9)))
    return {"score": round(100 * (0.6 * shape + 0.4 * size)), "shape": round(100 * shape), "size": round(100 * size)}


def check_against(mesh, feats, rid) -> dict:
    meta, ref_mesh, ref_path = load_reference(rid)
    fits = [check_interface(feats, i, open_mesh=not mesh.is_watertight) for i in meta["interfaces"]]
    best = max(fits, key=lambda f: f["score"])
    return {
        "reference": rid, "reference_name": meta["name"], "reference_status": meta.get("status"),
        "reference_mesh": str(ref_path),
        "fit": best["verdict"] if best["verdict"] != "no matching hole" else "no mating feature found",
        "best_interface": best, "interfaces": fits,
        "similarity": similarity(mesh, ref_mesh),
    }


# ------------------------------------------------------------------ report
def write_report(out: Path, name: str, results: list[dict]) -> Path:
    lines = [f"# Fit report: {name}", ""]
    provisional = {r["reference"] for res in results for r in res.get("checks", []) if r["reference_status"] == "provisional"}
    if provisional:
        lines += [f"> Provisional references ({', '.join(sorted(provisional))}): dimensions are typical values, "
                  "not measured from your parts. Treat verdicts as estimates.", ""]
    for res in results:
        lines += [f"## {Path(res['file']).name}", ""]
        if "error" in res:
            lines += [f"Could not analyse: {res['error']}", ""]
            continue
        s = res["summary"]
        lines += [f"- Size: {' x '.join(str(v) for v in s['extents_mm'])} mm, "
                  f"{s['faces']} faces, watertight: {s['watertight']}"]
        lines += [f"- Note: {n}" for n in res["notes"]]
        holes = [f for f in res["features"] if f["kind"] == "hole"][:6]
        if holes:
            lines += ["- Round holes: " + ", ".join(f"Ø{f['d']} ({f['axis']}, {f['length']} mm deep)" for f in holes)]
        lines += ["", "| Reference | Physical fit | Interface | Hole | Clearance | Similarity |", "|---|---|---|---|---|---|"]
        for c in res["checks"]:
            b = c["best_interface"]
            hole = f"Ø{b['hole_d']}" if "hole_d" in b else "-"
            clr = f"{b['clearance']:+} mm (ok {b['clearance_ok'][0]}..{b['clearance_ok'][1]})" if "clearance" in b else "-"
            lines += [f"| {c['reference']} | **{c['fit']}** | {b['interface']} | {hole} | {clr} | {c['similarity']['score']} / 100 |"]
            for n in b.get("notes", []):
                lines += [f"|  |  | {n} |  |  |  |"]
        lines += [""]
    path = out / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def cmd_check(a) -> int:
    files = model_files(a.inputs)
    if not files:
        print(json.dumps({"ok": False, "error": f"no model files ({', '.join(sorted(MESH_EXT))}) in {a.inputs}"}))
        return 1
    if a.out:
        out = Path(a.out)
    else:
        try:
            out = workspace(load_config()) / "fit" / a.name
        except ConfigError as e:
            print(json.dumps({"ok": False, "error": f"{e} (or pass --out)"}))
            return 1
    (out / "blender").mkdir(parents=True, exist_ok=True)
    refs = reference_ids() if a.ref in ("auto", "all") else [a.ref]

    results = []
    for f in files:
        res = {"file": str(f.resolve())}
        try:
            mesh, notes = load_mesh(f)
            feats = circular_features(mesh)
            stl = out / "blender" / f"{f.stem}.stl"
            mesh.export(stl)
            checks = [check_against(mesh, feats, rid) for rid in refs]
            checks.sort(key=lambda c: (c["best_interface"]["score"], c["similarity"]["score"]), reverse=True)
            if a.ref == "auto":
                checks = checks[:1]
            res.update(summary=summary(mesh), notes=notes, features=feats, blender_stl=str(stl), checks=checks)
        except Exception as e:  # noqa: BLE001 - one bad file must not stop the others
            res["error"] = f"{type(e).__name__}: {e}"
        results.append(res)

    for rid in refs:
        load_reference(rid)[1].export(out / "blender" / f"REF_{rid}.stl")

    report = write_report(out, a.name, results)
    (out / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    ok_results = [r for r in results if "checks" in r]
    best = max(ok_results, key=lambda r: (r["checks"][0]["best_interface"]["score"], r["checks"][0]["similarity"]["score"]), default=None)
    print(report.read_text(encoding="utf-8"))
    print(json.dumps({
        "ok": bool(ok_results), "report": str(report), "report_json": str(out / "report.json"),
        "blender_dir": str(out / "blender"),
        "best": None if not best else {
            "file": best["file"], "blender_stl": best["blender_stl"],
            "reference": best["checks"][0]["reference"], "fit": best["checks"][0]["fit"],
            "interface": best["checks"][0]["best_interface"]["interface"],
            "similarity": best["checks"][0]["similarity"]["score"],
        },
    }))
    return 0 if ok_results else 1


def cmd_measure(a) -> int:
    mesh, notes = load_mesh(Path(a.file))
    print(json.dumps({"summary": summary(mesh), "notes": notes, "features": circular_features(mesh)[:25]}, indent=2))
    return 0


def cmd_refs(_a) -> int:
    for rid in reference_ids():
        meta, mesh, path = load_reference(rid)
        feats = circular_features(mesh)
        print(f"{rid}: {meta['status']}  mesh={path}  size={summary(mesh)['extents_mm']}  "
              f"interfaces={[i['name'] + ' Ø' + str(i['shaft_d']) for i in meta['interfaces']]}  "
              f"pegs={sorted({f['d'] for f in feats if f['kind'] == 'boss'})[:6]}")
    return 0


def cmd_selftest(_a) -> int:
    """Synthetic parts with known answers, so a broken engine is caught by the doctor."""
    import tempfile

    def plate(hole_d, od=120.0, t=3.0):
        return trimesh.creation.annulus(r_min=hole_d / 2, r_max=od / 2, height=t, sections=128)

    cases = [("ac-lamp", plate(41.0), "fits"), ("ac-lamp", plate(38.5), "interference"),
             ("ac-lamp", plate(46.0), "too loose"), ("ac-lamp", plate(10.6, od=40), "fits"),
             ("dc-lamp", trimesh.creation.annulus(r_min=35.6, r_max=40, height=12, sections=128), "fits")]
    failed = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (rid, mesh, want) in enumerate(cases):
            p = Path(tmp) / f"case{i}.stl"
            mesh.export(p)
            m, _ = load_mesh(p)
            got = check_against(m, circular_features(m), rid)["fit"]
            print(f"case {i} {rid}: want {want}, got {got}")
            if got != want:
                failed.append(i)
    print(json.dumps({"ok": not failed, "failed_cases": failed}))
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("inputs", nargs="+")
    c.add_argument("--name", required=True)
    c.add_argument("--ref", default="auto", help="auto (best match), all, or a reference id")
    c.add_argument("--out")
    m = sub.add_parser("measure")
    m.add_argument("file")
    sub.add_parser("refs")
    sub.add_parser("selftest")
    a = ap.parse_args()
    return {"check": cmd_check, "measure": cmd_measure, "refs": cmd_refs, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
