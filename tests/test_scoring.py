import numpy as np
import pandas as pd
import pytest

from atlas_hympyr import scoring as sc

PRODUITS = {"fioul": {"indicateur": "rp_fioul"}, "gnr": {"indicateur": "surf_agri_ha"}}


def base_df():
    return pd.DataFrame(
        {
            "code": ["A", "B", "C", "D", "E"],
            "dept": ["31", "31", "81", "81", "09"],
            "surface_km2": [10.0, 10.0, 20.0, 5.0, 10.0],
            "rp_fioul": [0, 10, 40, 100, 100],
            "surf_agri_ha": [np.nan] * 5,
            "trajet_min": [10, 20, 30, 40, 100],
            "altitude_m": [100, 150, 200, 900, 1500],
        }
    )


def test_pct_rank_zero_is_floor():
    r = sc.pct_rank(pd.Series([0, 5, 10, 20]), zero_is_floor=True)
    assert r.iloc[0] == 0
    assert r.iloc[1] < r.iloc[2] < r.iloc[3] == 100


def test_pct_rank_keeps_nan():
    r = sc.pct_rank(pd.Series([1, np.nan, 3]))
    assert np.isnan(r.iloc[1]) and r.iloc[2] == 100


def test_add_potentiel_only_available_products():
    df = sc.add_potentiel(base_df(), PRODUITS)
    assert "pot_fioul" in df and "pot_gnr" not in df
    assert df.loc[0, "pot_fioul"] == 0
    # D et E ont le même volume mais D est deux fois plus dense
    assert df.loc[3, "densp_fioul"] > df.loc[4, "densp_fioul"]
    assert sc.produits_disponibles(df, PRODUITS) == ["fioul"]


def test_weighted_mean_renormalises_missing_components():
    parts = {"a": pd.Series([100.0, np.nan]), "b": pd.Series([0.0, 50.0])}
    out = sc.weighted_mean(parts, {"a": 1, "b": 1})
    assert out.tolist() == [50.0, 50.0]


def test_weighted_mean_requires_positive_weight():
    with pytest.raises(ValueError):
        sc.weighted_mean({"a": pd.Series([1.0])}, {"a": 0})


def test_difficulte_orders_by_remoteness_and_reports_completeness():
    df = sc.add_difficulte(base_df(), {"temps": 0.5, "altitude": 0.25, "sinuosite": 0.25})
    assert df["difficulte"].is_monotonic_increasing
    assert df["difficulte"].iloc[-1] > df["difficulte"].iloc[0]
    # la sinuosité est absente : 0.75 / 1.0 des poids disponibles
    assert df["difficulte_completude"].iloc[0] == pytest.approx(0.75)
    assert set(df["cls_difficulte"].dropna()) <= set(sc.CLASSES_DIFFICULTE)


def test_difficulte_without_any_component():
    df = sc.add_difficulte(base_df()[["code", "dept", "surface_km2"]], {"temps": 1.0})
    assert df["difficulte"].isna().all() and (df["difficulte_completude"] == 0).all()


def test_priorite_prefers_high_potential_and_easy_access():
    df = sc.add_potentiel(base_df(), PRODUITS)
    df = sc.add_difficulte(df, {"temps": 1.0})
    df = sc.add_priorite(df, "fioul", {"potentiel": 0.5, "densite": 0.2, "facilite": 0.3})
    # D (fort volume, accès correct) devrait dépasser E (même volume, très loin)
    assert df.loc[3, "priorite_fioul"] > df.loc[4, "priorite_fioul"]


def test_priorite_without_difficulty_falls_back_to_potential():
    df = sc.add_potentiel(base_df(), PRODUITS)
    df = sc.add_priorite(df, "fioul", {"potentiel": 1, "densite": 0, "facilite": 1})
    assert df["priorite_fioul"].notna().all()


def test_select_targets_filters():
    df = sc.add_potentiel(base_df(), PRODUITS)
    df = sc.add_difficulte(df, {"temps": 1.0})
    df = sc.add_priorite(df, "fioul", {"potentiel": 1, "densite": 0, "facilite": 1})
    out = sc.select_targets(df, "fioul", 10, departements=["81"], potentiel_min=10)
    assert set(out["dept"]) == {"81"}
    out = sc.select_targets(df, "fioul", 2)
    assert len(out) == 2
    assert out["priorite_fioul"].is_monotonic_decreasing


def test_concentration_curve():
    c = sc.concentration_curve(pd.Series([100, 0, 0, 50, 50]))
    assert c["part_communes"].iloc[0] == 0 and c["part_volume"].iloc[-1] == pytest.approx(1.0)
    assert c["part_volume"].iloc[1] == pytest.approx(0.5)  # la plus grosse commune = 50 %


def test_penalites_matching_and_max_rule(tmp_path):
    pen = pd.DataFrame(
        [
            ("ALL", 7, 9, 1.1, ""),
            ("DEP:31", 7, 9, 1.3, ""),
            ("C", 7, 9, 1.5, ""),
        ],
        columns=sc.PENALITES_COLONNES,
    )
    df = base_df()
    coef = sc.coef_penalite(df["code"], df["dept"], pen, 8.0)
    assert coef.tolist() == [1.3, 1.3, 1.5, 1.1, 1.1]
    assert sc.coef_penalite(df["code"], df["dept"], pen, 12.0).eq(1.0).all()
    out = sc.add_temps_ajuste(df, pen, 8.0)
    assert out.loc[0, "trajet_ajuste_min"] == pytest.approx(13.0)


def test_load_penalites_validation(tmp_path):
    p = tmp_path / "p.csv"
    p.write_text("zone;heure_debut;heure_fin;coef;commentaire\nALL;7;9;0.8;x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="< 1"):
        sc.load_penalites(p)
    p.write_text("zone;heure_debut\nALL;7\n", encoding="utf-8")
    with pytest.raises(ValueError, match="manquantes"):
        sc.load_penalites(p)
    assert sc.load_penalites(tmp_path / "absent.csv").empty


def test_shipped_penalites_template_is_neutral():
    from atlas_hympyr.paths import PENALITES_FILE

    pen = sc.load_penalites(PENALITES_FILE)
    assert (pen["coef"] == 1.0).all()
