"""Lecture et écriture de l'atlas (table des communes, contours, trajets par dépôt, métadonnées)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from atlas_hympyr.paths import PROCESSED_DIR

ATLAS_PARQUET = "atlas.parquet"
ATLAS_GEOJSON = "atlas.geojson"
ATLAS_META = "meta.json"
ROUTES_DIR = "routes"

ROUTE_COLUMNS = [
    "code",
    "trajet_min",
    "trajet_km",
    "sinuosite_deg_km",
    "denivele_m",
]


@dataclass
class Atlas:
    communes: pd.DataFrame
    geojson: dict[str, Any]
    routes: dict[str, pd.DataFrame] = field(default_factory=dict)
    depots: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_demo(self) -> bool:
        return self.meta.get("mode") == "demo"

    def table(self, depot_id: str | None = None) -> pd.DataFrame:
        """Table des communes, enrichie des trajets depuis le dépôt choisi (si disponible)."""
        df = self.communes
        if depot_id and depot_id in self.routes:
            r = self.routes[depot_id]
            cols = [c for c in r.columns if c == "code" or c not in df.columns]
            df = df.merge(r[cols], on="code", how="left")
        return df.copy()


def save_atlas(atlas: Atlas, out_dir: str | Path) -> None:
    out = Path(out_dir)
    (out / ROUTES_DIR).mkdir(parents=True, exist_ok=True)
    atlas.communes.to_parquet(out / ATLAS_PARQUET, index=False)
    with (out / ATLAS_GEOJSON).open("w", encoding="utf-8") as fh:
        json.dump(atlas.geojson, fh, ensure_ascii=False, separators=(",", ":"))
    for depot_id, r in atlas.routes.items():
        r.to_parquet(out / ROUTES_DIR / f"{depot_id}.parquet", index=False)
    meta = dict(atlas.meta)
    meta["depots"] = atlas.depots
    with (out / ATLAS_META).open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)


def has_real_data(processed_dir: str | Path | None = None) -> bool:
    d = Path(processed_dir) if processed_dir else PROCESSED_DIR
    return (d / ATLAS_PARQUET).exists() and (d / ATLAS_GEOJSON).exists()


def load_real(processed_dir: str | Path | None = None) -> Atlas:
    d = Path(processed_dir) if processed_dir else PROCESSED_DIR
    communes = pd.read_parquet(d / ATLAS_PARQUET)
    with (d / ATLAS_GEOJSON).open(encoding="utf-8") as fh:
        geojson = json.load(fh)
    meta: dict[str, Any] = {}
    if (d / ATLAS_META).exists():
        with (d / ATLAS_META).open(encoding="utf-8") as fh:
            meta = json.load(fh)
    depots = list(meta.pop("depots", []))
    routes = {p.stem: pd.read_parquet(p) for p in sorted((d / ROUTES_DIR).glob("*.parquet"))}
    meta.setdefault("mode", "reel")
    return Atlas(communes, geojson, routes, depots, meta)


def load_atlas(processed_dir: str | Path | None = None, force_demo: bool = False) -> Atlas:
    """Données réelles si le répertoire processed les contient, sinon démonstration synthétique."""
    if not force_demo and has_real_data(processed_dir):
        return load_real(processed_dir)
    from atlas_hympyr.demo import build_demo

    return build_demo()
