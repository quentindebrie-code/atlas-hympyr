"""Composants d'interface partagés : bannière, carte, formats, export."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from atlas_hympyr.data_access import Atlas

# Rampes séquentielles monochromes (une teinte, clair -> foncé), cf. docs/METHODOLOGIE.md
BLEUS = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
ORANGES = ["#fde8dc", "#f8c9ad", "#f2a47c", "#eb6834", "#c24f22", "#8c3a18", "#5e2710"]
CENTRE = {"lat": 43.55, "lon": 1.25}
# « white-bg » : aucun fond de carte externe (aucune requête vers un tiers depuis le navigateur)
MAP_STYLE = os.environ.get("ATLAS_MAP_STYLE", "carto-positron")


def fmt_int(x: Any) -> str:
    if x is None or pd.isna(x):
        return "n.d."
    return f"{x:,.0f}".replace(",", " ")


def banner(atlas: Atlas) -> None:
    if atlas.is_demo:
        st.error(
            "**DONNÉES DE DÉMONSTRATION SYNTHÉTIQUES.** Les communes sont fictives et les valeurs "
            "aléatoires : cet écran illustre l'outil, il ne décrit pas le territoire réel et ne "
            "doit servir à aucune décision. Pour charger les vraies données, voir le README.",
            icon=None,
        )
    else:
        gen = str(atlas.meta.get("generated_at", ""))[:10]
        routage = atlas.meta.get("routage", "estimation")
        msg = f"Données construites le {gen}."
        if routage == "estimation":
            msg += " Temps de trajet **estimés** (vol d'oiseau x coefficient de détour)."
        st.caption(msg)


def carte(
    df: pd.DataFrame,
    geojson: dict[str, Any],
    colonne: str,
    titre_legende: str,
    echelle: list[str],
    hover: dict[str, str],
    *,
    hauteur: int = 620,
) -> go.Figure:
    """Carte choroplèthe par commune. `hover` : colonne -> format d'affichage ('' = brut)."""
    hover_data = {"code": False, **{c: (f if f else True) for c, f in hover.items() if c in df}}
    fig = px.choropleth_map(
        df,
        geojson=geojson,
        locations="code",
        featureidkey="properties.code",
        color=colonne,
        color_continuous_scale=echelle,
        hover_name="nom",
        hover_data=hover_data,
        map_style=MAP_STYLE,
        center=CENTRE,
        zoom=6.4,
        opacity=0.78,
    )
    fig.update_traces(marker_line_width=0.2, marker_line_color="rgba(255,255,255,0.6)")
    fig.update_layout(
        height=hauteur,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        coloraxis_colorbar={"title": titre_legende, "thickness": 14, "len": 0.6},
    )
    return fig


def csv_bytes(df: pd.DataFrame) -> bytes:
    """CSV lisible par Excel en français (séparateur ;, virgule décimale, UTF-8 avec BOM)."""
    return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


def score_column(label: str) -> Any:
    return st.column_config.ProgressColumn(label, min_value=0, max_value=100, format="%.0f")


def num_column(label: str, fmt: str = "%.0f") -> Any:
    return st.column_config.NumberColumn(label, format=fmt)


def depot_selector(atlas: Atlas, key: str) -> str | None:
    if not atlas.routes:
        st.sidebar.warning("Aucun dépôt configuré : difficulté calculée sans trajets.")
        return None
    ids = list(atlas.routes)
    names = {d["id"]: d.get("nom", d["id"]) for d in atlas.depots}
    if len(ids) == 1:
        st.sidebar.caption(f"Dépôt : {names.get(ids[0], ids[0])}")
        return ids[0]
    return st.sidebar.selectbox("Dépôt de départ", ids, format_func=lambda i: names.get(i, i), key=key)


def methodo_note(texte: str) -> None:
    with st.expander("Comment lire cet écran"):
        st.markdown(texte)
