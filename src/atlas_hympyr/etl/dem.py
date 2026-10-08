"""Échantillonnage d'un modèle numérique de terrain (GeoTIFF) : altitude et dénivelé."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from atlas_hympyr.geo import cumulative_ascent, resample_lonlat


class DemSampler:
    """Lit un raster d'altitude (n'importe quel CRS) et l'échantillonne en lon/lat WGS84."""

    def __init__(self, path: str):
        import rasterio

        self._ds = rasterio.open(path)
        self._nodata = self._ds.nodata

    def close(self) -> None:
        self._ds.close()

    def sample(self, lons: Sequence[float], lats: Sequence[float]) -> np.ndarray:
        from rasterio.warp import transform

        crs = self._ds.crs
        if crs is not None and crs.to_epsg() != 4326:
            xs, ys = transform("EPSG:4326", crs, list(lons), list(lats))
        else:
            xs, ys = list(lons), list(lats)
        vals = np.array([v[0] for v in self._ds.sample(zip(xs, ys, strict=True))], dtype=float)
        if self._nodata is not None:
            vals[vals == self._nodata] = np.nan
        return vals

    def altitude(self, lon: float, lat: float) -> float:
        return float(self.sample([lon], [lat])[0])

    def route_ascent(self, coords: Sequence[Sequence[float]], step_m: float = 250.0) -> float:
        pts = resample_lonlat(coords, step_m)
        elev = self.sample(pts[:, 0], pts[:, 1])
        return cumulative_ascent(elev.tolist())
