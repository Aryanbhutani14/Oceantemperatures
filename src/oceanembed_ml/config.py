"""Project-wide paths and configuration loading (single place to change paths)."""
from __future__ import annotations

import os
from pathlib import Path

import yaml


def _find_root() -> Path:
    """Repository root = first parent containing configs/grid.yaml.

    Can be overridden with the OCEANEMBED_ROOT environment variable (useful
    when the package is installed and run from elsewhere).
    """
    env = os.environ.get("OCEANEMBED_ROOT")
    if env:
        return Path(env).resolve()
    for p in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
        if (p / "configs" / "grid.yaml").exists():
            return p
    raise FileNotFoundError("Cannot find the project root (configs/grid.yaml). Set OCEANEMBED_ROOT.")


ROOT = _find_root()
CONFIGS = ROOT / "configs"
DATA = ROOT / "data"
RAW, INTERIM, PROCESSED, FINAL, AUDIT = (DATA / d for d in ("raw", "interim", "processed", "final", "audit"))
FIGURES = ROOT / "reports" / "figures"


def load_yaml(name: str) -> dict:
    return yaml.safe_load((CONFIGS / name).read_text(encoding="utf-8"))
