"""Vue commerciale : qui consomme quoi, où."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from atlas_hympyr.app import ui
from atlas_hympyr.app.state import enriched, get_atlas, libelle, produits_cfg
from atlas_hympyr.scoring import produits_disponibles

METRIQUES = {
    "Volume estimé": ("vol_", ":,.0f", "Volume estimé"),
    "Densité de demande (par km²)": ("dens_", ":.2f", "Par km²"),
    "Score de potentiel (0-100)": ("pot_", ":.0f", "Potentiel"),
}


def render() -> None:
    atlas = get_atlas()
    ui.banner(atlas)
    st.header("Vue commerciale : où est la demande ?")
    df = enriched(None, None)
    dispo = produits_disponibles(df, produits_cfg())
    if not dispo:
        st.warning("Aucun produit n'a de données de potentiel. Voir le README (données réelles).")
        return

    segments = sorted({produits_cfg()[k].get("segment", "") for k in dispo})
    seg = st.sidebar.radio("Segment", ["Tous", *segments], key="com_segment")
    choix = [k for k in dispo if seg == "Tous" or produits_cfg()[k].get("segment") == seg]
    produit = st.sidebar.selectbox("Produit", choix, format_func=libelle, key="com_produit")
    metrique = st.sidebar.radio("Indicateur affiché", list(METRIQUES), key="com_metrique")
    depts = sorted(df["dept"].unique())
    sel = st.sidebar.multiselect("Départements", depts, default=depts, key="com_depts")

    prefix, fmt, legende = METRIQUES[metrique]
    colonne = f"{prefix}{produit}"
    d = df[df["dept"].isin(sel)] if sel else df
    p = produits_cfg()[produit]
    st.caption(f"{p['libelle']} · {p['segment']} · proxy : {p['unite']}")
    if p.get("avertissement"):
        st.warning(f"Fiabilité {p.get('fiabilite', 'à vérifier')} — {p['avertissement']}")

    fig = ui.carte(
        d,
        atlas.geojson,
        colonne,
        legende,
        ui.BLEUS,
        {
            "dept": "",
            f"vol_{produit}": ":,.0f",
            f"dens_{produit}": ":.2f",
            f"pot_{produit}": ":.0f",
            f"cls_pot_{produit}": "",
        },
    )
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Communes au plus fort potentiel")
        top = d.sort_values(colonne, ascending=False).head(15)
        cols = ["nom", "dept", "population", f"vol_{produit}", f"dens_{produit}", f"pot_{produit}"]
        st.dataframe(
            top[[c for c in cols if c in top]],
            hide_index=True,
            width="stretch",
            column_config={
                "nom": "Commune",
                "dept": "Dép.",
                "population": ui.num_column("Population"),
                f"vol_{produit}": ui.num_column("Volume estimé"),
                f"dens_{produit}": ui.num_column("Par km²", "%.2f"),
                f"pot_{produit}": ui.score_column("Potentiel"),
            },
        )
    with c2:
        st.subheader("Répartition par département")
        par_dept = d.groupby("dept", as_index=False)[f"vol_{produit}"].sum().sort_values("dept")
        bar = px.bar(
            par_dept,
            x="dept",
            y=f"vol_{produit}",
            text_auto=",.0f",
            labels={"dept": "Département", f"vol_{produit}": "Volume estimé"},
            color_discrete_sequence=[ui.BLEUS[4]],
        )
        bar.update_layout(height=360, margin={"l": 0, "r": 0, "t": 10, "b": 0}, showlegend=False)
        st.plotly_chart(bar, width="stretch")

    export = d[["code", "nom", "dept", f"vol_{produit}", f"dens_{produit}", f"pot_{produit}"]]
    st.download_button(
        "Exporter la sélection (CSV)",
        ui.csv_bytes(export.sort_values(colonne, ascending=False)),
        file_name=f"potentiel_{produit}.csv",
        mime="text/csv",
        key="com_export",
    )
    ui.methodo_note(
        "Le **volume estimé** est un proxy de la demande (ex. nombre de résidences principales "
        "chauffées au fioul), pas une quantité de produit. Le **score** classe les communes de 0 à "
        "100 (les communes sans demande valent 0). La **densité** privilégie les zones où une "
        "tournée est rentable. Valider ce potentiel contre les ventes réelles avec "
        "`python -m atlas_hympyr.backtest` avant de s'en servir pour décider."
    )
