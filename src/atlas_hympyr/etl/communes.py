"""Contours et référentiel des communes via l'API Découpage administratif (geo.api.gouv.fr).

Endpoint et paramètres (fields, format=geojson, geometry=contour) vérifiés dans la documentation de
l'API ; les noms exacts des propriétés renvoyées (code, nom, population) n'ont pas pu être
confirmés sur une réponse réelle : le parseur échoue avec un message explicite s'ils diffèrent.
La surface et le centroïde sont recalculés depuis la géométrie (pas de dépendance à l'unité du
champ « surface » de l'API).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pandas as pd

from atlas_hympyr.geo import geometry_area_centroid

GetJson = Callable[[str, dict[str, str]], dict[str, Any]]


def default_get_json(url: str, params: dict[str, str]) -> dict[str, Any]:
    import requests  # extra « etl »

    last: Exception | None = None
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:  # réseau, 5xx...
            last = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"Échec de l'appel {url} après 3 essais : {last}")


def fetch_departement(dep: str, url_template: str, get_json: GetJson | None = None) -> dict:
    get = get_json or default_get_json
    params = {"fields": "code,nom,population", "format": "geojson", "geometry": "contour"}
    return get(url_template.format(dep=dep), params)


def _round_coords(obj: Any, nd: int = 5) -> Any:
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(v), nd) for v in obj]
        return [_round_coords(o, nd) for o in obj]
    return obj


def simplify_geometry(geom: dict[str, Any], tolerance_deg: float) -> dict[str, Any]:
    """Simplifie (si shapely est installé) et arrondit les coordonnées pour alléger le web."""
    try:
        from shapely.geometry import mapping, shape

        simple = mapping(shape(geom).simplify(tolerance_deg, preserve_topology=True))
        geom = {"type": simple["type"], "coordinates": simple["coordinates"]}
    except ImportError:  # sans shapely : arrondi seul
        pass
    return {"type": geom["type"], "coordinates": _round_coords(geom["coordinates"])}


def parse_feature_collection(
    fc: dict[str, Any], simplification_deg: float = 0.0
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if fc.get("type") != "FeatureCollection":
        raise ValueError(f"Réponse inattendue (type={fc.get('type')!r}) : FeatureCollection attendu")
    rows: list[dict[str, Any]] = []
    feats: list[dict[str, Any]] = []
    for f in fc.get("features", []):
        props = f.get("properties") or {}
        if "code" not in props or "nom" not in props:
            raise ValueError(
                f"Propriétés inattendues {sorted(props)} : « code » et « nom » sont attendus. "
                "Vérifier la réponse de l'API (paramètre fields)."
            )
        geom = f.get("geometry")
        if not geom:
            continue
        area, lon, lat = geometry_area_centroid(geom)
        code = str(props["code"])
        rows.append(
            {
                "code": code,
                "nom": props["nom"],
                "dept": code[:2],
                "lon": lon,
                "lat": lat,
                "surface_km2": area,
                "population": props.get("population"),
            }
        )
        out_geom = simplify_geometry(geom, simplification_deg) if simplification_deg else geom
        feats.append(
            {
                "type": "Feature",
                "properties": {"code": code, "nom": props["nom"]},
                "geometry": out_geom,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["population"] = pd.to_numeric(df["population"], errors="coerce")
    return df, feats


def build_communes(
    departements: list[str],
    url_template: str,
    simplification_deg: float,
    get_json: GetJson | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frames: list[pd.DataFrame] = []
    features: list[dict[str, Any]] = []
    for dep in departements:
        df, feats = parse_feature_collection(
            fetch_departement(dep, url_template, get_json), simplification_deg
        )
        if df.empty:
            raise ValueError(f"Aucune commune renvoyée pour le département {dep}")
        frames.append(df)
        features.extend(feats)
    out = pd.concat(frames, ignore_index=True)
    if not out["code"].is_unique:
        raise ValueError("Codes communes en double dans la réponse de l'API")
    return out, {"type": "FeatureCollection", "features": features}
