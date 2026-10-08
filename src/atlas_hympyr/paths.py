"""Chemins du projet. La variable d'environnement ATLAS_ROOT permet de les surcharger."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("ATLAS_ROOT")
    if env:
        return Path(env).resolve()
    # src/atlas_hympyr/paths.py -> racine du dépôt
    return Path(__file__).resolve().parents[2]


ROOT = repo_root()
CONFIG_FILE = ROOT / "config" / "settings.yaml"
PENALITES_FILE = ROOT / "config" / "penalites_horaires.csv"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DOCS_DIR = ROOT / "docs"
