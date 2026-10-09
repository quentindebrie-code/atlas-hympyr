"""Tests de fumée de l'application Streamlit (mode démonstration, sans réseau)."""

import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")

PAGES = {
    "accueil": "page_accueil",
    "commercial": "page_commercial",
    "exploitation": "page_exploitation",
    "ciblage": "page_ciblage",
    "fiche": "page_fiche",
    "methodo": "page_methodo",
}


def run_page(module: str) -> AppTest:
    script = f"from atlas_hympyr.app import {module}\n{module}.render()\n"
    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    return at


@pytest.mark.parametrize("module", PAGES.values())
def test_page_renders_without_exception(module):
    at = run_page(module)
    assert not at.exception, [e.value for e in at.exception]
    # la bannière de démonstration est visible sur chaque page
    assert any("DÉMONSTRATION" in e.value for e in at.error)


def test_main_entrypoint_runs():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Atlas territorial" in t.value for t in at.title)


def test_commercial_switch_product_and_metric():
    at = run_page("page_commercial")
    at.sidebar.selectbox(key="com_produit").select("gnr").run()
    assert not at.exception, [e.value for e in at.exception]
    at.sidebar.radio(key="com_metrique").set_value("Densité de demande (par km²)").run()
    assert not at.exception, [e.value for e in at.exception]


def test_exploitation_hour_changes_travel_time():
    at = run_page("page_exploitation")
    assert not at.exception
    at.sidebar.slider(key="exp_heure").set_value(8.0).run()
    assert not at.exception, [e.value for e in at.exception]
    at.sidebar.radio(key="exp_indicateur").set_value("Temps de trajet (min)").run()
    assert not at.exception, [e.value for e in at.exception]


def test_ciblage_filters_and_empty_selection():
    at = run_page("page_ciblage")
    assert not at.exception
    at.sidebar.slider(key="cib_potmin").set_value(100).run()  # filtre quasi impossible
    assert not at.exception, [e.value for e in at.exception]
    at.sidebar.slider(key="cib_potmin").set_value(20).run()
    at.sidebar.slider(key="cib_wp").set_value(0.0).run()
    at.sidebar.slider(key="cib_wd").set_value(0.0).run()
    at.sidebar.slider(key="cib_wf").set_value(0.0).run()
    assert any("poids" in w.value for w in at.warning)  # tous les poids à zéro : message clair


def test_fiche_selects_a_commune():
    at = run_page("page_fiche")
    codes = at.selectbox(key="fiche_code").options
    at.selectbox(key="fiche_code").select_index(len(codes) // 2).run()
    assert not at.exception, [e.value for e in at.exception]


def test_committed_real_atlas_renders_without_demo_banner():
    """L'atlas construit versionné dans data/processed doit s'afficher sans bandeau de démonstration."""
    import subprocess
    import sys

    repo = Path(__file__).resolve().parents[1]
    if not (repo / "data" / "processed" / "atlas.parquet").exists():
        pytest.skip("aucun atlas construit dans data/processed")
    code = (
        "from streamlit.testing.v1 import AppTest\n"
        f"at = AppTest.from_file(r'{APP}', default_timeout=120).run()\n"
        "assert not at.exception, [e.value for e in at.exception]\n"
        "assert not any('DÉMONSTRATION' in e.value for e in at.error), 'bandeau de démonstration affiché'\n"
        "print('OK')\n"
    )
    env = {**os.environ, "ATLAS_ROOT": str(repo)}
    res = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, env=env, cwd=repo
    )
    assert res.returncode == 0 and "OK" in res.stdout, res.stdout[-500:] + res.stderr[-800:]
