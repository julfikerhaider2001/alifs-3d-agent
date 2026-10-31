# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Download a 3D model from a link (or take a local file) into <workspace>/input/<name>/.

  uv run scripts/fetch_model.py <url-or-path> [--name NAME] [--out DIR]

Supported:
  * printables.com/model/<id>-...   public API, no login
  * thingiverse.com/thing:<id>      official API; needs your Thingiverse app token in
                                    local.config.json "thingiverse_token" or env THINGIVERSE_TOKEN
  * direct links to .stl .3mf .obj .step .stp .glb .ply .zip
  * a local file, folder or .zip (e.g. something you downloaded yourself)
Sites that require a login or block scripts (MakerWorld, Cults3D, ...) are not scraped: download the
file in your browser and pass its path instead.

The last stdout line is JSON: {"ok": true, "dir": ..., "files": [...], "title": ..., "source": ...}.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from studio_config import ConfigError, load_config, workspace

MODEL_EXT = {".stl", ".3mf", ".obj", ".step", ".stp", ".glb", ".gltf", ".ply", ".f3d"}
UA = "alifs-3d-agent/0.1 (+personal product-render pipeline)"
LOGIN_SITES = {
    "makerworld.com": "MakerWorld",
    "cults3d.com": "Cults3D",
    "myminifactory.com": "MyMiniFactory",
    "thangs.com": "Thangs",
    "grabcad.com": "GrabCAD",
}


class FetchError(RuntimeError):
    pass


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "model"


def http(url: str, data: bytes | None = None, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP {e.code} from {urllib.parse.urlparse(url).netloc}") from e


def short_path(dest: Path, filename: str, limit: int = 240) -> Path:
    """dest/filename, with the stem trimmed so the full path stays under Windows' MAX_PATH."""
    name = Path(filename).name
    room = limit - len(str(dest)) - 1
    if len(name) > room:
        stem, ext = Path(name).stem, Path(name).suffix
        name = stem[: max(room - len(ext), 8)] + ext
    return dest / name


def save_payload(name: str, payload: bytes, dest: Path) -> list[Path]:
    """Write a download; unzip archives (model files only, flattened). Returns model files."""
    dest.mkdir(parents=True, exist_ok=True)
    if Path(name).suffix.lower() == ".zip":  # not .3mf, which is also a zip
        zip_path = dest / "_download.zip"
        zip_path.write_bytes(payload)
        with zipfile.ZipFile(zip_path) as z:
            for member in z.infolist():
                if member.is_dir() or Path(member.filename).suffix.lower() not in MODEL_EXT:
                    continue  # skip PDFs, G-code, images
                short_path(dest, member.filename).write_bytes(z.read(member))
        zip_path.unlink()
    else:
        short_path(dest, name).write_bytes(payload)
    return sorted(p for p in dest.rglob("*") if p.suffix.lower() in MODEL_EXT)


# ------------------------------------------------------------------ sources
def printables(url: str, dest_root: Path, name: str | None) -> dict:
    m = re.search(r"/model/(\d+)", url)
    if not m:
        raise FetchError("could not find the model id in the Printables link")
    pid = m.group(1)

    def gql(query: str) -> dict:
        body = json.dumps({"query": query}).encode()
        res = json.loads(http("https://api.printables.com/graphql/", body, {"content-type": "application/json"}))
        if res.get("errors"):
            raise FetchError("Printables API: " + res["errors"][0]["message"])
        return res["data"]

    info = gql(f'query {{ print(id: "{pid}") {{ id name slug downloadPacks {{ id fileType }} '
               f'stls {{ id name }} otherFiles {{ id name }} }} }}')["print"]
    if not info:
        raise FetchError(f"Printables model {pid} not found (deleted or private)")
    dest = dest_root / (name or slugify(info["slug"] or info["name"]))
    packs = info.get("downloadPacks") or []
    # Model packs first, then single STLs, then other packs (which may hold only G-code).
    jobs = [(p["id"], "pack") for p in packs if p["fileType"] == "MODEL_FILES"]
    jobs += [(s["id"], "stl") for s in info.get("stls") or []]
    jobs += [(p["id"], "pack") for p in packs if p["fileType"] != "MODEL_FILES"]
    if not jobs:
        raise FetchError("this Printables model has no downloadable files")
    files: list[Path] = []
    for fid, ftype in jobs:
        out = gql(f'mutation {{ getDownloadLink(id: "{fid}", printId: "{pid}", fileType: {ftype}, '
                  f'source: model_detail) {{ ok output {{ link }} errors {{ messages }} }} }}')["getDownloadLink"]
        if not out["ok"]:
            raise FetchError(f"Printables refused the download: {out['errors']}")
        link = out["output"]["link"]
        files = save_payload(Path(urllib.parse.urlparse(link).path).name, http(link), dest)
        if files and ftype == "pack":
            break
    return {"dir": str(dest), "files": [str(f) for f in files], "title": info["name"], "source": "printables"}


def thingiverse(url: str, dest_root: Path, name: str | None, token: str | None) -> dict:
    m = re.search(r"thing:(\d+)", url)
    if not m:
        raise FetchError("could not find the thing id in the Thingiverse link")
    if not token:
        raise FetchError("Thingiverse needs your own API token: create an app at "
                         "https://www.thingiverse.com/developers, copy its App Token into local.config.json "
                         "as \"thingiverse_token\" (or set THINGIVERSE_TOKEN). Or download the files in your "
                         "browser and pass the path.")
    tid = m.group(1)
    auth = {"Authorization": f"Bearer {token}"}
    thing = json.loads(http(f"https://api.thingiverse.com/things/{tid}", headers=auth))
    listing = json.loads(http(f"https://api.thingiverse.com/things/{tid}/files", headers=auth))
    dest = dest_root / (name or slugify(thing.get("name", f"thing-{tid}")))
    files: list[Path] = []
    for f in listing:
        if Path(f["name"]).suffix.lower() in MODEL_EXT | {".zip"}:
            files = save_payload(f["name"], http(f["download_url"], headers=auth), dest)
    if not files:
        raise FetchError("no model files in this Thing")
    return {"dir": str(dest), "files": [str(f) for f in files], "title": thing.get("name"), "source": "thingiverse"}


def direct(url: str, dest_root: Path, name: str | None) -> dict:
    fname = Path(urllib.parse.unquote(urllib.parse.urlparse(url).path)).name
    dest = dest_root / (name or slugify(Path(fname).stem))
    files = save_payload(fname, http(url), dest)
    return {"dir": str(dest), "files": [str(f) for f in files], "title": fname, "source": "direct"}


def local(path: Path, dest_root: Path, name: str | None) -> dict:
    dest = dest_root / (name or slugify(path.stem))
    if path.is_dir():
        if path.resolve() != dest.resolve():
            shutil.copytree(path, dest, dirs_exist_ok=True)
        files = sorted(p for p in dest.rglob("*") if p.suffix.lower() in MODEL_EXT)
    else:
        files = save_payload(path.name, path.read_bytes(), dest)
    return {"dir": str(dest), "files": [str(f) for f in files], "title": path.name, "source": "local"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="link or local path")
    ap.add_argument("--name", help="folder name under input/ (default: from the model title)")
    ap.add_argument("--out", help="parent folder (default: <workspace>/input)")
    a = ap.parse_args()

    cfg = {}
    try:
        cfg = load_config()
    except ConfigError:
        if not a.out:
            print(json.dumps({"ok": False, "error": "no local.config.json; run install.ps1 or pass --out"}))
            return 1
    dest_root = Path(a.out) if a.out else workspace(cfg) / "input"
    name = slugify(a.name) if a.name else None
    token = os.environ.get("THINGIVERSE_TOKEN") or cfg.get("thingiverse_token")

    src = a.source.strip().strip('"')
    host = urllib.parse.urlparse(src).netloc.lower().removeprefix("www.")
    try:
        if Path(src).exists():
            res = local(Path(src), dest_root, name)
        elif host.endswith("printables.com"):
            res = printables(src, dest_root, name)
        elif host.endswith("thingiverse.com"):
            res = thingiverse(src, dest_root, name, token)
        elif any(host.endswith(h) for h in LOGIN_SITES):
            site = next(v for h, v in LOGIN_SITES.items() if host.endswith(h))
            raise FetchError(f"{site} needs a logged-in browser to download, and this tool doesn't scrape it. "
                             f"Download the model in your browser, then give me the file path "
                             f"(or drop it in <workspace>/input/).")
        elif Path(urllib.parse.urlparse(src).path).suffix.lower() in MODEL_EXT | {".zip"}:
            res = direct(src, dest_root, name)
        else:
            raise FetchError("unrecognised link. Supported: Printables, Thingiverse (with token), direct file "
                             "links, or a local file/folder. For other sites, download it and pass the path.")
    except FetchError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1
    if not res["files"]:
        print(json.dumps({"ok": False, "error": "downloaded, but no 3D model files inside (e.g. only G-code/PDF); "
                          "ask the designer for STL/3MF/STEP or pick another model", **res}))
        return 1
    print(json.dumps({"ok": True, **res}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
