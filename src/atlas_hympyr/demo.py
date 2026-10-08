"""Territoire de démonstration 100 % synthétique.

Les « communes » sont des cases d'une grille, leurs valeurs sont générées aléatoirement avec une
structure plausible (montagne au sud, ville au centre). RIEN de ce qui est produit ici ne décrit
le territoire réel : l'application l'affiche en permanence.
"""

from __future__ import annotations

import datetime as dt
import warnings

import numpy as np
import pandas as pd

from atlas_hympyr.data_access import Atlas
from atlas_hympyr.geo import geometry_area_centroid, haversine_km
from atlas_hympyr.scoring import PENALITES_COLONNES

DEMO_DEPOT = {"id": "demo-depot", "nom": "Dépôt fictif (démonstration)", "lat": 43.60, "lon": 1.45}
AVERTISSEMENT = (
    "DONNÉES DE DÉMONSTRATION SYNTHÉTIQUES : communes fictives, valeurs aléatoires. "
    "Ne pas utiliser pour décider."
)


def _dept(lat: float, lon: float) -> str:
    if lat < 43.05 and lon < 0.7:
        return "65"
    if lat < 43.05 and lon < 1.7:
        return "09"
    if lat < 43.2 and lon >= 1.7:
        return "11"
    if lon < 0.5:
        return "32"
    if lon >= 2.0:
        return "81"
    if lat >= 43.9:
        return "82"
    return "31"


def _neighbourhood_range(grid: np.ndarray) -> np.ndarray:
    """Amplitude (max - min) d'altitude sur le voisinage 3x3, en ignorant les NaN."""
    padded = np.pad(grid, 1, constant_values=np.nan)
    stack = np.stack(
        [padded[i : i + grid.shape[0], j : j + grid.shape[1]] for i in range(3) for j in range(3)]
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # cases entièrement vides hors territoire
        rng = np.nanmax(stack, axis=0) - np.nanmin(stack, axis=0)
    return np.nan_to_num(rng)


def build_demo(seed: int = 42) -> Atlas:
    rng = np.random.default_rng(seed)
    lats = np.arange(42.75, 44.40, 0.05)
    lons = np.arange(-0.30, 2.75, 0.07)
    dlat, dlon = 0.05, 0.07

    rows: list[dict] = []
    feats: list[dict] = []
    index: dict[tuple[int, int], int] = {}
    for i, la in enumerate(lats):
        for j, lo in enumerate(lons):
            if ((la - 43.55) / 0.85) ** 2 + ((lo - 1.2) / 1.6) ** 2 > 1:
                continue
            ring = [
                [lo, la],
                [lo + dlon, la],
                [lo + dlon, la + dlat],
                [lo, la + dlat],
                [lo, la],
            ]
            geom = {"type": "Polygon", "coordinates": [ring]}
            area, clon, clat = geometry_area_centroid(geom)
            n = len(rows) + 1
            code = f"D{n:04d}"
            index[(i, j)] = len(rows)
            rows.append(
                {
                    "code": code,
                    "nom": f"Commune fictive {n:04d}",
                    "dept": _dept(clat, clon),
                    "lon": clon,
                    "lat": clat,
                    "surface_km2": area,
                    "_ij": (i, j),
                }
            )
            feats.append(
                {
                    "type": "Feature",
                    "properties": {"code": code, "nom": f"Commune fictive {n:04d}"},
                    "geometry": geom,
                }
            )
    df = pd.DataFrame(rows)
    lat = df["lat"].to_numpy()
    lon = df["lon"].to_numpy()

    def gauss2(lat0: float, lon0: float, s: float) -> np.ndarray:
        return np.exp(-(((lat - lat0) / s) ** 2 + ((lon - lon0) / (s * 1.3)) ** 2))

    urban = np.clip(
        gauss2(43.60, 1.44, 0.18) + 0.35 * gauss2(43.23, 0.07, 0.10) + 0.30 * gauss2(43.92, 2.15, 0.10), 0, 1
    )
    density = 18 + 2600 * urban + rng.normal(0, 6, len(df)).clip(-10, 30)
    population = (density * df["surface_km2"]).round().astype(int)

    alt = (
        80
        + 2100 * np.exp(-(((lat - 42.75) / 0.28) ** 2))
        + 450 * np.exp(-((((lat - 43.45) / 0.20) ** 2) + (((lon - 2.35) / 0.35) ** 2)))
        + rng.normal(0, 40, len(df))
    ).clip(50, None)

    rp_total = (population / 2.2).round().astype(int)
    rural = 1 / (1 + density / 200)
    share_fioul = (0.04 + 0.16 * rural + rng.normal(0, 0.03, len(df))).clip(0, 0.45)
    share_bois = (0.04 + 0.22 * (alt / 2200) + rng.normal(0, 0.02, len(df))).clip(0, 0.5)
    agri_share = (0.75 * (1 - urban) - 0.7 * (alt / 2200) + rng.normal(0, 0.08, len(df))).clip(0, 0.85)

    df["population"] = population
    df["rp_total"] = rp_total
    df["rp_fioul"] = rng.binomial(rp_total, share_fioul)
    df["rp_autre"] = rng.binomial(rp_total, share_bois)
    df["surf_agri_ha"] = (df["surface_km2"] * 100 * agri_share).round(1)
    df["pl_entreprises"] = rng.poisson(population / 400 + 8 * urban)
    df["pl_diesel_recents"] = rng.binomial(df["pl_entreprises"].to_numpy(), 0.45)
    df["altitude_m"] = alt.round(0)
    df["trafic_idx"] = (100 * urban + rng.normal(0, 6, len(df))).clip(0, 100).round(1)

    # Amplitude locale de relief (sert à fabriquer un dénivelé synthétique)
    grid = np.full((len(lats), len(lons)), np.nan)
    for (i, j), k in index.items():
        grid[i, j] = alt[k]
    relief = _neighbourhood_range(grid)
    local_relief = np.array([relief[i, j] for (i, j) in df["_ij"]])
    df = df.drop(columns="_ij")

    depot = DEMO_DEPOT
    hav = haversine_km(depot["lat"], depot["lon"], df["lat"], df["lon"]).to_numpy()
    sinuosite = (12 + 0.03 * alt + rng.normal(0, 6, len(df))).clip(4, None)
    km = hav * 1.3 * (1 + sinuosite / 400)
    minutes = km / 55 * 60 * (1 + alt / 6000)
    denivele = 0.5 * np.abs(alt - 150) + 0.6 * local_relief + rng.normal(0, 25, len(df)).clip(0, None)
    routes = pd.DataFrame(
        {
            "code": df["code"],
            "trajet_km": km.round(1),
            "trajet_min": minutes.round(0),
            "sinuosite_deg_km": sinuosite.round(1),
            "denivele_m": denivele.round(0),
        }
    )

    geojson = {"type": "FeatureCollection", "features": feats}
    meta = {
        "mode": "demo",
        "avertissement": AVERTISSEMENT,
        "generated_at": dt.date.today().isoformat(),
        "routage": "synthetique",
        "sources": {},
    }
    return Atlas(df, geojson, {depot["id"]: routes}, [dict(depot)], meta)


def demo_penalites() -> pd.DataFrame:
    """Pénalités illustratives pour la démonstration uniquement (aucune valeur réelle)."""
    return pd.DataFrame(
        [
            ("DEP:31", 7.0, 9.0, 1.30, "démo"),
            ("DEP:31", 17.0, 19.0, 1.35, "démo"),
            ("ALL", 7.0, 9.0, 1.05, "démo"),
        ],
        columns=PENALITES_COLONNES,
    )
