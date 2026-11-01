# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.64.0", "trimesh==4.5.3", "numpy", "networkx", "lxml"]
# ///
"""Production sheet: slice a model, cost it in BDT, and write a branded PDF.

  uv run scripts/production.py <model> [<model> ...] --name NAME
        [--printer A1|A1 mini|P1S|P1P|X1C] [--filament "PLA Matte"] [--color "Bone white"]
        [--qty 1] [--hardware "E27 holder=180" ...] [--source URL] [--license TEXT]
        [--image PNG] [--out DIR]
  uv run scripts/production.py selftest

Slicing uses the Bambu Studio CLI with the printer's 0.20mm Standard profile. Bambu's system
profiles inherit from each other and the CLI does not resolve that, so they are flattened first.
No Bambu Studio: grams and hours are estimated from the mesh volume and marked as estimates.
Rates come from pricing.json at the repo root.
Writes <out>/production.json, production.html and production.pdf (default out:
<workspace>/production/<NAME>). The last stdout line is JSON: {"ok": true, "pdf": ...}.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

from studio_config import REPO_ROOT, ConfigError, load_config, workspace

BAMBU = Path(r"C:\Program Files\Bambu Studio\bambu-studio.exe")
MACHINES = {"A1": "Bambu Lab A1", "A1 mini": "Bambu Lab A1 mini", "P1S": "Bambu Lab P1S",
            "P1P": "Bambu Lab P1P", "X1C": "Bambu Lab X1 Carbon"}


def load_pricing() -> dict:
    return json.loads((REPO_ROOT / "pricing.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- slicing
def _profiles(root: Path, printer: str, filament: str) -> dict[str, dict]:
    def load(kind: str, name: str) -> dict:
        d = json.loads((root / kind / f"{name}.json").read_text(encoding="utf-8"))
        if d.get("inherits"):
            base = load(kind, d["inherits"]); base.update(d); d = base
        return d

    machine_name = f"{MACHINES[printer]} 0.4 nozzle"

    def pick(kind: str, prefixes: list[str]) -> dict:
        for prefix in prefixes:
            for f in sorted((root / kind).glob(f"{prefix}*.json")):
                d = load(kind, f.stem)
                if machine_name in d.get("compatible_printers", []):
                    return d
        raise SystemExit(f"no {kind} profile {prefixes} for {machine_name}")

    out = {"machine": load("machine", machine_name),
           "process": pick("process", ["0.20mm Standard @BBL"]),
           "filament": pick("filament", [f"Bambu {filament} @BBL", f"Generic {filament} @BBL",
                                         f"Bambu {filament} Basic @BBL"])}
    for d in out.values():
        d.pop("inherits", None)
    return out


def slice_bambu(models: list[Path], printer: str, filament: str, exe: Path) -> dict:
    root = exe.parent / "resources" / "profiles" / "BBL"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        prof = _profiles(root, printer, filament)
        for kind, d in prof.items():
            (tmp / f"{kind}.json").write_text(json.dumps(d), encoding="utf-8")
        cmd = [str(exe), "--arrange", "1",
               "--load-settings", f"{tmp / 'machine.json'};{tmp / 'process.json'}",
               "--load-filaments", str(tmp / "filament.json"),
               "--slice", "0", "--min-save", "--export-3mf", "out.3mf", "--outputdir", str(tmp),
               *map(str, models)]
        subprocess.run(cmd, capture_output=True, timeout=1800)
        res_file = tmp / "result.json"
        res = json.loads(res_file.read_text(encoding="utf-8")) if res_file.is_file() else {}
    if res.get("return_code") != 0:
        raise RuntimeError(f"Bambu Studio slice failed: {res.get('error_string', 'no result.json (crash)')}")
    plates = res["sliced_plates"]
    return {
        "method": "Bambu Studio CLI",
        "grams": round(sum(f["total_used_g"] for p in plates for f in p["filaments"]), 1),
        "seconds": round(sum(p["total_predication"] for p in plates)),
        "plates": len(plates),
        "machine": prof["machine"]["name"], "process": prof["process"]["name"],
        "filament_profile": prof["filament"]["name"],
        "layer_height": round(res.get("layer_height", 0.2), 2),
        "walls": res.get("wall_loops"), "infill_pct": res.get("sparse_infill_density"),
        "supports": prof["process"].get("enable_support", "0") not in ("0", 0, False),
    }


def estimate(models: list[Path], density: float) -> dict:
    # ponytail: volume x density plus 5% waste, about 13 g/h on a 0.4 nozzle; a slicer is the upgrade
    import trimesh
    vol = sum(trimesh.load(str(m), force="mesh").volume for m in models) / 1000.0  # mm3 -> cm3
    grams = vol * density * 1.05
    return {"method": "estimate from mesh volume (no slicer)", "grams": round(grams, 1),
            "seconds": round(grams / 13 * 3600), "plates": 1, "machine": "-", "process": "-",
            "filament_profile": "-", "layer_height": 0.2, "walls": None, "infill_pct": None,
            "supports": None}


# ---------------------------------------------------------------- money
def costs(grams: float, seconds: float, filament: str, printer: str, hardware: dict[str, float],
          p: dict) -> dict:
    hours = seconds / 3600
    lines = {
        "Filament": grams / 1000 * p["filament_bdt_per_kg"][filament],
        "Electricity": p["printer_watts"][printer] / 1000 * hours * p["electricity_bdt_per_kwh"],
        "Machine time": hours * p["machine_bdt_per_hour"],
        "Labour and finishing": p["labour_bdt"],
        "Packaging": p["packaging_bdt"],
        **hardware,
    }
    subtotal = sum(lines.values())
    lines["Failed-print allowance"] = (lines["Filament"] + lines["Electricity"] + lines["Machine time"]) * p["failure_allowance"]
    cost = sum(lines.values())
    step = p["round_price_to"]
    rnd = lambda x: int(math.ceil(x / step) * step)
    rate = p["brand_rate_bdt_per_g"].get(filament)
    rate_price = rnd(grams * rate + sum(hardware.values())) if rate else None
    cost_plus = rnd(cost * (1 + p["margin"]))
    return {"lines": {k: round(v, 2) for k, v in lines.items()}, "subtotal": round(subtotal, 2),
            "unit_cost": round(cost, 2), "brand_rate_price": rate_price, "cost_plus_price": cost_plus,
            "suggested_price": max(x for x in (rate_price, cost_plus) if x),
            "margin": p["margin"], "rate_bdt_per_g": rate}


def fmt_time(seconds: float) -> str:
    h, m = divmod(round(seconds / 60), 60)
    return f"{h} h {m:02d} min"


# ---------------------------------------------------------------- pdf
def render_html(d: dict, logo: Path | None, image: Path | None) -> str:
    e = html.escape
    tk = lambda x: f"৳{x:,.0f}"
    s, c = d["slice"], d["cost"]
    meters = s["grams"] / (d["density"] * math.pi * 0.0875 ** 2 * 100)  # 1.75 mm filament
    rows = "".join(f"<tr><td>{e(k)}</td><td class=n>{tk(v)}</td></tr>" for k, v in c["lines"].items())
    hw = "".join(f"<tr><td>{e(k)}</td><td>1 per unit</td><td class=n>{tk(v)}</td></tr>" for k, v in d["hardware"].items())
    settings = [("Printer", s["machine"]), ("Process", s["process"]), ("Filament profile", s["filament_profile"]),
                ("Layer height", f"{s['layer_height']} mm"), ("Walls", s["walls"]),
                ("Sparse infill", f"{s['infill_pct']:.0f}%" if s["infill_pct"] is not None else None),
                ("Supports", {True: "on", False: "off"}.get(s["supports"])), ("Plates", s["plates"]),
                ("Method", s["method"])]
    settings_html = "".join(f"<div><dt>{e(k)}</dt><dd>{e(str(v))}</dd></div>" for k, v in settings if v not in (None, "-"))
    warn = (f"<p class=warn><b>Licence:</b> {e(d['license'])}. Selling prints may need the designer's permission.</p>"
            if d.get("license") and not any(w in d["license"].lower() for w in ("commercial use allowed", "cc by ", "cc0", "public domain"))
            else "")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(d['name'])} production sheet</title><style>
:root {{ --ink:#0A0A0B; --paper:#FAF8F3; --muted:#5E5A55; --rule:#D9D6CE; --copper:#D97B2C;
  --display:"Space Grotesk","Hind Siliguri",sans-serif; --body:"Inter","Hind Siliguri",sans-serif; --fig:"JetBrains Mono","Hind Siliguri",monospace; }}
@page {{ size: A4; margin: 0; }}
* {{ box-sizing: border-box; }} body {{ margin:0; padding: 12mm 16mm 10mm; font: 400 10pt/1.45 var(--body); color: var(--ink); background: var(--paper); }}
header {{ display:flex; justify-content:space-between; align-items:flex-start; border-bottom: 1.5pt solid var(--copper); padding-bottom: 10pt; }}
header img {{ height: 34pt; }} h1 {{ font: 600 22pt/1.1 var(--display); letter-spacing: -0.02em; margin: 0 0 4pt; }}
h2 {{ font: 600 12pt/1.2 var(--display); margin: 12pt 0 4pt; }}
.meta {{ color: var(--muted); font-size: 9pt; }} .meta a {{ color: inherit; }}
.top {{ display:grid; grid-template-columns: 1fr 118pt; gap: 16pt; margin-top: 14pt; }}
.top img {{ width: 118pt; border-radius: 4pt; background: #101216; }}
.kpis {{ display:grid; grid-template-columns: repeat(3, 1fr); gap: 10pt 14pt; margin: 0; align-content: start; }}
.kpis dt, .set dt {{ color: var(--muted); font-size: 8.5pt; }} .kpis dd {{ margin:0; font: 500 12.5pt/1.25 var(--fig); }}
.kpis .price dd {{ color: var(--copper); }}
table {{ width:100%; border-collapse: collapse; }} td, th {{ padding: 4pt 0; border-bottom: 0.5pt solid var(--rule); text-align:left; vertical-align: top; }}
th {{ font-weight: 600; font-size: 8.5pt; color: var(--muted); }} .n {{ text-align:right; font-family: var(--fig); }}
tr.total td {{ font-weight: 600; border-bottom: 1.5pt solid var(--ink); }}
.set {{ display:grid; grid-template-columns: repeat(3, 1fr); gap: 6pt 14pt; margin: 0; }} .set dd {{ margin: 0; }}
.two {{ display:grid; grid-template-columns: 1fr 1fr; gap: 20pt; }}
.warn {{ border-left: 3pt solid var(--copper); padding: 6pt 10pt; background: #F3E6D8; margin-top: 14pt; }}
.note {{ color: var(--muted); font-size: 8pt; margin-top: 12pt; }}
</style></head><body>
<header><div><h1>{e(d['title'])}</h1><div class=meta>Production sheet, {e(d['date'])}. Quantity {d['qty']}.{' Source: <a href="' + e(d['source']) + '">' + e(d['source']) + '</a>' if d.get('source') else ''}</div></div>
{f'<img src="{logo.as_uri()}" alt="Borgo Labs">' if logo else ''}</header>
<section class=top><dl class=kpis>
<div><dt>Material</dt><dd>{e(d['filament'])}</dd></div><div><dt>Colour</dt><dd>{e(d['color'])}</dd></div>
<div><dt>Filament per unit</dt><dd>{s['grams']:.0f} g ({meters:.1f} m)</dd></div>
<div><dt>Print time per unit</dt><dd>{fmt_time(s['seconds'])}</dd></div>
<div><dt>Production cost</dt><dd>{tk(c['unit_cost'])}</dd></div>
<div class=price><dt>Suggested price</dt><dd>{tk(c['suggested_price'])}</dd></div>
</dl>{f'<img src="{image.as_uri()}" alt="">' if image else ''}</section>
{warn}
<h2>Materials needed</h2>
<table><tr><th>Item</th><th>Quantity</th><th class=n>Cost</th></tr>
<tr><td>{e(d['filament'])} filament, {e(d['color'])}, 1.75 mm</td><td>{s['grams']:.0f} g per unit; {s['grams'] * d['qty'] / 1000:.2f} kg for {d['qty']}</td><td class=n>{tk(c['lines']['Filament'])}</td></tr>
{hw}<tr><td>Packaging</td><td>1 per unit</td><td class=n>{tk(c['lines']['Packaging'])}</td></tr></table>
<div class=two><div><h2>Cost per unit</h2><table>{rows}<tr class=total><td>Production cost</td><td class=n>{tk(c['unit_cost'])}</td></tr></table></div>
<div><h2>Selling price</h2><table>
{f"<tr><td>Brand rate, {s['grams']:.0f} g at ৳{c['rate_bdt_per_g']}/g{' plus hardware' if d['hardware'] else ''}</td><td class=n>{tk(c['brand_rate_price'])}</td></tr>" if c['brand_rate_price'] else ''}
<tr><td>Cost plus {c['margin']:.0%} margin</td><td class=n>{tk(c['cost_plus_price'])}</td></tr>
<tr class=total><td>Suggested price (the higher)</td><td class=n>{tk(c['suggested_price'])}</td></tr>
<tr><td>Margin at suggested price</td><td class=n>{tk(c['suggested_price'] - c['unit_cost'])}</td></tr>
<tr><td>Print time for {d['qty']} unit(s)</td><td class=n>{fmt_time(s['seconds'] * d['qty'])}</td></tr></table></div></div>
<h2>Print settings</h2><dl class=set>{settings_html}</dl>
<p class=note>Times and grams come from {e(s['method'])}. Costs use pricing.json in the alifs-3d-agent repo
(filament ৳/kg, electricity ৳{d['pricing']['electricity_bdt_per_kwh']}/kWh, machine ৳{d['pricing']['machine_bdt_per_hour']}/h, failed-print allowance {d['pricing']['failure_allowance']:.0%}). Edit that file to change them.
{('Design: ' + e(d['credit']) + '.') if d.get('credit') else ''}</p>
</body></html>"""


def write_pdf(html_path: Path, pdf_path: Path) -> None:
    from export_poster import font_css
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); page = b.new_page()
        page.goto(html_path.as_uri(), wait_until="load")
        page.add_style_tag(content=font_css())
        page.evaluate("document.fonts.ready")
        page.pdf(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=True)
        b.close()


# ---------------------------------------------------------------- cli
def selftest() -> int:
    p = load_pricing()
    c = costs(100, 3600, "PLA Basic", "A1", {"Holder": 100}, p)
    assert c["lines"]["Filament"] == 220.0, c
    assert abs(c["lines"]["Electricity"] - 1.14) < 0.01, c
    assert c["brand_rate_price"] == 700 and c["suggested_price"] >= c["cost_plus_price"], c
    assert fmt_time(23814) == "6 h 37 min"
    print(json.dumps({"ok": True}))
    return 0


def main() -> int:
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("models", nargs="+")
    ap.add_argument("--name", required=True)
    ap.add_argument("--title")
    ap.add_argument("--printer", default="A1", choices=list(MACHINES))
    ap.add_argument("--filament", default="PLA Matte")
    ap.add_argument("--color", default="Bone white")
    ap.add_argument("--qty", type=int, default=1)
    ap.add_argument("--hardware", action="append", default=[], help='"Item name=BDT", per unit')
    ap.add_argument("--source"); ap.add_argument("--license"); ap.add_argument("--credit")
    ap.add_argument("--image"); ap.add_argument("--out"); ap.add_argument("--config")
    a = ap.parse_args()

    p = load_pricing()
    if a.filament not in p["filament_bdt_per_kg"]:
        print(json.dumps({"ok": False, "error": f"filament {a.filament!r} not in pricing.json; add it or use one of {list(p['filament_bdt_per_kg'])}"}))
        return 1
    models = [Path(m).resolve() for m in a.models]
    hardware = {k.strip(): float(v) for k, v in (h.rsplit("=", 1) for h in a.hardware)}
    try:
        cfg = load_config(a.config)
        out = Path(a.out) if a.out else workspace(cfg) / "production" / a.name
    except ConfigError as e:
        if not a.out:
            print(json.dumps({"ok": False, "error": str(e)})); return 1
        cfg, out = {}, Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    exe = Path(cfg.get("bambu_studio_path") or BAMBU)
    try:
        s = slice_bambu(models, a.printer, a.filament, exe) if exe.is_file() else estimate(models, p["density_g_cm3"][a.filament])
    except (RuntimeError, SystemExit, subprocess.TimeoutExpired) as e:
        print(f"production.py: slicer failed ({e}); falling back to a volume estimate", file=sys.stderr)
        s = estimate(models, p["density_g_cm3"][a.filament])

    d = {"name": a.name, "title": a.title or a.name.replace("-", " ").title(), "date": dt.date.today().isoformat(),
         "qty": a.qty, "printer": a.printer, "filament": a.filament, "color": a.color, "hardware": hardware,
         "source": a.source, "license": a.license, "credit": a.credit, "density": p["density_g_cm3"][a.filament],
         "models": [str(m) for m in models], "slice": s, "pricing": p,
         "cost": costs(s["grams"], s["seconds"], a.filament, a.printer, hardware, p)}
    logo = REPO_ROOT / "brand" / "borgo-labs-logo-light.png"
    (out / "production.json").write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    html_path = out / "production.html"
    html_path.write_text(render_html(d, logo if logo.is_file() else None, Path(a.image).resolve() if a.image else None), encoding="utf-8")
    write_pdf(html_path, out / "production.pdf")
    print(json.dumps({"ok": True, "pdf": str(out / "production.pdf"), "grams": s["grams"],
                      "print_time": fmt_time(s["seconds"]), "unit_cost_bdt": d["cost"]["unit_cost"],
                      "suggested_price_bdt": d["cost"]["suggested_price"], "method": s["method"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
