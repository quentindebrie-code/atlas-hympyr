"""Tests de la chaîne d'import sur des fichiers fictifs.

Ils prouvent la logique (filtrage, agrégation, couverture, garde-fous), PAS la compatibilité avec
les vrais fichiers Insee / SDES / IGN : les noms de colonnes réels sont à renseigner par
l'utilisateur dans config/settings.yaml.
"""

import json

import pandas as pd
import pytest

from atlas_hympyr.config import ConfigError
from atlas_hympyr.data_access import load_real
from atlas_hympyr.etl import colonnes
from atlas_hympyr.etl.build import assemble, build
from atlas_hympyr.etl.communes import parse_feature_collection
from atlas_hympyr.etl.insee_logement import load_insee_logement
from atlas_hympyr.etl.routing import EstimationProvider, OSRMProvider, parse_osrm_route
from atlas_hympyr.etl.sdes_parc import load_sdes_parc
from atlas_hympyr.etl.tabular import normalize_code, to_number
from atlas_hympyr.scoring import add_difficulte, add_potentiel


def square(lon, lat, d=0.1):
    return {
        "type": "Polygon",
        "coordinates": [[[lon, lat], [lon + d, lat], [lon + d, lat + d], [lon, lat + d], [lon, lat]]],
    }


def feature_collection(dep, n=3, lon0=1.0, lat0=43.0):
    feats = [
        {
            "type": "Feature",
            "properties": {"code": f"{dep}{i:03d}", "nom": f"Ville {dep}-{i}", "population": 100 * i},
            "geometry": square(lon0 + 0.1 * i, lat0),
        }
        for i in range(1, n + 1)
    ]
    return {"type": "FeatureCollection", "features": feats}


# --- communes -------------------------------------------------------------------------------


def test_parse_feature_collection():
    df, feats = parse_feature_collection(feature_collection("31"))
    assert list(df["code"]) == ["31001", "31002", "31003"]
    assert (df["dept"] == "31").all() and (df["surface_km2"] > 50).all()
    assert len(feats) == 3 and feats[0]["properties"] == {"code": "31001", "nom": "Ville 31-1"}


def test_parse_feature_collection_rejects_unexpected_schema():
    fc = {"type": "FeatureCollection", "features": [{"properties": {"foo": 1}, "geometry": square(0, 0)}]}
    with pytest.raises(ValueError, match="attendus"):
        parse_feature_collection(fc)
    with pytest.raises(ValueError, match="FeatureCollection"):
        parse_feature_collection({"type": "Autre"})


def test_simplification_keeps_valid_polygon():
    _, feats = parse_feature_collection(feature_collection("31", 1), simplification_deg=0.001)
    ring = feats[0]["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1] and len(ring) >= 4


# --- insee / sdes --------------------------------------------------------------------------


def test_normalize_helpers():
    assert normalize_code(pd.Series(["9001", "31555", 9002.0])).tolist() == ["09001", "31555", "09002"]
    assert to_number(pd.Series(["1,5", " 2 ", "x"])).fillna(-1).tolist() == [1.5, 2.0, -1.0]


def test_insee_loader(tmp_path):
    f = tmp_path / "insee.csv"
    f.write_text("CODGEO;TOT;FIOUL;BOIS\n9001;100;12,5;4\n31555;5000;10;1\n75056;999;9;9\n", encoding="utf-8")
    cfg = {
        "fichier": str(f),
        "separateur": ";",
        "colonnes": {"code": "CODGEO", "rp_total": "TOT", "rp_fioul": "FIOUL", "rp_autre": "BOIS"},
    }
    df = load_insee_logement(cfg, ["09", "31"]).set_index("code")
    assert set(df.index) == {"09001", "31555"}  # Paris exclu, zéro de tête restauré
    assert df.loc["09001", "rp_fioul"] == 12.5


def test_insee_loader_requires_mapping_and_file(tmp_path):
    with pytest.raises(ConfigError, match="non renseignées"):
        load_insee_logement({"fichier": "x", "colonnes": {"code": None, "rp_fioul": None}}, ["31"])
    cfg = {"fichier": str(tmp_path / "absent.csv"), "colonnes": {"code": "A", "rp_fioul": "B"}}
    with pytest.raises(FileNotFoundError, match="télécharger"):
        load_insee_logement(cfg, ["31"])


SDES = (
    "COMMUNE;GENRE;ENERGIE;USAGER;CRITAIR;NB\n"
    "31555;PL;Diesel;Entreprise;2;10\n"
    "31555;PL;Diesel;Ménage;2;5\n"
    "31555;VP;Diesel;Entreprise;2;99\n"
    "31555;PL;Essence;Entreprise;3;7\n"
    "9001;PL;Diesel;Entreprise;3;s\n"
    "9001;PL;Diesel;Entreprise;2;4\n"
    "75056;PL;Diesel;Entreprise;2;50\n"
)


def sdes_cfg(path, **over):
    cfg = {
        "fichier": str(path),
        "separateur": ";",
        "colonnes": {
            "code": "COMMUNE",
            "nombre": "NB",
            "genre": "GENRE",
            "energie": "ENERGIE",
            "utilisateur": "USAGER",
            "crit_air": "CRITAIR",
        },
        "filtres": {
            "pl_entreprises": {"genre": ["PL"], "utilisateur": ["Entreprise"]},
            "pl_diesel_recents": {"genre": ["PL"], "energie": ["diesel"], "crit_air": ["2"]},
        },
    }
    cfg.update(over)
    return cfg


def test_sdes_loader_filters_and_aggregates(tmp_path):
    f = tmp_path / "sdes.csv"
    f.write_text(SDES, encoding="utf-8")
    res, stats = load_sdes_parc(sdes_cfg(f), ["09", "31"], chunksize=2)
    res = res.set_index("code")
    assert res.loc["31555", "pl_entreprises"] == 17  # 10 diesel + 7 essence, ménage et VP exclus
    assert res.loc["31555", "pl_diesel_recents"] == 15  # Crit'Air 2 diesel PL : 10 + 5
    assert res.loc["09001", "pl_entreprises"] == 4  # la valeur « s » compte pour 0
    assert "75056" not in res.index
    assert stats["valeurs_non_numeriques"] == 1


def test_sdes_loader_guards(tmp_path):
    f = tmp_path / "sdes.csv"
    f.write_text(SDES, encoding="utf-8")
    bad = sdes_cfg(f, filtres={"pl_entreprises": {"genre": []}})
    with pytest.raises(ConfigError, match="vide"):
        load_sdes_parc(bad, ["31"])
    bad = sdes_cfg(f, filtres={"x": {"couleur": ["rouge"]}})
    with pytest.raises(ConfigError, match="inconnue"):
        load_sdes_parc(bad, ["31"])


def test_sdes_year_filter(tmp_path):
    f = tmp_path / "sdes.csv"
    f.write_text("COMMUNE;GENRE;NB;AN\n31555;PL;10;2025\n31555;PL;12;2026\n", encoding="utf-8")
    cfg = {
        "fichier": str(f),
        "colonnes": {"code": "COMMUNE", "nombre": "NB", "genre": "GENRE"},
        "filtres": {"pl": {"genre": ["PL"]}},
        "annee_colonne": "AN",
        "annee_valeur": "2026",
    }
    res, _ = load_sdes_parc(cfg, ["31"])
    assert res.loc[0, "pl"] == 12


# --- RPG ------------------------------------------------------------------------------------


def test_rpg_aggregation():
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import box

    from atlas_hympyr.etl.rpg import aggregate_surfaces

    communes = gpd.GeoDataFrame(
        {"code": ["A", "B"]},
        geometry=[box(600000, 6500000, 601000, 6501000), box(601000, 6500000, 602000, 6501000)],
        crs=2154,
    )
    parcelles = gpd.GeoDataFrame(
        geometry=[
            box(600100, 6500100, 600200, 6500200),  # 1 ha dans A
            box(600300, 6500300, 600500, 6500400),  # 2 ha dans A
            box(601100, 6500100, 601200, 6500200),  # 1 ha dans B
            box(700000, 6500000, 700100, 6500100),  # hors communes
        ],
        crs=2154,
    )
    out = aggregate_surfaces(parcelles, communes).set_index("code")
    assert out.loc["A", "surf_agri_ha"] == pytest.approx(3.0)
    assert out.loc["B", "surf_agri_ha"] == pytest.approx(1.0)
    with pytest.raises(ValueError, match="CRS"):
        aggregate_surfaces(gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)]), communes)


# --- routage et MNT -----------------------------------------------------------------------


def test_estimation_provider():
    depot = {"id": "d", "lat": 43.0, "lon": 1.0}
    communes = pd.DataFrame({"code": ["a", "b"], "lat": [43.0, 43.0], "lon": [1.0, 1.5]})
    out = EstimationProvider(60, 1.3).metrics(depot, communes)
    assert out.loc[0, "trajet_min"] == 0
    assert out.loc[1, "trajet_km"] == pytest.approx(40.7 * 1.3, rel=0.05)
    assert out.loc[1, "trajet_min"] == pytest.approx(out.loc[1, "trajet_km"], abs=1)  # 60 km/h
    with pytest.raises(ValueError):
        EstimationProvider(0, 1.3)


OSRM_OK = {
    "code": "Ok",
    "routes": [
        {
            "distance": 20000,
            "duration": 1800,
            "geometry": {"coordinates": [[1.0 + 0.001 * i, 43.0 + 0.0003 * (i % 7)] for i in range(200)]},
        }
    ],
}


def test_parse_osrm_route():
    r = parse_osrm_route(OSRM_OK)
    assert r["distance_m"] == 20000 and len(r["coords"]) == 200
    assert parse_osrm_route({"code": "NoRoute", "routes": []}) is None
    with pytest.raises(ValueError):
        parse_osrm_route({"code": "Ok", "routes": [{"distance": 1}]})


def test_osrm_provider_with_stub_and_failures():
    calls = []

    def fake_get(url, params):
        calls.append(url)
        if "9.0" in url:
            raise RuntimeError("serveur indisponible")
        return OSRM_OK

    prov = OSRMProvider("http://x/", coef_pl=1.2, get_json=fake_get, workers=2)
    depot = {"id": "d", "lat": 43.0, "lon": 1.0}
    communes = pd.DataFrame({"code": ["ok", "ko"], "lon": [1.5, 9.0], "lat": [43.1, 43.1]})
    out = prov.metrics(depot, communes).set_index("code")
    assert out.loc["ok", "trajet_km"] == 20.0
    assert out.loc["ok", "trajet_min"] == pytest.approx(36.0)  # 30 min x 1.2
    assert out.loc["ok", "sinuosite_deg_km"] > 0
    assert pd.isna(out.loc["ko", "trajet_min"])  # l'échec d'une commune n'arrête pas le lot
    assert calls[0].startswith("http://x/route/v1/driving/1.0,43.0;")


def test_dem_sampler_and_ascent(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    import numpy as np
    from rasterio.transform import from_origin

    from atlas_hympyr.etl.dem import DemSampler

    path = tmp_path / "mnt.tif"
    # rampe : altitude = 100 m + 1000 m par degré de longitude, pixels de 0,01°
    lons = 1.0 + 0.01 * np.arange(200)
    data = np.tile(100 + 1000 * (lons - 1.0), (200, 1)).astype("float32")
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=200,
        width=200,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(1.0, 44.0, 0.01, 0.01),
        nodata=-9999,
    ) as dst:
        dst.write(data, 1)
    dem = DemSampler(str(path))
    assert dem.altitude(1.505, 43.5) == pytest.approx(600, abs=15)
    ascent = dem.route_ascent([(1.0, 43.5), (1.5, 43.5)], step_m=500)
    assert ascent == pytest.approx(500, rel=0.15)
    dem.close()


# --- colonnes (aide) --------------------------------------------------------------------------


def test_colonnes_helper(tmp_path):
    f = tmp_path / "f.csv"
    f.write_text("CODGEO;P22_RP_FIOUL;P22_RP_BOIS\n1;2;3\n", encoding="utf-8")
    cols = colonnes.read_header(f, ";")
    found = colonnes.find_columns(cols, ["fioul", "gaz"])
    assert found["fioul"] == ["P22_RP_FIOUL"] and found["gaz"] == []
    f2 = tmp_path / "g.csv"
    f2.write_text("GENRE\nPL\nVP\nPL\n", encoding="latin-1")
    assert colonnes.distinct_values(f2, ";", "GENRE") == ["PL", "VP"]


# --- assemblage et construction de bout en bout (hors ligne) -----------------------------------


def test_assemble_reports_coverage():
    communes = pd.DataFrame({"code": [f"c{i}" for i in range(20)]})
    parts = {
        "ok": pd.DataFrame({"code": [f"c{i}" for i in range(20)], "x": range(20)}),
        "mauvais": pd.DataFrame({"code": ["c1", "c2", "zzz"], "y": [1, 2, 3]}),
    }
    out, rep = assemble(communes, parts)
    assert rep["ok"]["alerte"] is False and rep["ok"]["taux_couverture"] == 1.0
    assert rep["mauvais"]["alerte"] is True and rep["mauvais"]["exemples_inconnus"] == ["zzz"]
    assert out["y"].notna().sum() == 2


def test_end_to_end_build_offline(tmp_path):
    insee = tmp_path / "insee.csv"
    insee.write_text(
        "CODGEO;TOT;FIOUL\n"
        + "\n".join(f"{dep}{i:03d};{200 * i};{20 * i}" for dep in ("31", "81") for i in range(1, 4))
        + "\n",
        encoding="utf-8",
    )
    cfg = {
        "perimetre": {"departements": ["31", "81"]},
        "depots": [{"id": "d1", "nom": "Dépôt test", "lat": 43.0, "lon": 1.0}],
        "routage": {
            "fournisseur": "estimation",
            "estimation": {"vitesse_moyenne_kmh": 50, "coef_detour": 1.3},
        },
        "geo": {"api_communes": "https://exemple/{dep}", "simplification_deg": 0.0},
        "sources": {
            "insee_logement": {
                "fichier": str(insee),
                "colonnes": {"code": "CODGEO", "rp_total": "TOT", "rp_fioul": "FIOUL", "rp_autre": None},
            },
            "sdes_parc": {"fichier": str(tmp_path / "absent.csv"), "colonnes": {}},
            "rpg": {"fichier": str(tmp_path / "absent.gpkg")},
        },
    }

    def fake_api(url, params):
        dep = url.rsplit("/", 1)[-1]
        return feature_collection(dep, lon0=1.0 if dep == "31" else 2.0)

    out = tmp_path / "out"
    logs: list[str] = []
    atlas = build(cfg, out, log=logs.append, get_json=fake_api)
    assert len(atlas.communes) == 6
    assert atlas.communes["rp_fioul"].notna().all()
    assert any("[sdes] IGNORÉ" in line for line in logs)  # source absente -> ignorée, pas bloquante
    assert "pl_entreprises" not in atlas.communes

    reloaded = load_real(out)
    assert reloaded.meta["mode"] == "reel" and reloaded.depots[0]["id"] == "d1"
    t = reloaded.table("d1")
    t = add_potentiel(t, {"fioul": {"indicateur": "rp_fioul"}, "gnr": {"indicateur": "surf_agri_ha"}})
    assert "pot_fioul" in t and "pot_gnr" not in t  # produit indisponible : pas de colonne fantôme
    t = add_difficulte(t, {"temps": 1.0})
    assert t["difficulte"].notna().all() and t["difficulte_completude"].iloc[0] == 1.0
    json.loads((out / "meta.json").read_text(encoding="utf-8"))

    # en mode strict, une source non configurée interrompt la construction
    with pytest.raises(ConfigError):
        build(cfg, tmp_path / "out2", strict=True, log=logs.append, get_json=fake_api)
