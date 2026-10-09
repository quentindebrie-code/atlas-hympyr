"""Les tests visent le mode démonstration : ils ne doivent pas dépendre de l'atlas réel versionné.

ATLAS_ROOT est posé avant tout import du paquet : le dépôt de test contient la configuration et les
pénalités, mais aucun atlas construit (data/processed vide).
"""

import os
import shutil
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_ROOT = Path(tempfile.mkdtemp(prefix="atlas_test_root_"))
shutil.copytree(_REPO / "config", _ROOT / "config")
(_ROOT / "data" / "processed").mkdir(parents=True)
(_ROOT / "data" / "raw").mkdir(parents=True)
os.environ["ATLAS_ROOT"] = str(_ROOT)
