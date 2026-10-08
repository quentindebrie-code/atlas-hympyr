import json

import pandas as pd
import pytest

from atlas_hympyr.backtest import evaluate_potential
from atlas_hympyr.config import load_settings, produits
from atlas_hympyr.data_access import has_real_data, load_atlas, load_real, save_atlas
from atlas_hympyr.demo import DEMO_DEPOT, build_demo
from atlas_hympyr.scoring import add_potentiel


def test_demo_is_deterministic_and_flagged():
    a, b = build_demo(), build_demo()
    pd.testing.assert_frame_equal(a.communes, b.communes)
    assert a.is_demo and "DÉMONSTRATION" in a.meta["avertissement"]
    assert len(a.communes) > 500
    assert a.communes["code"].is_unique
    assert len(a.geojson["features"]) == len(a.communes)


def test_demo_codes_cannot_be_confused_with_insee():
    assert build_demo().communes["code"].str.startswith("D").all()


def test_demo_table_contains_route_columns():
    t = build_demo().table(DEMO_DEPOT["id"])
    for col in ("trajet_min", "trajet_km", "sinuosite_deg_km", "denivele_m"):
        assert col in t and t[col].notna().all()


def test_save_and_reload_roundtrip(tmp_path):
    a = build_demo()
    save_atlas(a, tmp_path)
    assert has_real_data(tmp_path)
    b = load_real(tmp_path)
    assert len(b.communes) == len(a.communes)
    assert set(b.routes) == set(a.routes)
    assert b.depots[0]["id"] == DEMO_DEPOT["id"]
    json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))


def test_load_atlas_falls_back_to_demo(tmp_path):
    assert load_atlas(tmp_path).is_demo


def test_backtest_perfect_proxy_and_unmatched_codes():
    cfg = load_settings()
    df = add_potentiel(build_demo().communes, produits(cfg))
    ventes = pd.DataFrame({"code": df["code"], "volume": df["vol_fioul"] * 1000})
    ventes.loc[len(ventes)] = ["99999", 5]
    res = evaluate_potential(df, ventes, "fioul")
    assert res["spearman"] > 0.99
    # avec un proxy parfait, la part captée par le top 30 % = concentration réelle du volume
    vol = df["vol_fioul"].sort_values(ascending=False)
    attendu = vol.head(int(len(df) * 0.3)).sum() / vol.sum()
    assert res["part_volume_reel_dans_top"] == pytest.approx(attendu, abs=0.005)
    assert res["codes_ventes_inconnus"] == ["99999"]


def test_backtest_rejects_bad_input():
    df = add_potentiel(build_demo().communes, produits(load_settings()))
    with pytest.raises(ValueError):
        evaluate_potential(df, pd.DataFrame({"code": ["1"]}), "fioul")
    with pytest.raises(ValueError):
        evaluate_potential(df, pd.DataFrame({"code": ["1"], "volume": [1]}), "inconnu")
