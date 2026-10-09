"""Chargement mis en cache des données et des scores."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from atlas_hympyr.config import get, load_settings, produits
from atlas_hympyr.data_access import Atlas, load_atlas
from atlas_hympyr.demo import demo_penalites
from atlas_hympyr.paths import CONFIG_FILE, PENALITES_FILE, PROCESSED_DIR
from atlas_hympyr.scoring import (
    add_difficulte,
    add_potentiel,
    add_temps_ajuste,
    load_penalites,
)


def _mtime(path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def data_token() -> tuple[float, float]:
    """Date de modification de l'atlas construit et de la configuration.

    Sert de clé de cache : sans elle, une application hébergée qui reçoit de nouvelles données
    continuerait d'afficher l'ancien atlas (ou la démonstration) tant qu'on ne la redémarre pas.
    """
    return _mtime(PROCESSED_DIR / "atlas.parquet"), _mtime(CONFIG_FILE)


@st.cache_resource(show_spinner="Chargement de l'atlas…")
def _load_atlas_cached(token: tuple[float, float]) -> Atlas:
    return load_atlas()


@st.cache_resource
def _load_settings_cached(token: tuple[float, float]) -> dict:
    return load_settings()


def get_atlas() -> Atlas:
    return _load_atlas_cached(data_token())


def get_settings() -> dict:
    return _load_settings_cached(data_token())


def get_penalites() -> pd.DataFrame:
    atlas = get_atlas()
    return demo_penalites() if atlas.is_demo else load_penalites(PENALITES_FILE)


def has_penalites() -> bool:
    pen = get_penalites()
    return bool((pen["coef"] > 1.0).any()) if not pen.empty else False


def poids_difficulte() -> dict[str, float]:
    return {k: float(v) for k, v in (get(get_settings(), "scoring.poids_difficulte", {}) or {}).items()}


def poids_priorite() -> dict[str, float]:
    return {k: float(v) for k, v in (get(get_settings(), "scoring.poids_priorite", {}) or {}).items()}


def enriched(depot_id: str | None, heure: float | None) -> pd.DataFrame:
    """Table des communes avec potentiels, trajets depuis le dépôt et difficulté d'accès."""
    return _enriched(depot_id, heure, data_token())


@st.cache_data(show_spinner=False)
def _enriched(depot_id: str | None, heure: float | None, token: tuple[float, float]) -> pd.DataFrame:
    atlas = get_atlas()
    cfg = get_settings()
    df = add_potentiel(atlas.table(depot_id), produits(cfg))
    temps_col = "trajet_min"
    if heure is not None and "trajet_min" in df.columns:
        df = add_temps_ajuste(df, get_penalites(), heure)
        temps_col = "trajet_ajuste_min"
    return add_difficulte(df, poids_difficulte(), temps_col)


def produits_cfg() -> dict[str, dict]:
    return produits(get_settings())


def libelle(key: str) -> str:
    return produits_cfg().get(key, {}).get("libelle", key)
