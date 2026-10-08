"""Temps, distances, sinuosité et dénivelé depuis un dépôt vers chaque commune.

Deux fournisseurs :
- EstimationProvider : hors ligne, distance à vol d'oiseau x coefficient de détour (ordre de grandeur).
- OSRMProvider : serveur OSRM auto-hébergé sur un extrait OpenStreetMap (API /route/v1, geometries
  geojson). Le profil OSRM par défaut est « voiture » : appliquer un coefficient poids lourd
  calibré (routage.coef_temps_poids_lourd). Les points d'arrivée sont les centroïdes des communes,
  recalés par OSRM sur la route la plus proche (en montagne, vérifier les cas extrêmes).
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
import pandas as pd

from atlas_hympyr.geo import haversine_km, sinuosity_deg_per_km

COLUMNS = ["code", "trajet_km", "trajet_min", "sinuosite_deg_km", "denivele_m"]


class EstimationProvider:
    def __init__(self, vitesse_kmh: float, coef_detour: float, coef_pl: float = 1.0):
        if vitesse_kmh <= 0 or coef_detour < 1:
            raise ValueError("vitesse_kmh > 0 et coef_detour >= 1 attendus")
        self.v, self.detour, self.coef_pl = vitesse_kmh, coef_detour, coef_pl

    def metrics(self, depot: dict[str, Any], communes: pd.DataFrame) -> pd.DataFrame:
        hav = haversine_km(depot["lat"], depot["lon"], communes["lat"], communes["lon"])
        km = hav * self.detour
        return pd.DataFrame(
            {
                "code": communes["code"].to_numpy(),
                "trajet_km": km.round(1).to_numpy(),
                "trajet_min": (km / self.v * 60 * self.coef_pl).round(0).to_numpy(),
                "sinuosite_deg_km": np.nan,
                "denivele_m": np.nan,
            }
        )


def parse_osrm_route(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extrait distance (m), durée (s) et tracé d'une réponse /route/v1 ; None si pas d'itinéraire."""
    if payload.get("code") != "Ok" or not payload.get("routes"):
        return None
    r = payload["routes"][0]
    coords = (r.get("geometry") or {}).get("coordinates")
    if coords is None or "distance" not in r or "duration" not in r:
        raise ValueError("Réponse OSRM inattendue : geometry/distance/duration manquants")
    return {"distance_m": float(r["distance"]), "duration_s": float(r["duration"]), "coords": coords}


class OSRMProvider:
    def __init__(
        self,
        url: str,
        profil: str = "driving",
        timeout_s: float = 20,
        coef_pl: float = 1.0,
        dem: Any | None = None,
        workers: int = 4,
        get_json: Callable[[str, dict[str, str]], dict[str, Any]] | None = None,
    ):
        self.url = url.rstrip("/")
        self.profil = profil
        self.timeout = timeout_s
        self.coef_pl = coef_pl
        self.dem = dem
        self.workers = workers
        self._get_json = get_json or self._default_get

    def _default_get(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        import requests

        r = requests.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def route(self, depot: dict[str, Any], lon: float, lat: float) -> dict[str, Any] | None:
        coords = f"{depot['lon']},{depot['lat']};{lon},{lat}"
        url = f"{self.url}/route/v1/{self.profil}/{coords}"
        return parse_osrm_route(
            self._get_json(url, {"overview": "full", "geometries": "geojson", "steps": "false"})
        )

    def _one(self, depot: dict[str, Any], row: tuple[str, float, float]) -> dict[str, Any]:
        code, lon, lat = row
        out: dict[str, Any] = dict.fromkeys(COLUMNS, np.nan)
        out["code"] = code
        try:
            r = self.route(depot, lon, lat)
        except Exception:  # un échec ponctuel ne doit pas faire échouer les 2 800 autres
            return out
        if r is None:
            return out
        out["trajet_km"] = round(r["distance_m"] / 1000, 1)
        out["trajet_min"] = round(r["duration_s"] / 60 * self.coef_pl, 0)
        out["sinuosite_deg_km"] = round(sinuosity_deg_per_km(r["coords"]), 1)
        if self.dem is not None:
            out["denivele_m"] = round(self.dem.route_ascent(r["coords"]), 0)
        return out

    def metrics(self, depot: dict[str, Any], communes: pd.DataFrame) -> pd.DataFrame:
        rows = list(zip(communes["code"], communes["lon"], communes["lat"], strict=True))
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            results = list(ex.map(lambda r: self._one(depot, r), rows))
        return pd.DataFrame(results, columns=COLUMNS)
