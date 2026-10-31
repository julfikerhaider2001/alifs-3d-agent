# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Locate and load local.config.json for alifs-3d-agent.

Lookup order:
  1. --config <path> passed to a script (handled by callers via load_config(path))
  2. ALIF3D_CONFIG environment variable (set by scripts/setup.ps1)
  3. local.config.json at the repo root (next to scripts/)

Run directly to print the resolved config as JSON:
  uv run scripts/studio_config.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = REPO_ROOT / "fonts"
BLENDER_MCP_PORT = 9877
POSTER_SIZES = {
    "feed": (1080, 1350),
    "story": (1080, 1920),
    "facebook": (1200, 630),
}


class ConfigError(RuntimeError):
    pass


def config_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("ALIF3D_CONFIG")
    if env and Path(env).is_file():
        return Path(env)
    return REPO_ROOT / "local.config.json"


def load_config(explicit: str | None = None) -> dict:
    path = config_path(explicit)
    if not path.is_file():
        raise ConfigError(
            f"local.config.json not found at {path}. Run scripts\\setup.ps1 on this PC first."
        )
    # utf-8-sig tolerates a BOM if someone edits the file in an older editor.
    cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    cfg["_path"] = str(path)
    return cfg


def workspace(cfg: dict) -> Path:
    ws = cfg.get("workspace")
    if not ws:
        raise ConfigError("local.config.json has no 'workspace'. Re-run scripts\\setup.ps1.")
    return Path(ws)


if __name__ == "__main__":
    try:
        cfg = load_config(sys.argv[1] if len(sys.argv) > 1 else None)
    except ConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    cfg["_plugin_root"] = str(REPO_ROOT)
    cfg["_fonts_dir"] = str(FONTS_DIR)
    print(json.dumps(cfg, indent=2))
