# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.64.0"]
# ///
"""Export an HTML/CSS poster to PNG at social sizes with headless Chromium.

  uv run scripts/export_poster.py <poster.html> --name NAME
        [--sizes feed,story,facebook] [--out DIR]

Sizes: feed 1080x1350, story 1080x1920, facebook 1200x630.
Writes <out>/<NAME>_<size>.png (default out: <workspace>/posters from local.config.json).

Before each screenshot the exporter:
  * sets <html data-size="feed|story|facebook"> so the poster CSS can adapt its layout,
  * injects @font-face rules for the bundled fonts (Inter, Space Grotesk, JetBrains Mono,
    Hind Siliguri, Noto Sans Bengali) as data: URIs, so the poster only names the families,
  * waits for fonts, and fails if any Bangla text is not set in a Bengali font.
The last stdout line is JSON: {"ok": true, "files": [...]}.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from studio_config import FONTS_DIR, POSTER_SIZES, ConfigError, load_config, workspace

FONT_FACES = [
    # (family, file, weight range)
    ("Inter", "Inter-Variable.ttf", "100 900"),
    ("Space Grotesk", "SpaceGrotesk-Variable.ttf", "300 700"),
    ("JetBrains Mono", "JetBrainsMono-Variable.ttf", "100 800"),
    ("Noto Sans Bengali", "NotoSansBengali-Variable.ttf", "100 900"),
    ("Hind Siliguri", "HindSiliguri-Regular.ttf", "400"),
    ("Hind Siliguri", "HindSiliguri-Medium.ttf", "500"),
    ("Hind Siliguri", "HindSiliguri-SemiBold.ttf", "600"),
    ("Hind Siliguri", "HindSiliguri-Bold.ttf", "700"),
]
BENGALI_FAMILIES = ("hind siliguri", "noto sans bengali")

# Returns a list of problems: Bangla text whose first font-family is not a Bengali font.
CHECK_BANGLA_JS = r"""
() => {
  const bad = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!/[ঀ-৿]/.test(n.nodeValue)) continue;
    const el = n.parentElement;
    const first = getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim().toLowerCase();
    if (!BENGALI.includes(first)) bad.push(`<${el.tagName.toLowerCase()}> "${n.nodeValue.trim().slice(0, 40)}" uses ${first}`);
  }
  return bad;
}
"""


def font_css() -> str:
    rules = []
    for family, file, weight in FONT_FACES:
        data = base64.b64encode((FONTS_DIR / file).read_bytes()).decode("ascii")
        rules.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};font-style:normal;"
            f"font-display:block;src:url(data:font/ttf;base64,{data}) format('truetype');}}"
        )
    return "\n".join(rules)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html")
    ap.add_argument("--name", required=True)
    ap.add_argument("--sizes", default="feed,story,facebook")
    ap.add_argument("--out")
    ap.add_argument("--config")
    a = ap.parse_args()

    html = Path(a.html).resolve()
    if not html.is_file():
        print(json.dumps({"ok": False, "error": f"no such file: {html}"}))
        return 1
    sizes = [s.strip() for s in a.sizes.split(",") if s.strip()]
    unknown = [s for s in sizes if s not in POSTER_SIZES]
    if unknown:
        print(json.dumps({"ok": False, "error": f"unknown sizes {unknown}; use {list(POSTER_SIZES)}"}))
        return 1
    if a.out:
        out = Path(a.out).resolve()
    else:
        try:
            out = workspace(load_config(a.config)) / "posters"
        except ConfigError as e:
            print(json.dumps({"ok": False, "error": f"{e} (or pass --out)"}))
            return 1
    out.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    css = font_css()
    check_js = CHECK_BANGLA_JS.replace("BENGALI", json.dumps(list(BENGALI_FAMILIES)))
    files, problems = [], []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for size in sizes:
                w, h = POSTER_SIZES[size]
                page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
                page.goto(html.as_uri(), wait_until="load")
                page.add_style_tag(content=css)
                page.evaluate("s => document.documentElement.setAttribute('data-size', s)", size)
                page.evaluate("""async () => {
                    await Promise.all([
                      document.fonts.load("400 32px 'Inter'"),
                      document.fonts.load("700 32px 'Hind Siliguri'", "বাংলা"),
                      document.fonts.load("400 32px 'Noto Sans Bengali'", "বাংলা"),
                    ]);
                    await document.fonts.ready;
                }""")
                bad = page.evaluate(check_js)
                if bad:
                    problems += [f"{size}: {b}" for b in bad]
                target = out / f"{a.name}_{size}.png"
                page.screenshot(path=str(target), clip={"x": 0, "y": 0, "width": w, "height": h})
                files.append(str(target))
                print(f"export_poster.py: {size} {w}x{h} -> {target}", flush=True)
                page.close()
            browser.close()
    except PlaywrightError as e:
        hint = "Run: uvx --from playwright==1.64.0 playwright install chromium" if "Executable doesn't exist" in str(e) else ""
        print(json.dumps({"ok": False, "error": str(e).splitlines()[0], "hint": hint}))
        return 1

    if problems:
        for prob in problems:
            print("export_poster.py: Bangla text not in a Bengali font:", prob, file=sys.stderr)
        print(json.dumps({"ok": False, "files": files, "error": "Bangla text must use 'Hind Siliguri' or 'Noto Sans Bengali' as the first font-family", "problems": problems}))
        return 1
    print(json.dumps({"ok": True, "files": files}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
