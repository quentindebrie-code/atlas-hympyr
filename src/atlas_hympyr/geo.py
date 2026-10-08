"""Fonctions géométriques pures (sans dépendance géospatiale lourde)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np

EARTH_RADIUS_KM = 6371.0088
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON_EQUATOR = 111.320

Coord = Sequence[float]  # (lon, lat)


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance à vol d'oiseau en km (vectorisée)."""
    la1, lo1, la2, lo2 = (np.radians(v) for v in (lat1, lon1, lat2, lon2))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


# --- surfaces et centroïdes -------------------------------------------------------------


def _ring_xy_km(ring: Sequence[Coord]) -> tuple[np.ndarray, np.ndarray, float, float, float]:
    arr = np.asarray(ring, dtype=float)
    if arr.ndim != 2 or arr.shape[0] < 3:
        raise ValueError("Anneau invalide : au moins 3 points attendus")
    if not np.allclose(arr[0], arr[-1]):
        arr = np.vstack([arr, arr[0]])
    lon0, lat0 = arr[0, 0], arr[0, 1]
    lat_mid = float(arr[:, 1].mean())
    x = (arr[:, 0] - lon0) * math.cos(math.radians(lat_mid)) * KM_PER_DEG_LON_EQUATOR
    y = (arr[:, 1] - lat0) * KM_PER_DEG_LAT
    return x, y, lon0, lat0, lat_mid


def _ring_area_centroid(ring: Sequence[Coord]) -> tuple[float, float, float]:
    """Retourne (aire km² positive, lon, lat du centroïde) d'un anneau."""
    x, y, lon0, lat0, lat_mid = _ring_xy_km(ring)
    cross = x[:-1] * y[1:] - x[1:] * y[:-1]
    signed = 0.5 * cross.sum()
    area = abs(signed)
    if area < 1e-12:
        return 0.0, float(lon0), float(lat0)
    cx = ((x[:-1] + x[1:]) * cross).sum() / (6 * signed)
    cy = ((y[:-1] + y[1:]) * cross).sum() / (6 * signed)
    lon = lon0 + cx / (math.cos(math.radians(lat_mid)) * KM_PER_DEG_LON_EQUATOR)
    lat = lat0 + cy / KM_PER_DEG_LAT
    return float(area), float(lon), float(lat)


def _polygons(geom: dict[str, Any]) -> list[list[list[Coord]]]:
    gtype = geom.get("type")
    if gtype == "Polygon":
        return [geom["coordinates"]]
    if gtype == "MultiPolygon":
        return list(geom["coordinates"])
    raise ValueError(f"Géométrie non supportée : {gtype}")


def geometry_area_centroid(geom: dict[str, Any]) -> tuple[float, float, float]:
    """(aire km², lon, lat) d'une géométrie GeoJSON Polygon/MultiPolygon (approx. locale ~1 %)."""
    total = 0.0
    sx = 0.0
    sy = 0.0
    for rings in _polygons(geom):
        for i, ring in enumerate(rings):
            area, lon, lat = _ring_area_centroid(ring)
            weight = area if i == 0 else -area  # les trous se soustraient
            total += weight
            sx += weight * lon
            sy += weight * lat
    if total <= 0:
        raise ValueError("Surface nulle ou négative")
    return total, sx / total, sy / total


# --- tracés routiers ---------------------------------------------------------------------


def project_m(coords: Sequence[Coord]) -> np.ndarray:
    """Projette (lon, lat) en mètres dans un repère local (équirectangulaire)."""
    arr = np.asarray(coords, dtype=float)
    lat_mid = float(arr[:, 1].mean())
    x = (arr[:, 0] - arr[0, 0]) * math.cos(math.radians(lat_mid)) * KM_PER_DEG_LON_EQUATOR * 1000
    y = (arr[:, 1] - arr[0, 1]) * KM_PER_DEG_LAT * 1000
    return np.column_stack([x, y])


def polyline_length_m(xy: np.ndarray) -> float:
    if len(xy) < 2:
        return 0.0
    return float(np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1])).sum())


def resample_xy(xy: np.ndarray, step_m: float) -> np.ndarray:
    """Rééchantillonne une polyligne (mètres) à pas constant."""
    if step_m <= 0:
        raise ValueError("step_m doit être > 0")
    seg = np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1]))
    dist = np.concatenate([[0.0], np.cumsum(seg)])
    total = dist[-1]
    if total == 0:
        return xy[:1]
    s = np.arange(0.0, total, step_m)
    s = np.append(s, total)
    return np.column_stack([np.interp(s, dist, xy[:, 0]), np.interp(s, dist, xy[:, 1])])


def resample_lonlat(coords: Sequence[Coord], step_m: float) -> np.ndarray:
    """Points (lon, lat) régulièrement espacés le long d'un tracé (pour échantillonner un MNT)."""
    arr = np.asarray(coords, dtype=float)
    xy = project_m(arr)
    seg = np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1]))
    dist = np.concatenate([[0.0], np.cumsum(seg)])
    if dist[-1] == 0:
        return arr[:1]
    s = np.append(np.arange(0.0, dist[-1], step_m), dist[-1])
    return np.column_stack([np.interp(s, dist, arr[:, 0]), np.interp(s, dist, arr[:, 1])])


def sinuosity_deg_per_km(coords: Sequence[Coord], step_m: float = 250.0) -> float:
    """Sinuosité d'un tracé = somme des changements de cap (degrés) par km.

    Le tracé est rééchantillonné à pas fixe pour ne pas dépendre de la densité de points
    de numérisation. 0 pour une ligne droite ; ~360/km pour un cercle de ~160 m de rayon.
    """
    xy = project_m(coords)
    length_km = polyline_length_m(xy) / 1000
    if length_km == 0:
        return 0.0
    rs = resample_xy(xy, step_m)
    if len(rs) < 3:
        return 0.0
    heading = np.arctan2(np.diff(rs[:, 1]), np.diff(rs[:, 0]))
    dtheta = np.diff(heading)
    dtheta = (dtheta + np.pi) % (2 * np.pi) - np.pi
    return float(np.degrees(np.abs(dtheta)).sum() / length_km)


def cumulative_ascent(elevations: Sequence[float], threshold_m: float = 5.0) -> float:
    """Dénivelé positif cumulé avec filtre d'hystérésis (ignore le bruit < threshold_m)."""
    vals = [float(v) for v in elevations if v is not None and not math.isnan(float(v))]
    if len(vals) < 2:
        return 0.0
    ref = vals[0]
    total = 0.0
    for v in vals[1:]:
        if v - ref >= threshold_m:
            total += v - ref
            ref = v
        elif ref - v >= threshold_m:
            ref = v
    return total
