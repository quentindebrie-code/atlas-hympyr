"""Fiche commune : tous les indicateurs d'une commune, comparés au territoire."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from atlas_hympyr.app import ui
from atlas_hympyr.app.state import enriched, get_atlas, libelle, produits_cfg
from atlas_hympyr.scoring import produits_disponibles

COMPOSANTES = {
    "d_temps": "Temps de trajet",
    "d_sinuosite": "Sinuosité",
    "d_altitude": "Altitude",
    "d_denivele": "Dénivelé",
    "d_trafic": "Circulation",
}


def render() -> None:
    atlas = get_atlas()
    ui.banner(atlas)
    st.header("Fiche commune")
    depot = ui.depot_selector(atlas, "fiche_depot")
    df = enriched(depot, None).sort_values("nom").reset_index(drop=True)
    # libellé unique « Nom (code) » : permet de chercher par nom ou par code INSEE
    labels = dict(zip(df["nom"] + " (" + df["code"] + ")", df["code"], strict=True))
    choix = st.selectbox("Commune (saisir pour chercher)", list(labels), key="fiche_code")
    code = labels[choix]
    row = df[df["code"] == code].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Département", row["dept"])
    c2.metric("Population", ui.fmt_int(row.get("population")))
    c3.metric("Surface (km²)", f"{row['surface_km2']:.1f}")
    c4.metric("Altitude (m)", ui.fmt_int(row.get("altitude_m")))

    st.subheader("Potentiel par produit")
    dispo = produits_disponibles(df, produits_cfg())
    lignes = []
    for k in dispo:
        rang = df.groupby("dept")[f"vol_{k}"].rank(ascending=False, method="min")
        dep_n = int((df["dept"] == row["dept"]).sum())
        r = int(rang[df["code"] == code].iloc[0])
        lignes.append(
            {
                "Produit": libelle(k),
                "Volume estimé": row[f"vol_{k}"],
                "Potentiel (0-100)": row[f"pot_{k}"],
                "Niveau": row[f"cls_pot_{k}"],
                "Rang dans le département": f"{r} / {dep_n}",
            }
        )
    if lignes:
        st.dataframe(
            pd.DataFrame(lignes),
            hide_index=True,
            width="stretch",
            column_config={
                "Volume estimé": ui.num_column("Volume estimé"),
                "Potentiel (0-100)": ui.score_column("Potentiel (0-100)"),
            },
        )
    else:
        st.info("Aucun indicateur de potentiel disponible.")

    st.subheader("Difficulté d'accès")
    if pd.notna(row.get("difficulte")):
        st.markdown(
            f"**{row['cls_difficulte']}** · score {row['difficulte']:.0f} / 100 "
            f"· temps {ui.fmt_int(row.get('trajet_min'))} min · {ui.fmt_int(row.get('trajet_km'))} km"
        )
        comp = {v: row[k] for k, v in COMPOSANTES.items() if k in df and pd.notna(row.get(k))}
        fig = go.Figure(
            go.Bar(
                x=list(comp.values()),
                y=list(comp),
                orientation="h",
                marker_color=ui.ORANGES[3],
                text=[f"{v:.0f}" for v in comp.values()],
                hovertemplate="%{y} : mieux classé que %{x:.0f} % des communes<extra></extra>",
            )
        )
        fig.update_layout(
            height=260,
            margin={"l": 0, "r": 0, "t": 10, "b": 0},
            xaxis={"range": [0, 100], "title": "Rang sur le territoire (100 = le plus difficile)"},
            yaxis={"autorange": "reversed"},
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Difficulté d'accès non calculable (dépôt ou indicateurs manquants).")
