"""Surfaces agricoles par commune à partir du Registre parcellaire graphique (IGN).

Les surfaces sont recalculées depuis la géométrie en Lambert-93 (EPSG:2154) : pas de dépendance au
nom du champ « surface » du fichier. Chaque parcelle est affectée à la commune qui contient un point
intérieur à la parcelle (une parcelle à cheval sur deux communes est comptée dans une seule).
Nécessite l'extra « etl » (geopandas).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from atlas_hympyr.etl.tabular import check_file

HOW_TO = "Télécharger le RPG (parcelles ou îlots) sur le site de l'IGN / data.gouv.fr."


def aggregate_surfaces(parcelles, communes) -> pd.DataFrame:
    """parcelles, communes : GeoDataFrames (CRS défini). Retourne code, surf_agri_ha."""
    import geopandas as gpd

    if parcelles.crs is None or communes.crs is None:
        raise ValueError("CRS manquant sur les parcelles ou les communes")
    p = parcelles.to_crs(2154)
    c = communes[["code", "geometry"]].to_crs(2154)
    pts = gpd.GeoDataFrame(
        {"surf_ha": p.geometry.area / 10_000},
        geometry=p.geometry.representative_point(),
        crs=2154,
    )
    joined = gpd.sjoin(pts, c, how="inner", predicate="within")
    out = joined.groupby("code", as_index=False)["surf_ha"].sum()
    return out.rename(columns={"surf_ha": "surf_agri_ha"})


def load_rpg(cfg_source: dict[str, Any], communes_geojson: dict[str, Any]) -> pd.DataFrame:
    import geopandas as gpd

    path = check_file(cfg_source["fichier"], HOW_TO)
    gdf = gpd.read_file(path, layer=cfg_source.get("couche"))
    if gdf.crs is None:
        gdf = gdf.set_crs(int(cfg_source.get("crs_defaut", 2154)))
    col = cfg_source.get("colonne_groupe_culture")
    exclus = cfg_source.get("groupes_exclus") or []
    if col and exclus:
        if col not in gdf.columns:
            raise ValueError(f"Colonne « {col} » absente du RPG (colonnes : {list(gdf.columns)})")
        gdf = gdf[~gdf[col].astype(str).isin([str(x) for x in exclus])]
    communes = gpd.GeoDataFrame.from_features(communes_geojson["features"], crs=4326)
    return aggregate_surfaces(gdf, communes)
